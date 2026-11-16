# -*- coding: utf-8 -*-
"""Plugin android-auto: codec/frame layers and a full loopback session against the demo phone
(the same code path the "Demo phone" button uses: TLS, discovery, channels, video decode via
ffmpeg, media acks, sensors, input events, bye-bye)."""
import os
import shutil
import socket
import sys
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from idemu import plugins as _pl                                            # noqa: E402  (shim: localiza o idplugins)

_PLUGIN = os.path.join(_pl.DROP or '', 'android-auto')                      # plugins/ vive no projeto idplugins
_HAS = bool(_pl.DROP) and os.path.isdir(_PLUGIN)
if _HAS:
    sys.path.insert(0, _PLUGIN)
    from aa_core import aoap, frames, manifest, pb, session as sessionmod, sim, tls as tlsmod  # noqa: E402
    from aa_core import transport as transportmod                                                # noqa: E402

skip = unittest.skipUnless(_HAS, 'android-auto plugin not installed (plugins/android-auto)')


@skip
class PbTest(unittest.TestCase):
    def test_varints(self):
        self.assertEqual(pb.vint(0), b'\x00')
        self.assertEqual(pb.vint(300), b'\xac\x02')
        self.assertEqual(pb.svint(-1), b'\xff' * 9 + b'\x01')       # int32 -1 sign-extends to 64 bits

    def test_roundtrip(self):
        raw = (pb.Out().v(1, 6).packed(1, [19, 20, 65536]).s(2, -123456).str(3, 'iPhone')
               .str(4, pb.Out().v(1, 7).flag(2, True).bytes()).bytes())
        m = pb.parse(raw)
        self.assertEqual(pb.gi(m, 1), 6)                            # first of the repeated
        self.assertEqual(pb.gpacked(m, 1), [6, 19, 20, 65536])
        self.assertEqual(pb.gi(m, 2), -123456)
        self.assertEqual(pb.gs(m, 3), 'iPhone')
        self.assertEqual(pb.gi(pb.gsubs(m, 4)[0], 1), 7)
        self.assertTrue(pb.gb(pb.gsubs(m, 4)[0], 2))

    def test_unknown_fields_survive(self):
        raw = pb.Out().v(99, 1).str(100, b'\x01\x02').bytes()
        m = pb.parse(raw)
        self.assertEqual(pb.gi(m, 99), 1)
        self.assertEqual(pb.g(m, 100), b'\x01\x02')


@skip
class FrameTest(unittest.TestCase):
    def test_build_read(self):
        r = frames.FrameReader()
        wire = frames.build(0, frames.BULK, b'\x00\x01abc') + frames.build(6, frames.BULK | frames.ENC, b'x' * 100)
        got = []
        for i in range(len(wire)):                                  # byte-at-a-time: nothing lost
            got += r.feed(wire[i:i + 1])
        self.assertEqual(got, [(0, frames.BULK, b'\x00\x01abc'), (6, frames.BULK | frames.ENC, b'x' * 100)])

    def test_fragmentation(self):
        fr = frames.Reassembler()
        self.assertIsNone(fr.add(6, frames.FIRST | frames.ENC, b'aaa')[0])
        self.assertIsNone(fr.add(6, frames.MIDDLE | frames.ENC, b'bbb')[0])
        msg, flags = fr.add(6, frames.LAST | frames.ENC, b'ccc')
        self.assertEqual(msg, b'aaabbbccc')
        self.assertTrue(flags & frames.ENC)
        msg, _ = fr.add(6, frames.BULK, b'solo')
        self.assertEqual(msg, b'solo')


@skip
class ManifestTest(unittest.TestCase):
    def setUp(self):
        self.m = pb.parse(manifest.build(resolution=2))

    def test_required_channels_present(self):
        chans = {pb.gi(c, 1) for c in pb.gsubs(self.m, 1)}
        for cid in (1, 6, 7, 8, 9, 14):                             # sensor/video/input/audio/mic
            self.assertIn(cid, chans)

    def test_video_and_touch(self):
        for c in pb.gsubs(self.m, 1):
            if pb.gi(c, 1) == 6:
                vc = pb.gsubs(pb.gsubs(c, 3)[0], 4)[0]
                self.assertEqual(pb.gi(vc, 1), 2)                   # 1280x720
                self.assertEqual(pb.gi(vc, 10), 3)                  # H.264
            if pb.gi(c, 1) == 7:
                src = pb.gsubs(c, 4)[0]
                self.assertIn(65536, pb.gpacked(src, 1))            # rotary advertised
                ts = pb.gsubs(src, 2)[0]
                self.assertEqual((pb.gi(ts, 1), pb.gi(ts, 2)), (1280, 720))

    def test_identity_fields(self):
        self.assertEqual(pb.gs(self.m, 2), 'BMW')
        self.assertEqual(pb.gs(pb.gsubs(self.m, 17)[0], 6), 'iDrive head unit (emulated)')
        self.assertEqual(pb.gi(pb.gsubs(pb.gsubs(self.m, 16)[0], 1)[0], 1), 3000)


@skip
class AoapTest(unittest.TestCase):
    def test_handshake_requests(self):
        reqs = aoap.aoap_requests('SER1')
        self.assertEqual(reqs[0][:2], (aoap.BMREQ_IN, aoap.AOA_GET_PROTOCOL))
        strings = [r for r in reqs if r[1] == aoap.AOA_SEND_STRING]
        self.assertEqual([r[3] for r in strings], [0, 1, 2, 3, 4, 5])
        self.assertEqual(strings[0][4], b'Android\x00')
        self.assertEqual(strings[-1][4], b'SER1\x00')
        self.assertEqual(reqs[-1][1], aoap.AOA_START)

    def test_frame_len(self):
        self.assertEqual(aoap.frame_len(frames.build(0, frames.BULK, b'12345')[:4]), 9)
        self.assertEqual(aoap.frame_len(frames.build(0, frames.FIRST, b'12345')[:4]), 13)


@skip
class SensorEncodingTest(unittest.TestCase):
    def test_encodings(self):
        from aa_core import sensors
        v = sensors.snapshot(None, {'night': False, 'driving_status': 0})
        self.assertEqual(v['gear'], 101)                            # no car: P, brake on
        f, b = sensors.event_bytes(manifest.SENSOR['CAR_SPEED'], {'speed_kmh': 50.0})
        self.assertEqual((f, b), (3, pb.Out().v(1, 13889).bytes()))  # 50 km/h -> 13.889 m/s *1000
        f, b = sensors.event_bytes(manifest.SENSOR['LOCATION'],
                                   dict(v, fix=True, lat=-23.55, lon=-46.63, alt=760.0,
                                        speed_kmh=0.0, heading=90.0, hdop=0.9))
        loc = pb.parse(b)
        self.assertEqual(pb.gi(loc, 2), -235500000)
        self.assertEqual(pb.gi(loc, 7), 90000000)
        self.assertIsNone(sensors.event_bytes(manifest.SENSOR['LOCATION'], dict(v, fix=False)))


class _Log(list):
    """List of log lines that is also callable as the log callback."""

    def __call__(self, m):
        self.append(str(m))


class _Stub(object):
    """Feed stand-in capturing what the session reports."""

    def __init__(self):
        self.log = _Log()
        self.status = {}
        self.closed = None
        self.media = []
        self.sensors = []
        from aa_core.media import Audio, Video
        self.video, self.audio = Video(self.log), Audio(self.log)

    def on_status(self, **kw):
        self.status.update(kw)

    def on_close(self, reason):
        self.closed = reason

    def on_media_status(self, d):
        self.media.append(d)

    def on_nav(self, d):
        pass

    def on_voice(self, t):
        pass

    def on_video_focus(self, p):
        pass

    def on_sensor_start(self, t):
        self.sensors.append(t)


@skip
@unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg needed for the session test')
class SessionLoopbackTest(unittest.TestCase):
    """Demo phone <-> real Session over a loopback socket, no manager and no fixed ports."""

    def setUp(self):
        self.feed = _Stub()
        self.ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ls.bind(('127.0.0.1', 0))
        self.ls.listen(1)
        self.session = None
        self.stop = threading.Event()
        threading.Thread(target=self._accept, daemon=True).start()

    def tearDown(self):
        self.stop.set()
        if self.session:
            self.session.close('test end')
        try:
            self.ls.close()
        except OSError:
            pass

    def _accept(self):
        c, _ = self.ls.accept()
        opts = {'tls_ctx': tlsmod.client_ctx(), 'identity': None, 'driver_position': 0, 'resolution': 2}
        s = sessionmod.Session(sessionmod.Transport(c, self.feed.log), opts, self.feed)
        self.session = s
        threading.Thread(target=transportmod.pump, args=(c, s, self.stop), daemon=True).start()
        s.start()

    def _wait(self, what, fn, timeout=25.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.session and fn():
                return True
            time.sleep(0.15)
        self.fail('timeout waiting for %s (log: %s)' % (what, ' | '.join(self.feed.log[-12:])))

    def test_full_session(self):
        port = self.ls.getsockname()[1]
        phone = sim.start('127.0.0.1', port, log=self.feed.log, seconds=0)
        self.addCleanup(lambda: (phone.stop_ev.set(), phone.join(5)))
        self._wait('session accepted', lambda: self.session)
        self._wait('tls + auth', lambda: any('TLS up' in l for l in self.feed.log))
        self._wait('input bound', lambda: any('input bound' in l for l in self.feed.log), 25)
        self._wait('video decoded', lambda: self.feed.video.stats()['frames'] > 2, 30)
        self._wait('media acks', lambda: self.session.stats['ack'] > 2)
        self._wait('sensors started', lambda: 3 in self.session.sensors_started)
        from aa_core import sensors
        threading.Thread(target=sensors.run, args=(self.session, lambda: None,
                         {'night': False, 'driving_status': 0}, self.stop), daemon=True).start()
        self._wait('sensor events sent', lambda: phone.stats['sensors'] > 0, 15)
        self._wait('media status parsed', lambda: any(d.get('state') == 2 for d in self.feed.media))
        self._wait('phone saw video', lambda: phone.stats['video'] > 0)
        self._wait('phone saw audio', lambda: phone.stats['acks'] > 0)

        self.assertTrue(self.session.send_key(23, True))
        self.session.send_key(23, False)
        self.assertTrue(self.session.send_touch(0, 0, [(640, 360, 0)]))
        self.session.send_touch(2, 0, [(640, 300, 0)])
        self.session.send_touch(1, 0, [(640, 300, 0)])
        self.assertTrue(self.session.send_rotary(12))
        self._wait('phone saw input', lambda: phone.stats['inputs'] >= 4, 10)

        jpeg = self.feed.video.wait(self.feed.video.seq, timeout=5)
        self.assertTrue(jpeg and jpeg[1][:2] == b'\xff\xd8')

        phone.stop_ev.set()
        self._wait('bye-bye', lambda: self.session.state == 'closed', 10)


if __name__ == '__main__':
    unittest.main()
