"""Controle sem interface do ambiente em execução: aperta teclas e fotografa a tela por HTTP ou linha de comando.

Técnica inspirada no "hmi-remote" do projeto bimmulator (https://github.com/agent00jackson/bimmulator — sem
licença, por isso reimplementada do zero para o IDEmu): uma página com os botões do controlador e a tela
atualizando serve para conferir na mão, e o mesmo HTTP alimenta corridas fechadas (apertar -> fotografia ->
analisar) sem navegador, sem Electron e sem a interface web.  Onde o bimmulator fala com o QMP do QEMU e com
o soquete do servidor ANGLE, aqui vão os caminhos nativos do IDEmu: os datagramas de <ctl>/input.sock
(runtime.key/rotor/touch — os mesmos eventos que a interface web envia) e o framebuffer RGB que o glhost
escreve (runtime.screen_png).  Roda em processo próprio, anexado pelo diretório de execução (/tmp/idemu-<uid>/<id>).

  python3 -m idemu remote <id> [--port 8772]      servidor (página em http://127.0.0.1:8772/)
  python3 -m idemu remote <id> press menu next push      aperta e sai
  python3 -m idemu remote <id> screen shot.png           salva a tela atual

API (só 127.0.0.1):
  GET  /api/v1/buttons   nomes dos botões e aliases
  GET  /api/v1/state     quadro atual (seq, fps, frames por segundo do glhost, uptime)
  POST /api/v1/press     {"keys": ["menu", "next", "push"], "delay_ms": 400}
  POST /api/v1/click     {"x": 640, "y": 240, "down": true}  (toque no CID, iDrive 5/6)
  GET  /api/v1/screen.png  a tela do head unit em PNG
"""
import json
import os
import socket
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Os botões são os eventos de controlador que o shim entrega ao HMI (src/shim/hook.c, push_ctrl;
# os mesmos códigos da interface web idemu/web/run.js).  No firmware não há tecla MAP própria
# (docs/OUTRAS_GERACOES.md: "Não há tecla para MAP (5) nem NAV (7)") — 'map' segue o MEDIA, como no CIC.
KEY_BUTTONS = {'menu': 1, 'back': 2, 'options': 3, 'media': 4, 'cd': 5, 'comm': 6, 'nav': 7, 'push': 8,
               'up': 9, 'down': 10, 'left': 11, 'right': 12}
ALIASES = {'select': 'push', 'enter': 'push', 'ok': 'push', 'escape': 'back', 'home': 'menu', 'option': 'options',
           'radio': 'media', 'phone': 'comm', 'communication': 'comm', 'navigation': 'nav', 'map': 'media',
           'cw': 'next', 'ccw': 'prev', 'clockwise': 'next', 'anticlockwise': 'prev', 'counterclockwise': 'prev'}
MAX_KEYS = 64
MAX_BODY = 8192
HOLD_MS = 150          # tempo entre pressionar e soltar uma tecla de botão
TILT_MS = 80           # o servidor web usa o mesmo pulso curto para as inclinações


def button_names():
    return {'buttons': sorted(list(KEY_BUTTONS) + ['next', 'prev']), 'aliases': ALIASES}


def _resolve(name):
    key = str(name).strip().lower()
    key = ALIASES.get(key, key)
    if key in KEY_BUTTONS:
        return ('key', KEY_BUTTONS[key])
    if key in ('next', 'prev'):
        return ('rotor', 1 if key == 'next' else -1)
    raise ValueError('botao desconhecido: %r (use um de %s)' % (name, ', '.join(button_names()['buttons'])))


class Remote(object):
    """Aperta teclas e fotografa num Runtime já ligado (o ambiente tem de estar em execução)."""

    def __init__(self, rt):
        self.rt = rt
        self.lock = threading.Lock()

    def press(self, keys, delay_ms=400, hold_ms=None):
        acts = [_resolve(k) for k in keys]                     # valida tudo antes de mandar qualquer tecla
        if not 1 <= len(acts) <= MAX_KEYS:
            raise ValueError('envie de 1 a %d botoes' % MAX_KEYS)
        if not 0 <= int(delay_ms) <= 10000:
            raise ValueError('delay_ms entre 0 e 10000')
        hold = (hold_ms if hold_ms is not None else HOLD_MS) / 1000.0
        with self.lock:
            for i, (kind, arg) in enumerate(acts):
                if i:
                    time.sleep(int(delay_ms) / 1000.0)
                if kind == 'rotor':
                    self.rt.rotor(arg)
                elif arg in (9, 10, 11, 12):                   # inclinar: pulso curto, como o tilt da interface web
                    self.rt.key(arg, 1)
                    time.sleep(TILT_MS / 1000.0)
                    self.rt.key(arg, 0)
                else:
                    self.rt.key(arg, 1)
                    time.sleep(hold)
                    self.rt.key(arg, 0)
        return len(acts)

    def click(self, x, y, down=True, move=False):
        self.rt.touch(float(x), float(y), bool(down), bool(move))

    def state(self):
        seq = 0
        try:
            seq = self.rt.frame_seq()
        except Exception:
            pass
        return {'seq': seq, 'fps': getattr(self.rt, 'fps_t', None) and len(self.rt.fps_t) / 3.0 or 0,
                'state': getattr(self.rt, 'state', None),
                'uptime_s': round(time.time() - self.rt.t0, 1) if getattr(self.rt, 't0', None) else None,
                'drawing': bool(seq)}

    def bench(self, seconds=5.0, keys=None, delay_ms=400):
        """Fluxo de quadros sob uma carga repetível (giros e teclas): (frames, fps médio, fps por janela de 1 s).
        A carga e a medição são as mesmas da página, então o número é comparável entre execuções e builds."""
        acts = [_resolve(k) for k in (keys or ['next'] * 8)]
        start = self.rt.frame_seq()
        t0 = time.time()
        windows = []
        last, wstart = start, t0
        i = 0
        while time.time() - t0 < seconds:
            kind, arg = acts[i % len(acts)]
            i += 1
            if kind == 'rotor':
                self.rt.rotor(arg)
            else:
                self.rt.key(arg, 1)
                time.sleep(0.05)
                self.rt.key(arg, 0)
            time.sleep(max(0.0, int(delay_ms) / 1000.0 - 0.05))
            now, seq = time.time(), self.rt.frame_seq()
            if now - wstart >= 1.0:
                windows.append(max(0, seq - last))
                last, wstart = seq, now
        total = max(0, self.rt.frame_seq() - start)
        dur = max(1e-6, time.time() - t0)
        return {'seconds': round(dur, 2), 'frames': total, 'fps': round(total / dur, 1), 'fps_windows': windows}

    def screen_png(self):
        return self.rt.screen_png()


PAGE = """<!doctype html><meta charset="utf-8"><title>IDEmu remote</title>
<style>body{font:14px system-ui;background:#1a1c1f;color:#ddd;margin:16px;display:flex;gap:24px;flex-wrap:wrap}
img{max-width:70vw;border:1px solid #444;border-radius:6px}
.b{display:inline-block;width:86px;margin:4px;padding:10px;border-radius:8px;border:1px solid #555;background:#2c2f33;color:#eee;font-size:14px}
.b:active{background:#e57000;color:#fff}#st{color:#8a8;font:12px monospace}</style>
<h3>IDEmu remote <span id="st"></span></h3>
<div id="pad"></div><img id="scr" alt="tela do head unit">
<script>
const B=["menu","back","options","media","comm","nav","push","up","down","left","right","next","prev"];
const pad=document.getElementById('pad');
B.forEach(k=>{const b=document.createElement('button');b.className='b';b.textContent=k;
b.onclick=()=>fetch('/api/v1/press',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keys:[k]})});
pad.appendChild(b);});
const s=new Image();
async function tick(){try{const r=await fetch('/api/v1/screen.png');if(r.ok){document.getElementById('scr').src='/api/v1/screen.png?'+Date.now();}
const j=await(await fetch('/api/v1/state')).json();document.getElementById('st').textContent='q'+j.seq+' '+(j.fps||0).toFixed(1)+'fps';}catch(e){document.getElementById('st').textContent=e;}}
setInterval(tick,1500);tick();
</script>"""


class Handler(BaseHTTPRequestHandler):
    remote = None                       # definido pela fabrica

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype='application/json'):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=HTTPStatus.OK):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), 'application/json')

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        r = self.remote
        try:
            if path in ('/', '/index.html'):
                self._send(HTTPStatus.OK, PAGE.encode(), 'text/html; charset=utf-8')
            elif path == '/api/v1/buttons':
                self._json(button_names())
            elif path == '/api/v1/state':
                self._json(r.state())
            elif path == '/api/v1/screen.png':
                png, seq = r.screen_png()
                if not png:
                    self._json({'error': 'sem quadro ainda: o renderizador ainda nao desenhou'}, HTTPStatus.CONFLICT)
                else:
                    self._send(HTTPStatus.OK, png, 'image/png')
            else:
                self._json({'error': 'caminho desconhecido', 'endpoints': '/api/v1/buttons /api/v1/state /api/v1/screen.png POST /api/v1/press POST /api/v1/click'}, HTTPStatus.NOT_FOUND)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            self._json({'error': repr(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        if n > MAX_BODY:
            raise ValueError('corpo grande demais')
        try:
            return json.loads(self.rfile.read(n) or b'{}')
        except ValueError:
            raise ValueError('corpo precisa ser JSON')

    def do_POST(self):
        path = self.path.split('?', 1)[0]
        r = self.remote
        try:
            d = self._body()
            if path == '/api/v1/press':
                n = r.press(d.get('keys') or [], int(d.get('delay_ms', 400)))
                self._json({'ok': True, 'pressed': n, 'state': r.state()})
            elif path == '/api/v1/click':
                r.click(d['x'], d['y'], bool(d.get('down', True)), bool(d.get('move')))
                self._json({'ok': True})
            else:
                self._json({'error': 'caminho desconhecido'}, HTTPStatus.NOT_FOUND)
        except (ValueError, KeyError) as e:
            self._json({'error': str(e)}, HTTPStatus.BAD_REQUEST)
        except Exception as e:
            self._json({'error': repr(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)


def make_server(remote, port=8772):
    class Bound(Handler):
        pass
    Bound.remote = remote
    return ThreadingHTTPServer(('127.0.0.1', port), Bound)


def open_runtime(env_id, envs_dir=None):
    """Runtime enxuto apontando para o ambiente: so os caminhos de entrada e do framebuffer (o ambiente precisa estar ligado)."""
    from . import runtime
    root = envs_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'environments')
    ed = os.path.join(root, env_id)
    with open(os.path.join(ed, 'env.json')) as f:
        env = json.load(f)
    rt = runtime.Runtime(ed, env)
    if not os.path.exists(os.path.join(rt.ctl, 'input.sock')):
        raise SystemExit('ambiente %s nao esta em execucao (sem %s): ligar com "python3 -m idemu gui" ou "run %s" primeiro'
                         % (env_id, os.path.join(rt.ctl, 'input.sock'), env_id))
    return rt


def main(argv):
    """python3 -m idemu remote <id> [serve|press ...|screen arquivo] [--port N]"""
    import argparse
    ap = argparse.ArgumentParser(prog='idemu remote', description='controle sem interface do ambiente em execucao')
    ap.add_argument('env')
    ap.add_argument('rest', nargs='*', help='serve | press <botoes...> | screen <arquivo>')
    ap.add_argument('--port', type=int, default=int(os.environ.get('IDEMU_REMOTE_PORT', '8772')))
    ap.add_argument('--delay', type=int, default=400)
    a = ap.parse_args(argv)
    rt = open_runtime(a.env)
    r = Remote(rt)
    rest = a.rest or ['serve']
    if rest[0] == 'press':
        print('apertados: %d' % r.press(rest[1:], a.delay))
        return 0
    if rest[0] == 'screen':
        png, seq = r.screen_png()
        if not png:
            raise SystemExit('sem quadro ainda: o renderizador ainda nao desenhou')
        with open(rest[1] if len(rest) > 1 else 'screen.png', 'wb') as f:
            f.write(png)
        print('%s (quadro %d)' % (rest[1] if len(rest) > 1 else 'screen.png', seq))
        return 0
    if rest[0] == 'bench':                          # fluxo de quadros sob carga repetível (json): python3 -m idemu remote <id> bench [segundos]
        print(json.dumps(r.bench(float(rest[1]) if len(rest) > 1 else 5.0)))
        return 0
    if rest[0] != 'serve':
        raise SystemExit('uso: remote <id> [serve|press <botoes...>|screen <arquivo>|bench [segundos]]')
    st = r.state()
    if not st['drawing']:
        print('aviso: nenhum quadro ainda (o ambiente esta ligando ou quem o ligou nao e o glhost?)')
    try:
        if socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect_ex(('127.0.0.1', 8765)) == 0:
            print('aviso: a interface web (porta 8765) esta aberta neste ambiente — entrada pelos dois lados ao mesmo tempo se mistura')
    except OSError:
        pass
    srv = make_server(r, a.port)
    print('IDEmu remote: http://127.0.0.1:%d/  (Ctrl+C encerra)' % a.port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0
