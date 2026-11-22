"""Controle sem interface (idemu/hmihead.py): nomes de botões, validações e o servidor HTTP com um Runtime falso.
Sem emulador: o Remote recebe um stub que grava os comandos; o HTTP é testado de ponta a ponta em porta efêmera."""
import json
import os
import sys
import threading
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from idemu import hmihead  # noqa: E402


class FakeRT:
    def __init__(self):
        self.cmds = []
        self.t0 = 1000.0
        self.state = 'running'

    def key(self, code, val): self.cmds.append(('key', code, val))
    def rotor(self, delta): self.cmds.append(('rotor', delta))
    def touch(self, x, y, down, move=False): self.cmds.append(('touch', x, y, down, move))
    def frame_seq(self): return 42
    def screen_png(self): return b'\x89PNG-fake', 42


class ButtonsTest(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(hmihead._resolve('OK'), ('key', 8))
        self.assertEqual(hmihead._resolve('enter'), ('key', 8))
        self.assertEqual(hmihead._resolve('cw'), ('rotor', 1))
        self.assertEqual(hmihead._resolve('ccw'), ('rotor', -1))
        self.assertEqual(hmihead._resolve('RADIO'), ('key', 4))

    def test_desconhecido_valida_antes_de_apertar(self):
        rt = FakeRT()
        r = hmihead.Remote(rt)
        with self.assertRaises(ValueError):
            r.press(['menu', 'nao-existe'])
        self.assertEqual(rt.cmds, [])                      # nada foi enviado: a validacao veio antes

    def test_sequencia_press_release_e_pulso_de_inclinacao(self):
        rt = FakeRT()
        hmihead.Remote(rt).press(['push', 'up', 'next'], delay_ms=0, hold_ms=0)
        self.assertEqual(rt.cmds, [('key', 8, 1), ('key', 8, 0), ('key', 9, 1), ('key', 9, 0), ('rotor', 1)])


class HttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rt = FakeRT()
        cls.srv = hmihead.make_server(hmihead.Remote(cls.rt), port=0)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close()

    def get(self, path):
        with urllib.request.urlopen('http://127.0.0.1:%d%s' % (self.port, path), timeout=5) as r:
            return r.status, r.read()

    def post(self, path, body):
        req = urllib.request.Request('http://127.0.0.1:%d%s' % (self.port, path), json.dumps(body).encode(),
                                     {'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_buttons_e_state(self):
        s, b = self.get('/api/v1/buttons')
        self.assertEqual(s, 200)
        self.assertIn('push', json.loads(b)['buttons'])
        st, body = self.get('/api/v1/state')
        self.assertEqual(json.loads(body)['seq'], 42)

    def test_screen_png(self):
        s, b = self.get('/api/v1/screen.png')
        self.assertEqual((s, b), (200, b'\x89PNG-fake'))

    def test_press_pelo_http(self):
        s, j = self.post('/api/v1/press', {'keys': ['menu', 'next'], 'delay_ms': 0})
        self.assertEqual((s, j['pressed']), (200, 2))
        self.assertIn(('key', 1, 1), self.rt.cmds)
        self.assertIn(('rotor', 1), self.rt.cmds)

    def test_erro_de_botao_devolve_400(self):
        s, j = self.post('/api/v1/press', {'keys': ['teleporte']})
        self.assertEqual(s, 400)
        self.assertIn('desconhecido', j['error'])

    def test_click(self):
        s, j = self.post('/api/v1/click', {'x': 100, 'y': 50, 'down': True})
        self.assertEqual(s, 200)
        self.assertIn(('touch', 100.0, 50.0, True, False), self.rt.cmds)

    def test_pagina(self):
        s, b = self.get('/')
        self.assertEqual(s, 200)
        self.assertIn(b'IDEmu remote', b)


if __name__ == '__main__':
    unittest.main()
