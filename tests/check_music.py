import ast
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('player', ROOT / 'computer/play.py')
player = importlib.util.module_from_spec(spec)
spec.loader.exec_module(player)
source = ast.parse((ROOT / 'legacy/passing_lights.py').read_text())
source.body = [node for node in source.body if not
               (isinstance(node, ast.ImportFrom) and node.module in ('galactic', 'picographics'))]
board = {'__name__': 'test_board'}
exec(compile(source, 'board/main.py', 'exec'), board)


class MusicTests(unittest.TestCase):

    def test_sender_backpressure_and_recovery(self):
        import serial
        class Port:
            def __init__(self):
                self.incoming = b''
                self.sent = []
                self.timeout_next = False
            @property
            def in_waiting(self):
                return len(self.incoming)
            def read(self, count):
                result, self.incoming = self.incoming[:count], self.incoming[count:]
                return result
            def write(self, payload):
                self.sent.append(payload)
                if self.timeout_next:
                    self.timeout_next = False
                    raise serial.SerialTimeoutException('simulated congestion')
                return len(payload)
            def reset_output_buffer(self):
                pass
        port = Port()
        link = player.CueLink(port)
        link.tick([1,2,3,4], 0)
        for i in range(1,40):
            link.tick([5,6,7,8], i/40)
        self.assertEqual(len(port.sent), 1)  # never queue behind a busy board
        port.incoming = b'CASSETTE_'
        link.tick([5,6,7,8], 1)
        self.assertEqual(len(port.sent), 1)
        port.incoming = b'READY_V2\n'
        link.tick([5,6,7,8], 1.1)
        self.assertIn(b'L 5 6 7 8', port.sent[-1])
        port.incoming = b'CASSETTE_READY_V2\n'
        port.timeout_next = True
        link.tick([9,9,9,9], 1.2)  # timeout must not interrupt audio loop
        self.assertFalse(link.disabled)
        count = len(port.sent)
        link.tick([9,9,9,9], 1.3)
        self.assertEqual(len(port.sent), count)
        link.tick([9,9,9,9], 3.3)
        self.assertEqual(port.sent[-1], b'\nHELLO\n')
        port.incoming = b'CASSETTE_READY_V2\n'
        link.tick([10,10,10,10], 3.4)
        self.assertFalse(link.disabled)
        self.assertIn(b'L 10 10 10 10', port.sent[-1])

    def test_complete_track(self):
        data = json.loads((ROOT / 'computer/envelopes.json').read_text())
        with wave.open(str(ROOT / 'computer/song.wav'), 'rb') as wav:
            self.assertEqual(wav.getnchannels(), 2)
            self.assertAlmostEqual(wav.getnframes() / wav.getframerate(), data['duration'], places=3)
        self.assertLess(abs(len(data['frames']) / data['fps'] - data['duration']), 1/data['fps'])
        for i, row in enumerate(data['frames']):
            self.assertEqual(len(row), 4)
            self.assertTrue(all(isinstance(x, int) and 0 <= x <= 255 for x in row))
            values = player.frame_at(data, (i + 0.5) / data['fps'])
            packet = player.packet(values)
            self.assertLess(len(packet), 64)
        self.assertEqual(player.frame_at(data, -1), [0]*7)
        self.assertEqual(player.frame_at(data, data['duration']), [0]*7)
        self.assertGreater(len({tuple(row) for row in data['frames']}), 100)

    def test_receiver_and_timeout(self):
        ticks = [0]
        stream = io.StringIO('L 255 128 64 0\n')
        class Poll:
            def register(self, *args):
                pass
            def poll(self, timeout):
                return [1] if stream.tell() < len(stream.getvalue()) else []
        board['select'] = SimpleNamespace(poll=Poll, POLLIN=1)
        board['sys'] = SimpleNamespace(stdin=stream)
        board['time'] = SimpleNamespace(ticks_ms=lambda: ticks[0], ticks_diff=lambda a,b: a-b)
        receiver = board['USBInput']()
        values = receiver.sample(0)
        self.assertEqual(values.bass, 1)
        self.assertAlmostEqual(values.mid, 128/255)
        for malformed in ('L nope 0 0 0', 'L 999 0 0 0', 'L 0', 'garbage'):
            receiver.receive_line(malformed)
            self.assertEqual(values.bass, 1)
        ticks[0] = 1001
        self.assertEqual(receiver.sample(1.001).bass, 0)

    def test_drum_impulses_move_orbs_immediately(self):
        still, kick, snare = board['Scene'](), board['Scene'](), board['Scene']()
        base, bass_hit, snare_hit = board['Levels'](), board['Levels'](), board['Levels']()
        base.set(.5,.5,.2,.6)
        bass_hit.set(.5,.5,.2,.6,drum=1)
        snare_hit.set(.5,.5,.2,.6,snare=1)
        still.update(.025,base)
        kick.update(.025,bass_hit)
        snare.update(.025,snare_hit)
        self.assertGreater(kick.positions[0][0],still.positions[0][0])
        self.assertGreater(snare.positions[0][1],still.positions[0][1])
        self.assertGreater(kick.radii[0],still.radii[0])

    def test_music_breathing_and_silence(self):
        scene, levels = board['Scene'](), board['Levels']()
        levels.set(.9,.8,.3,.9)
        for _ in range(80): scene.update(.025,levels)
        big = scene.radii[0]
        bright = sum(scene.canvas.history)
        levels.set(0,0,0,0)
        for _ in range(200): scene.update(.025,levels)
        self.assertLess(scene.radii[0],big*.5)
        self.assertLess(sum(scene.canvas.history),bright*.1)

    def test_fractional_glow_is_continuous(self):
        scene=board['Scene']()
        scene.canvas.begin()
        scene.field(20.49,5.0,1.5,(100,0,0),1)
        before=list(scene.canvas.light)
        scene.canvas.begin()
        scene.field(20.51,5.0,1.5,(100,0,0),1)
        after=list(scene.canvas.light)
        self.assertLess(max(abs(a-b) for a,b in zip(before,after)),2)
        self.assertGreater(sum(after),0)

    def test_percussion_cue_timestamps(self):
        data={'duration':2,'fps':1,'version':2,'frames':[[0]*4,[0]*4],
              'hits':[[],[[1.0,255]],[]]}
        self.assertEqual(player.frame_at(data,.99)[5],0)
        self.assertEqual(player.frame_at(data,1.0)[5],255)
        self.assertEqual(player.frame_at(data,1.13)[5],0)

    def test_timing_direction_and_controls(self):
        self.assertEqual(player.adjusted_offset(120,'+'),145)
        self.assertEqual(player.adjusted_offset(120,'-'),95)
        self.assertEqual(player.adjusted_offset(120,'0'),0)
        with self.assertRaises(ValueError): player.adjusted_offset(0,'nan')
        data={'duration':2,'fps':1,'version':2,
              'frames':[[0]*4,[0]*4],'hits':[[],[[1.0,255]],[]]}
        self.assertEqual(player.frame_at(data,.88)[5],0)
        self.assertEqual(player.frame_at(data,.88+.120)[5],255)

    def test_music_scene(self):
        data = json.loads((ROOT / 'computer/envelopes.json').read_text())
        scene, levels = board['Scene'](), board['Levels']()
        crossed=False
        for frame in range(1600):
            values=player.frame_at(data,frame/40)
            levels.set(*(v/255 for v in values))
            canvas=scene.update(.025,levels)
            crossed |= scene.positions[0][0] > scene.positions[1][0]
            for x,y in scene.positions:
                self.assertTrue(0<=x<53 and 0<=y<11)
        self.assertTrue(crossed)
        pixels=[canvas.rgb(i) for i in range(583)]
        self.assertTrue(all(0<=v<=255 for rgb in pixels for v in rgb))
        self.assertLess(sum(max(rgb)>30 for rgb in pixels),220)



if __name__ == '__main__':
    unittest.main()
