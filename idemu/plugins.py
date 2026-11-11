"""plugins – extensões de host em pastas/ZIPs que caem na pasta `plugins/`.

Cada plugin é um ZIP (`meutool.zip`) ou uma pasta (`meutool/`) com um `plugin.json` e cai na pasta
`plugins/` do projeto; a GUI os reenumera ao iniciar e com `POST /api/plugins/rescan`. O ZIP é
desempacotado em `plugins/.installed/<id>/` (re-desempacotado quando o arquivo muda) e os arquivos
são servidos em `/plugins/<id>/<caminho>` — o JavaScript do plugin roda na página da IDEmu e pode
registrar abas na tela Execução (`IDE.registerTab`) e chamar a API local como qualquer tela faz.

plugin.json (tudo opcional; sem ele o id vem do nome do arquivo):
  {"id": "meutool", "name": "Minha ferramenta", "version": "1.0", "description": "...",
   "scripts": ["main.js"], "styles": ["style.css"], "python": "server_side.py"}
Sem `scripts`/`styles`, todos os `.js`/`.css` na raiz do pacote entram, em ordem de nome.
`python` é opcional e avançado: o módulo é importado e `register(api)` é chamado uma vez, com
`api.id`, `api.dir` (pasta desempacotada) e `api.app` (o App do servidor — mesma liberdade que um
arquivo em tools/ tem; só plugins confiáveis). docs/PLUGINS.md.

Segurança do desempacotamento (o ZIP vem de fora): caminhos relativos só, sem `..`, sem links
simbólicos, no máximo 4096 arquivos e 256 MB.
"""
import importlib.util, json, os, re, shutil, sys, threading, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DROP = os.path.join(ROOT, 'plugins')
ID_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,31}$')
MAX_FILES = 4096
MAX_BYTES = 256 << 20

_lock = threading.Lock()
_state = {'items': [], 'mods': {}}


def _slug(name):
    s = re.sub(r'[^a-z0-9_-]+', '-', os.path.splitext(os.path.basename(name))[0].lower()).strip('-')
    return (s or 'plugin')[:32]


def _read_manifest(raw):
    try:
        m = json.loads(raw.decode('utf-8', 'replace'))
        return (m if isinstance(m, dict) else {}), None
    except ValueError as e:
        return {}, 'plugin.json inválido: %s' % e


def _check_member(name):
    """Caminho interno do ZIP: relativo, sem escapes, sem links. Devolve o caminho limpo ou None."""
    n = name.replace('\\', '/')
    if n.startswith('/'): return None                          # caminho absoluto no ZIP: anomalia, não saniza
    if not n or n.endswith('/'): return None
    parts = [p for p in n.split('/') if p not in ('', '.')]
    if any(p == '..' for p in parts) or re.match(r'^[a-zA-Z]:', n): return None
    return '/'.join(parts)


def _manifest_member(zf):
    """Localiza o plugin.json do ZIP (mais raso vence; também aceita 'pasta/plugin.json' de ZIP de pasta).
    Devolve (prefixo_do_pacote, caminho_no_zip) ou (None, motivo) quando há mais de um."""
    cands = []
    for m in zf.infolist():
        rel = _check_member(m.filename)
        if rel and rel.rsplit('/', 1)[-1].lower() == 'plugin.json': cands.append(rel)
    if not cands: return None, None
    cands.sort(key=lambda r: (r.count('/'), len(r)))
    depth = cands[0].count('/')
    if sum(1 for r in cands if r.count('/') == depth) > 1: return None, 'mais de um plugin.json no ZIP'
    best = cands[0]
    return (best.rsplit('/', 1)[0] if '/' in best else ''), best


def _extract(zf, dst, prefix=''):
    """Desempacota com as travas de sempre, removendo o prefixo (pasta de dentro do ZIP); levanta ValueError com o motivo."""
    names, total = [], 0
    for m in zf.infolist():
        if m.is_dir(): continue
        rel = _check_member(m.filename)
        if rel is None: raise ValueError('caminho rejeitado no ZIP: %s' % m.filename)
        if prefix:
            if not rel.startswith(prefix + '/'): continue            # lixo fora da pasta do plugin
            rel = rel[len(prefix) + 1:]
        if (m.external_attr >> 16) & 0o170000 == 0o120000: raise ValueError('link simbólico no ZIP: %s' % m.filename)
        total += m.file_size
        if total > MAX_BYTES: raise ValueError('ZIP grande demais (desempacotado passa de %d MB)' % (MAX_BYTES >> 20))
        names.append((m, rel))
    if len(names) > MAX_FILES: raise ValueError('ZIP com arquivos demais (%d)' % len(names))
    for m, rel in names:
        d = os.path.join(dst, *rel.split('/'))
        os.makedirs(os.path.dirname(d), exist_ok=True)
        with zf.open(m) as src, open(d, 'wb') as out:
            out.write(src.read())


def _load_dir(pdir, manifest, err, pid, src):
    if err: return {'id': pid, 'name': pid, 'version': '', 'description': '', 'scripts': [], 'styles': [], 'error': err, 'source': src}
    scripts = manifest.get('scripts') or sorted(f for f in os.listdir(pdir) if f.endswith('.js'))
    styles = manifest.get('styles') or sorted(f for f in os.listdir(pdir) if f.endswith('.css'))
    bad = [s for s in list(scripts) + list(styles) if _check_member(s) is None]
    missing = [s for s in list(scripts) + list(styles) if not os.path.isfile(os.path.join(pdir, *s.split('/')))]
    it = {'id': pid, 'name': manifest.get('name') or pid, 'version': str(manifest.get('version') or ''),
          'description': str(manifest.get('description') or ''), 'scripts': [s for s in scripts if s not in bad and s not in missing],
          'styles': [s for s in styles if s not in bad and s not in missing], 'error': None, 'source': src}
    if bad: it['error'] = 'caminho rejeitado no plugin.json: %s' % bad[0]
    elif missing: it['error'] = 'falta %s no pacote' % missing[0]
    return it


def _import_py(pid, pdir, rel, app):
    path = os.path.join(pdir, *rel.split('/'))
    if not os.path.isfile(path): raise ValueError('módulo python %s não está no pacote' % rel)
    mod = importlib.util.module_from_spec(importlib.util.spec_from_file_location('idemu_plugin_' + pid, path))
    mod.__package__ = ''
    sys.modules['idemu_plugin_' + pid] = mod
    mod.__dict__['__file__'] = path
    mod.__spec__.loader.exec_module(mod)
    reg = getattr(mod, 'register', None)
    if callable(reg):
        class Api: pass
        api = Api(); api.id = pid; api.dir = pdir; api.app = app
        reg(api)
    return mod


def scan(app=None, base=None, log=lambda m: None):
    """Enumera plugins/ (pastas e ZIPs), desempacota os ZIPs novos/alterados e devolve a lista pública.
    Plugins com defeito voltam como itens com `error` (e ficam de fora da GUI) — nunca derrubam o servidor."""
    base = base or DROP
    inst = os.path.join(base, '.installed')
    items = []
    if not os.path.isdir(base):
        with _lock: _state['items'] = items
        return public()
    entries = sorted(os.listdir(base))
    with _lock:
        for name in entries:
            if name.startswith('.'): continue
            src = os.path.join(base, name)
            loose, zpath = None, None
            if os.path.isdir(src): loose = src
            elif name.lower().endswith('.zip'): zpath = src
            else: continue
            manifest, err = {}, None
            pdir = None
            try:
                prefix = ''
                if loose:
                    if not os.path.isfile(os.path.join(loose, 'plugin.json')): continue
                    pdir = loose
                    manifest, err = _read_manifest(open(os.path.join(loose, 'plugin.json'), 'rb').read())
                else:
                    with zipfile.ZipFile(zpath) as zf:
                        prefix, found = _manifest_member(zf)
                        if found is None: continue                  # ZIP sem plugin.json não é um plugin (a pasta de despejo aceita qualquer coisa)
                        if prefix is None: err = found              # mais de um plugin.json
                        else: manifest, err = _read_manifest(zf.read(found))
                pid = str(manifest.get('id') or '').strip().lower() or _slug(name)
                if not ID_RE.match(pid): err = 'id inválido: %r (use letras minúsculas, números, - e _)' % pid
                elif any(i['id'] == pid for i in items): err = 'id repetido: %s (dois pacotes com o mesmo id)' % pid
            except zipfile.BadZipFile:
                items.append({'id': _slug(name), 'name': name, 'version': '', 'description': '', 'scripts': [], 'styles': [], 'error': 'ZIP inválido', 'source': name})
                continue
            except OSError as e:
                items.append({'id': _slug(name), 'name': name, 'version': '', 'description': '', 'scripts': [], 'styles': [], 'error': 'não consegui ler: %s' % e, 'source': name})
                continue
            if err:
                items.append({'id': pid, 'name': pid, 'version': '', 'description': '', 'scripts': [], 'styles': [], 'error': err, 'source': name})
                continue
            if zpath:
                pdir = os.path.join(inst, pid)
                stamp = os.path.join(pdir, '.idemu-src')
                cur = '%d:%d' % (os.path.getmtime(zpath), os.path.getsize(zpath))
                stale = (not os.path.isfile(stamp)) or open(stamp).read() != cur or not os.path.isfile(os.path.join(pdir, 'plugin.json'))
                if stale:
                    shutil.rmtree(pdir, ignore_errors=True)
                    os.makedirs(pdir)
                    try:
                        with zipfile.ZipFile(zpath) as zf: _extract(zf, pdir, prefix)
                        open(stamp, 'w').write(cur)
                    except (ValueError, zipfile.BadZipFile) as e:
                        items.append({'id': pid, 'name': pid, 'version': '', 'description': '', 'scripts': [], 'styles': [], 'error': str(e), 'source': name})
                        continue
            it = _load_dir(pdir, manifest, None, pid, name)
            it['pdir'] = pdir                                       # privado: só file_for() usa (fora de public())
            if not it['error'] and manifest.get('python'):
                try:
                    if pid in _state['mods']: del sys.modules['idemu_plugin_' + pid]
                    _state['mods'][pid] = _import_py(pid, pdir, str(manifest['python']), app)
                except Exception as e:
                    it['error'] = 'python: %s: %s' % (type(e).__name__, e)
                    _state['mods'].pop(pid, None)
            if it['error']: log('plugin %s: %s' % (pid, it['error']))
            items.append(it)
        _state['items'] = items
    return public()


def public():
    """A lista como a GUI vê (sem caminhos de arquivo)."""
    with _lock:
        return [{'id': i['id'], 'name': i['name'], 'version': i['version'], 'description': i['description'],
                 'scripts': i['scripts'], 'styles': i['styles'], 'error': i['error']} for i in _state['items'] if not i['error']]


def problems():
    """Plugins com defeito (para a GUI avisar), sem caminhos privados."""
    with _lock:
        return [{'id': i['id'], 'name': i['name'], 'version': i['version'], 'error': i['error'], 'source': i.get('source') or ''}
                for i in _state['items'] if i['error']]


def file_for(pid, rel):
    """Caminho absoluto de um arquivo do plugin, ou None (id desconhecido, caminho fora da pasta)."""
    with _lock:
        it = next((i for i in _state['items'] if i['id'] == pid and not i['error']), None)
    if not it: return None
    pdir = it.get('pdir')
    if not pdir: return None
    clean = _check_member(rel)
    if clean is None: return None
    p = os.path.normpath(os.path.join(pdir, *clean.split('/')))
    if not (p == os.path.normpath(pdir) or p.startswith(os.path.normpath(pdir) + os.sep)) or not os.path.isfile(p): return None
    return p
