# -*- coding: utf-8 -*-
"""Plugin carplay-touch: the pad events mirrored as screen touches, its gates, the video rect from the
renderer log, and the typed buffer (hook.py wraps Runtime.touchpad; docs/TOUCH_CONTROLLER.md, docs/CARPLAY.md)."""
import os, socket, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from idemu import plugins, runtime                                                    # noqa: E402

PKG = os.path.join(plugins.DROP or '', 'carplay-touch')                # plugins/ lives in the idplugins project
CP_TC = b'\x03\x00\xff\x01\xbf\x00\x00\x00'    # CccsTouchControl gesture-only: CCarPlayActivity holds the pad
SPELLER_TC = b'\x03\x0f\x02\x00\x00\x00\x00\x01'   # character classes: one of the HMI's spellers holds it


class Rt(object):
    """Stub head unit: records the screen touches the mirror injects; CarPlay connected, gesture mode by default."""
    kind = None
    state = 'running'
    env = {'display': '6_5_800x480'}
    _n = 0

    def __init__(self, logd, ctl, tc=CP_TC):
        self.id, self.logd, self.ctl = 'test-%d' % Rt._n, logd, ctl
        Rt._n += 1
        self.touched, self.sent = [], []
        self.fake_iphone = type('F', (), {'state': 'connected'})()
        self.v850 = type('V', (), {'bridge': type('B', (), {'ccs_touch_control': tc})})()

    def touch(self, x, y, down, move=False): self.touched.append((x, y, down, move))
    def send_cmd(self, line): self.sent.append(line)


class CarplayTouchTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        logd = os.path.join(tmp.name, 'logs'); ctl = os.path.join(tmp.name, 'ctl')
        os.makedirs(logd); os.makedirs(ctl)
        with open(os.path.join(logd, 'renderer.log'), 'w') as f:
            f.write('[map] camada visivel 0,0 800x480\n[video] camada visivel 160,0 640x480\n')
        self.vk = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.vk.bind(os.path.join(ctl, 'input.sock')); self.vk.settimeout(0.3)
        self.addCleanup(self.vk.close)
        self.rt = Rt(logd, ctl)
        app = type('A', (), {'rt': self.rt, 'need_rt': lambda s: s.rt})()
        self.hook = plugins._import_py('carplay-touch', PKG, 'hook.py', app)   # register() wraps Runtime.touchpad
        self.addCleanup(self.hook.CONFIG.update, {'mode': 'cursor', 'gain': 640, 'always': False})

    def _drain(self):
        out = []
        while True:
            try: out.append(self.vk.recv(200).decode())
            except socket.timeout: return out

    # ---- gates ----
    def test_pad_state(self):
        h = self.hook
        self.assertEqual(h.pad_state(self.rt), 'carplay')
        self.rt.v850.bridge.ccs_touch_control = SPELLER_TC
        self.assertEqual(h.pad_state(self.rt), 'speller')
        self.rt.v850.bridge.ccs_touch_control = None
        self.assertEqual(h.pad_state(self.rt), 'off')
        self.assertFalse(h.gate_open(self.rt, 'off'))
        self.assertTrue(h.gate_open(self.rt, 'carplay'))

    def test_no_mirror_in_speller_or_without_always(self):
        h = self.hook
        self.rt.v850.bridge.ccs_touch_control = SPELLER_TC
        h.mirror(self.rt, 0.5, 0.5, True); h.mirror(self.rt, 0.6, 0.5, True, True); h.mirror(self.rt, 0.6, 0.5, False)
        self.rt.v850.bridge.ccs_touch_control = None
        h.mirror(self.rt, 0.5, 0.5, True); h.mirror(self.rt, 0.5, 0.5, False)
        self.assertEqual(self.rt.touched, [])
        h.CONFIG['always'] = True                                # outside CarPlay: only the speller keeps the pad
        h.mirror(self.rt, 0.5, 0.5, True); h.mirror(self.rt, 0.5, 0.5, False)
        self.assertEqual(len(self.rt.touched), 2)

    # ---- cursor mirror ----
    def test_cursor_press_drag_tap(self):
        h = self.hook
        h.mirror(self.rt, 0.5, 0.5, True)                        # press: cursor centers on the video area, no jump
        self.assertEqual(self.rt.touched[-1], (479, 239, True, False))
        h.mirror(self.rt, 0.6, 0.5, True, move=True)             # drag: +0.1 pad * 640 px = +64 px
        self.assertEqual(self.rt.touched[-1], (543, 239, True, True))
        h.mirror(self.rt, 0.6, 0.5, False)                       # lift: release at the cursor
        self.assertEqual(self.rt.touched[-1], (543, 239, False, False))

    def test_cursor_clamped_to_video(self):
        h = self.hook
        h.mirror(self.rt, 0.5, 0.5, True)
        for i in range(40):                                      # far right strokes stop at the video edge
            h.mirror(self.rt, 0.5 + i * 0.05, 0.5, True, move=True)
        self.assertEqual(self.rt.touched[-1], (799, 239, True, True))

    def test_two_fingers_release_the_mirror_touch(self):
        h = self.hook
        h.mirror(self.rt, 0.5, 0.5, True)
        h.mirror(self.rt, 0.52, 0.5, True, True, x2=0.48, y2=0.5)   # pinch starts: the cursor finger lets go
        self.assertEqual(self.rt.touched[-1], (479, 239, False, False))
        h.mirror(self.rt, 0.55, 0.5, True, True, x2=0.45, y2=0.5)
        h.mirror(self.rt, 0.55, 0.5, False, x2=0.45, y2=0.5)        # and no more touches until the next stroke
        self.assertEqual(len(self.rt.touched), 2)

    def test_gate_close_midstroke(self):
        h = self.hook
        h.mirror(self.rt, 0.5, 0.5, True)
        self.rt.v850.bridge.ccs_touch_control = None              # CarPlay loses the screen mid-drag
        h.mirror(self.rt, 0.6, 0.5, True, move=True)
        self.assertEqual(self.rt.touched[-1], (479, 239, False, False))

    # ---- video rect, display, recenter ----
    def test_video_rect_and_display(self):
        h = self.hook
        self.assertEqual(h.video_rect(self.rt), {'x': 160, 'y': 0, 'w': 640, 'h': 480})
        self.assertEqual(h.display_size(self.rt), (800, 480))
        self.assertEqual(h.recenter(self.rt), (479, 239))
        with open(os.path.join(self.rt.logd, 'renderer.log'), 'a') as f:
            f.write('[video] camada oculta 160,0 640x480\n')
        self.assertIsNone(h.video_rect(self.rt))                  # CarPlay gone: cursor clamps to the display
        self.assertEqual(h.cursor_bounds(self.rt), (0, 0, 799, 479))

    # ---- typed buffer and the video keystroke line ----
    def test_type_and_typed_routes(self):
        h = self.hook
        st = h.handle_api('POST', 'cptouch/type', {'text': 'MA'})
        self.assertEqual(st['typed'], 'MA')
        self.assertTrue(any(l.startswith('V k type') and 'MA' in l for l in self._drain()))
        st = h.handle_api('POST', 'cptouch/typed', {'action': 'back'})
        self.assertEqual(st['typed'], 'M')
        st = h.handle_api('POST', 'cptouch/typed', {'action': 'clear'})
        self.assertEqual(st['typed'], '')
        with self.assertRaises(Exception):
            h.handle_api('POST', 'cptouch/type', {})

    def test_config_and_state_routes(self):
        h = self.hook
        st = h.handle_api('POST', 'cptouch/config', {'mode': 'typing', 'gain': 3000, 'always': True})
        self.assertEqual((st['mode'], st['gain'], st['always']), ('typing', 2400, True))
        with self.assertRaises(Exception):
            h.handle_api('POST', 'cptouch/config', {'mode': 'swipe'})
        st = h.handle_api('GET', 'cptouch/state', {})
        for k in ('running', 'carplay', 'pad', 'gate', 'cursor', 'video', 'display', 'typed', 'recognizer'):
            self.assertIn(k, st)
        self.assertEqual(st['carplay'], 'connected')

    # ---- the wrapper on Runtime.touchpad: the original path and the mirror both run ----
    def test_touchpad_wrapper(self):
        runtime.Runtime.touchpad(self.rt, 0.5, 0.5, True)
        runtime.Runtime.touchpad(self.rt, 0.5, 0.5, False)
        self.assertEqual(len(self.rt.sent), 2)                    # events 41 still reach the shim
        self.assertTrue(self.rt.sent[0].startswith('41 1 '))
        self.assertEqual(self.rt.touched, [(479, 239, True, False), (479, 239, False, False)])

    # ---- typing mode: no screen touches, the recognizer is asked after the pause ----
    def test_typing_mode_does_not_touch(self):
        h = self.hook
        h.CONFIG['mode'] = 'typing'
        h.mirror(self.rt, 0.2, 0.3, True); h.mirror(self.rt, 0.3, 0.4, True, True); h.mirror(self.rt, 0.3, 0.4, False)
        self.assertEqual(self.rt.touched, [])
        if h.STATE['timer']: h.STATE['timer'].cancel()            # the recognizer may not exist here: stop the timer


if __name__ == '__main__':
    unittest.main()
