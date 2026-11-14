"""A metade de head unit dos plugins: a parte de plugins/ que roda DENTRO do iDrive virtual.

Em IDEmu há UM tipo de plugin (a pasta plugins/, docs/PLUGINS.md). Cada pacote pode ter duas
metades independentes: a de navegador/servidor (idemu/plugins.py — abas, API, python) e esta,
a metade que roda dentro da head unit virtual, como um tweak instalado por SSH num carro real:

    plugins/<id>/
        plugin.json      opcional {"description": "..."}; o id é o nome da pasta
        pre.sh           opcional: roda no boot ANTES do HmiMain3D (source: pode exportar variáveis)
        boot.sh          opcional: roda no boot, pouco antes do HMI subir (ksh; inicialização pesada)
        lib/*.so         opcional: viram /fs/shim/ulib/<nome>.so e o pathmgr as encontra antes do HMI
        data/**          opcional: dados lidos pelos scripts ou pelo HMI (em /fs/shim/udata/<id>/)

Um pacote só com main.js/hook.py é ignorado aqui (metade de navegador apenas); um pacote só com
boot.sh é um plugin legítimo que vive inteiramente dentro do carro. Os arquivos da metade de
navegador (*.js, *.css, *.py, __pycache__/) nunca vão para o guest.

Dois caminhos de instalação, sem concorrência entre si:

  * próximo boot (persistente): a pasta é empacotada no shim.img (builder.build_shim) e o boot.sh do
    guest roda pre.sh/boot.sh sozinho. Refazer o shim.img muda o snapshot_key (idemu/runtime.py),
    então o próximo start é frio por construção;
  * ao vivo (guest rodando): install() empurra os arquivos pelo console (shell.sock, idemu/guestfs)
    para /fs/shim/u/<id>/ e roda o script do plugin; hmi_restart() (slay HmiMain3D) faz o laço do
    boot.sh relançar o HMI em ~3 s com o pacote no lugar.

A memória do guest é RAM e o fast-boot volta ao snapshot: o que foi empurrado ao vivo dura até o
próximo start; para sobreviver ao reboot, deixe a pasta em plugins/ (caminho do próximo boot).
Formato e receitas: docs/PLUGINS.md e docs/GUESTPLUGINS.md.
"""
import json
import os
import re
import time

from . import guestfs

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(os.path.dirname(HERE), 'plugins')           # a pasta única de plugins (docs/PLUGINS.md)
GUEST_ROOT = '/fs/shim/u'                                       # onde o guest vê os pacotes instalados
GUEST_ULIB = '/fs/shim/ulib'                                    # bibliotecas dos plugins (LD_LIBRARY_PATH)
GUEST_UDATA = '/fs/shim/udata'                                  # dados dos plugins
ID_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,31}$')
SCRIPTS = ('pre.sh', 'boot.sh')


class PluginError(Exception):
    pass


def _slug(name):
    s = re.sub(r'[^a-z0-9_-]+', '-', name.strip().lower()).strip('-')[:32]
    return s


def public_dir():
    return ROOT


def _is_host_file(rel):
    """Arquivos da metade de navegador/servidor do pacote — nunca vão para o guest.
    O guest não roda python/navegador: vale para qualquer profundidade (ex.: aa_core/ do android-auto)."""
    if rel.startswith('__pycache__/') or rel.startswith('cache/'):
        return True
    return rel.endswith(('.js', '.css', '.py'))


def list_plugins():
    """Os pacotes de plugins/ que têm metade de head unit — o que o próximo boot vai trazer (e o que install() empurra).
    Pacotes só de navegador/servidor (sem pre.sh/boot.sh/lib) não são plugins de guest: ficam de fora, sem erro."""
    out = []
    if not os.path.isdir(ROOT):
        return out
    for name in sorted(os.listdir(ROOT)):
        p = os.path.join(ROOT, name)
        if name.startswith('.') or not os.path.isdir(p):
            continue
        pid = _slug(name)
        if not ID_RE.match(pid):
            continue
        desc, err = '', None
        mf = os.path.join(p, 'plugin.json')
        files = []
        for dirpath, dirnames, filenames in os.walk(p):
            if dirpath == p:
                dirnames[:] = [d for d in dirnames if not d.startswith('.') and d not in ('__pycache__', 'cache')]
            else:
                dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != '__pycache__']
            for f in sorted(filenames):
                if f.startswith('.'):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, f), p).replace(os.sep, '/')
                if _is_host_file(rel):
                    continue
                files.append(rel)
        if not any(s in files for s in SCRIPTS) and not any(f.startswith('lib/') for f in files):
            continue                                            # plugin só de navegador/servidor: nada a instalar no carro
        if os.path.isfile(mf):
            try:
                desc = str(json.load(open(mf)).get('description', ''))
            except (OSError, ValueError) as e:
                err = 'plugin.json inválido: %s' % e
        out.append({'id': pid, 'name': name, 'description': desc, 'error': err,
                    'files': files,
                    'scripts': [s for s in SCRIPTS if s in files],
                    'lib': [f[4:] for f in files if f.startswith('lib/')],
                    'dir': p})
    return out


def plugin_dir(pid):
    for p in list_plugins():
        if p['id'] == pid:
            return p
    raise PluginError('plugin de head unit desconhecido: %s (crie plugins/%s/ com boot.sh)' % (pid, pid or '?'))


def guest_files(pkg):
    """[(rel-no-pacote, absoluto-no-guest)] — o layout que pre.sh/boot.sh veem em /fs/shim/u/<id>/."""
    pid = pkg['id']
    out = []
    for rel in pkg['files']:
        if rel.startswith('lib/'):
            g = '%s/%s' % (GUEST_ULIB, os.path.basename(rel))
        elif rel.startswith('data/'):
            g = '%s/%s/%s' % (GUEST_UDATA, pid, rel[5:])
        else:
            g = '%s/%s/%s' % (GUEST_ROOT, pid, rel)
        out.append((rel, g))
    return out


def _mode_for(rel):
    if rel.endswith('.sh') or rel.endswith('.so'):
        return '0755'
    return '0644'


# ── transporte de arquivos (texto) pelo tty — o motivo de não usar guestfs.push:
# o codec base64 monta um heredoc com run_lines(), que roda CADA LINHA como um comando (nunca fecha
# o heredoc); o codec printf chama `printf`, que não existe no PATH desta firmware; e o echo embutido
# do ksh só expande octal com um $() no caminho (que traga NULs/linhas). Um `cat >> f << 'EOF'` em UM
# run() atravessa o tty como texto cru (linhas nuas, sem backslash, sem linha chamada EOF) e é
# verificado byte a byte depois. Binários (.so) precisam de um decoder no guest — ver docs/GUESTPLUGINS.md.

def push_text(g, local, remote, timeout=None):
    """Empurra um arquivo de TEXTO para o guest pela sessão aberta (heredoc em um único comando)."""
    data = open(local, 'rb').read()
    if b'\x00' in data or b'\r' in data:
        raise PluginError('%s não é texto (NUL/CR): o console é 8-bit limpo mas o tty traduz CR; '
                          'para binários, publique um decoder no guest primeiro (docs/GUESTPLUGINS.md)' % local)
    text = data.decode('utf-8')
    if re.search(r'(?m)^(EOF|\tEOF)$', text):
        raise PluginError('%s contém a palavra EOF em linha própria — não dá para embutir neste heredoc' % local)
    lines = text.split('\n')
    if not data:
        return 0
    rq = guestfs.shquote(remote)
    # heredoc do ksh precisa de TMPDIR gravável (o /tmp não existe no guest: "can't create temporary
    # file /tmp/sh…") — e cada linha vai com seu próprio \r (run_lines), senão o tty vê tudo uma linha
    script = ['export TMPDIR=${TMPDIR:-/dev/shmem}', ': > %s' % rq,
              "cat >> %s << 'EOF'" % rq] + lines + ['EOF']
    rc, out = g.run_lines(script, timeout or 60)
    if rc != 0:
        raise PluginError('falha gravando %s no guest (rc=%d): %s' % (remote, rc, out.decode('utf-8', 'replace').strip()))
    fed = sum(len(l) + 1 for l in lines)
    rc, out = g.run('wc -c < %s; wc -l < %s' % (rq, rq))
    try:
        got_b, got_l = [int(x) for x in out.decode().split()]
    except ValueError:
        raise PluginError('não consegui conferir %s no guest: %r' % (remote, out[:60]))
    # o heredoc do ksh pode ecoar 1 linha vazia no fim; conteúdo é conferido de verdade pelo chk
    if abs(got_b - fed) > 24 or abs(got_l - len(lines)) > 2:
        raise PluginError('verificação falhou em %s: guest tem %d bytes / %d linhas, esperado ~%d / %d'
                          % (remote, got_b, got_l, fed, len([l for l in lines if l != ''])))
    chk = None
    if remote.endswith('.sh'):
        chk = 'ksh -n %s' % rq                       # o guest só aceita o script se ele compilar ali
    if chk:
        rc, out = g.run('%s 2>&1 && echo SYNTAX-OK || echo SYNTAX-BAD' % chk)
        if b'SYNTAX-OK' not in out:
            raise PluginError('%s chegou corrompido no guest: %s' % (remote, out.decode('utf-8', 'replace').strip()[:160]))
    return len(data)


def _session(sock, timeout):
    """Sessão com pré-checagem: se o shell estiver preso (heredoc aberto, restinho de teste), um
    Ctrl-C seguido de ping recupera a janela antes de qualquer operação do plugin."""
    class _Opened(guestfs.GuestSession):
        def __enter__(self):
            return self                      # já aberta: `with` não pode reabrir (lock duplicado)
    g = _Opened(sock, timeout=timeout)
    g.open()
    try:
        g.run('echo IDEMU_PL_PING', timeout=5)
    except Exception:
        try:
            g._abort()
            time.sleep(0.4)
            g.run('echo IDEMU_PL_PING', timeout=8)
        except Exception as e:
            g.close()
            raise PluginError('o console do guest não responde (ambiente bootando ou shell ocupado): %s' % e)
    return g


def shell_sock(runtime):
    """O console do guest (ShellMux/ConsoleMux) do runtime em execução."""
    if runtime is None or getattr(runtime, 'state', 'stopped') not in ('booting', 'running'):
        raise PluginError('nenhum ambiente em execução: o plugin entra no próximo boot sozinho (plugins/)')
    sock = os.path.join(runtime.run, 'shell.sock')
    if not os.path.exists(sock):
        raise PluginError('este ambiente não expõe o console do guest por shell.sock (só iDrive 5/6 tem ShellMux)')
    return sock


def install(runtime, pid, timeout=60.0, run_scripts=False):
    """Empurra o pacote para o guest em execução. run_scripts=True roda os scripts na hora
    (pre.sh é sourced na sessão do console — efeitos vivêm só ali; use hmi_restart() para o HMI)."""
    pkg = plugin_dir(pid)
    if pkg['error']:
        raise PluginError(pkg['error'])
    sock = shell_sock(runtime)
    files = guest_files(pkg)
    dirs = sorted({'/'.join(g.split('/')[:-1]) for _, g in files} | {GUEST_ROOT, GUEST_ULIB, GUEST_UDATA + '/' + pkg['id']})
    pushed = []
    with _session(sock, timeout) as g:
        rc, out = g.run('test -d /fs/shim && echo shim-ok')
        if rc != 0 or b'shim-ok' not in out:
            raise PluginError('o disco de shim não está montado (ambiente ainda bootando?)')
        # substitui o pacote anterior com o mesmo id
        g.run('rm -rf %s %s' % (guestfs.shquote('%s/%s' % (GUEST_ROOT, pkg['id'])), guestfs.shquote('%s/%s' % (GUEST_UDATA, pkg['id']))))
        rc, out = g.run_lines(['mkdir -p %s' % guestfs.shquote(d) for d in dirs], timeout)
        if rc != 0:
            raise PluginError('mkdir no guest falhou: %s' % out.decode('utf-8', 'replace').strip())
        for rel, gpath in files:
            n = push_text(g, os.path.join(pkg['dir'], rel), gpath)
            pushed.append({'file': rel, 'bytes': n})
        chmods = ['chmod %s %s' % (_mode_for(rel), guestfs.shquote(gpath)) for rel, gpath in files]
        rc, out = g.run_lines(chmods, timeout)
        if rc != 0:
            raise PluginError('chmod no guest falhou: %s' % out.decode('utf-8', 'replace').strip())
    if run_scripts:
        logs = {s: run(runtime, pid, s, timeout)['out'] for s in SCRIPTS if s in pkg['scripts']}
        return {'id': pkg['id'], 'pushed': pushed, 'ran': logs, 'live': True}
    return {'id': pkg['id'], 'pushed': pushed, 'live': True,
            'note': 'arquivos no guest; rode os scripts (run) ou reinicie o HMI para aplicar'}


def uninstall(runtime, pid):
    pkg = plugin_dir(pid)
    sock = shell_sock(runtime)
    libs = [ '%s/%s' % (GUEST_ULIB, os.path.basename(r)) for r, _ in guest_files(pkg) if r.startswith('lib/') ]
    with _session(sock, 30.0) as g:
        g.run('rm -rf %s %s; rm -f %s' % (guestfs.shquote('%s/%s' % (GUEST_ROOT, pkg['id'])),
                                          guestfs.shquote('%s/%s' % (GUEST_UDATA, pkg['id'])),
                                          ' '.join(guestfs.shquote(x) for x in libs)))
    return {'id': pkg['id'], 'removed': True, 'note': 'no próximo boot o pacote volta se a pasta plugins/ ainda existir'}


def run(runtime, pid, which='boot.sh', timeout=60.0):
    """Roda um script do plugin instalado no guest — do jeito que o boot.sh faria: subshell duplo e
    stdios soltos do tty, então daemons que o script dispara sobrevivem (a sessão do console é
    serializada por lock; o script em si roda em background e o log fica em /var/plug.log)."""
    pkg = plugin_dir(pid)
    if which not in SCRIPTS:
        raise PluginError('script desconhecido: %s (use pre.sh ou boot.sh)' % which)
    sock = shell_sock(runtime)
    gp = guestfs.shquote('%s/%s/%s' % (GUEST_ROOT, pkg['id'], which))
    with _session(sock, timeout) as g:
        rc, out = g.run('if [ -f %s ]; then { ( ksh %s </dev/null >>/var/plug.log 2>&1 & ) ; } ; echo launched; sleep 2; tail -6 /var/plug.log 2>/dev/null; else echo absent; fi'
                        % (gp, gp), timeout)
    return {'id': pkg['id'], 'script': which, 'out': out.decode('utf-8', 'replace').strip()}


def guest_list(runtime, timeout=15.0):
    """O que está instalado AGORA no guest (não o que existe no host)."""
    sock = shell_sock(runtime)
    with _session(sock, timeout) as g:
        rc, out = g.run('ls %s 2>/dev/null' % GUEST_ROOT, timeout)
    return [l.strip() for l in out.decode('utf-8', 'replace').splitlines() if l.strip() and not l.startswith('ls:')]


def hmi_restart(runtime, timeout=15.0):
    """Relança o HMI dentro do guest: o laço do boot.sh (boot.sh:41) traz de volta em ~3 s."""
    sock = shell_sock(runtime)
    with _session(sock, timeout) as g:
        rc, out = g.run('slay HmiMain3D 2>&1; echo done', timeout)
    return {'restarted': rc == 0, 'out': out.decode('utf-8', 'replace').strip()}
