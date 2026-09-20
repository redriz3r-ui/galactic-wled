"""Host integration tests; no board libraries or third-party packages required."""
import contextlib
import io
import json
import os
from pathlib import Path
import random
import socket
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'board'))
from audio import Audio,USBInput
from engine import Engine
from effects import NAMES,resolve
from palettes import Palette,PALETTES
from presets import Store,DEFAULTS,SHOWCASE
from compositor import Canvas,composite,ZONES
from api import API
from controls import Controls
from web import Server,WiFi
import config

class PlatformTests(unittest.TestCase):
 def setUp(self):
  random.seed(42)
  self.temp=tempfile.TemporaryDirectory()
  self.e=Engine(Store(self.temp.name+'/settings.json'))
  self.api=API(self.e)
 def tearDown(self): self.temp.cleanup()
 def post(self,path,value): return self.api.handle('POST','/api/'+path,json.dumps(value).encode())
 def test_effects_and_palettes(self):
  for name in NAMES:
   self.assertTrue(callable(resolve(name)))
   self.e.apply({'effect':name,'layers':[]},0)
   for i in range(30):
    self.e.audio.push([.9,.4,.7,.8,int(i%10==0),0,.5])
    result=self.e.step(.04)
   self.assertEqual(len(result),1749)
   self.assertIsNone(self.e.error,name)
   self.assertGreater(sum(result),0,name)
  for name in PALETTES:
   p=Palette(name);p.update(self.e.audio)
   self.assertEqual(len(p.colors),64)
   self.assertTrue(all(0<=v<=255 for color in p.colors for v in color))
 def test_presets_reset_and_playlist(self):
  for p in DEFAULTS:
   self.e.apply_preset(p['name'],0);self.e.step(.04)
   self.assertEqual(self.e.contexts[0].spec['effect'],p['effect'])
  self.e.apply({'params':{'density':1}})
  self.e.apply_preset('Ambient')
  self.assertEqual(self.e.contexts[0].params['density'],.4)
  self.e.set_playlist({'items':[{'preset':'Ambient','duration':1},{'preset':'Fire','duration':1}],'loop':False})
  for _ in range(26): self.e.step(.04)
  self.assertEqual(self.e.active_preset,'Fire')
  for _ in range(26): self.e.step(.04)
  self.assertFalse(self.e.playlist_running)
  self.e.set_playlist({'items':[{'preset':'Ambient','duration':1}],'loop':True})
  for _ in range(26): self.e.step(.04)
  self.assertTrue(self.e.playlist_running)
 def test_usb_protocol_and_overflow(self):
  stream=io.StringIO('L 255 128 64 200 255 0 100\nHELLO\n'+'X'*250+'L 0 0 0 0\n')
  class Poll:
   def register(self,*a): return
   def poll(self,*a): return [1] if stream.tell()<len(stream.getvalue()) else []
  a=Audio();receiver=USBInput(a,stream,Poll())
  with contextlib.redirect_stdout(io.StringIO()) as output:
   for _ in range(3): receiver.poll_once()
  self.assertIn('CASSETTE_READY_V2',output.getvalue())
  self.assertEqual(a.raw[0],1)
  for bad in ('L -1 0 0 0','L 999 0 0 0','L nan 0 0 0','L 0','x'):
   receiver.receive_line(bad);self.assertEqual(a.raw[0],1)
  receiver.receive_line('B '+' '.join(['255']*8));self.assertEqual(a.raw_bands,[1]*16)
  receiver.receive_line('W '+' '.join(['0']*53));self.assertEqual(a.waveform,[-1]*53)
 def test_audio_timeout_and_transients(self):
  a=Audio()
  with patch('audio.ticks_ms',return_value=0):
   a.push([1,.7,.3,.8,1,0,0]);a.update(.04)
   self.assertGreater(a.beat,0)
   for _ in range(20): a.push([1,.7,.3,.8,1,0,0]);a.update(.04)
   self.assertEqual(a.beat,0)  # a sustained channel is not a new transient
  with patch('audio.ticks_ms',return_value=2000):
   for _ in range(80): a.update(.04)
   self.assertFalse(a.connected);self.assertLess(a.level,.001)
   self.assertEqual(a.drum,0)
 def test_api_atomic_validation(self):
  before=self.e.state(True)
  for value in ({'brightness':2},{'effect':'missing'},{'palette':'missing'},{'speed':float('nan')},
                {'audio_reactive':1},{'layers':[{}, {}, {}]},{'params':[]},{'layers':[{'zone':'bad'}]},
                {'layers':[{'effect':'passing_lights'}]},{'brightness':.2,'params':{'speed':-1}},
                {'layers':[{'effect':[]}]}):
   status,_=self.post('state',value);self.assertEqual(status,400,value)
   self.assertEqual(self.e.state(True),before)
  self.assertEqual(self.post('state',{'effect':'cassette','speed':.8})[0],200)
  self.assertEqual(self.e.contexts[0].params['speed'],.8)
  self.assertEqual(self.post('audio',{'levels':[.1,.2,.3,.4],'bands':[.6]*16})[0],200)
  self.assertEqual(self.post('audio/config',{'gain':2,'gate':.1,'agc':True})[0],200)
  self.assertEqual(self.e.audio.gain,2)
 def test_zones_and_blend_kernels(self):
  for mode,expected in [('replace',200),('add',255),('lighten',200),('alpha',200),('screen',222)]:
   out=Canvas();out.data[:]=bytes([100])*1749
   src=Canvas(26,11);src.data[:]=bytes([200])*len(src.data)
   composite(out,src,ZONES['left'],mode,1)
   self.assertAlmostEqual(out.data[0],expected,delta=1)
   self.assertEqual(out.data[26*3],100)
  out=Canvas();src=Canvas();src.pixel(-1,0,(255,255,255));self.assertEqual(sum(src.data),0)
  src.pixel(0,0,(200,0,0));composite(out,src,ZONES['full'],'alpha',.5);self.assertEqual(out.data[0],100)
 def test_transition_and_power(self):
  for _ in range(30): self.e.step(.04)
  before=bytes(self.e.display)
  self.e.apply({'effect':'fire','layers':[]},1)
  self.assertEqual(bytes(self.e.previous),before)
  self.e.step(.04)
  self.assertLess(max(abs(a-b) for a,b in zip(before,self.e.display)),12)
  self.e.apply({'power':False});self.assertEqual(sum(self.e.step(.04)),0)
 def test_save_restore(self):
  self.e.apply({'effect':'cassette','brightness':.32,'params':{'speed':.8}},0)
  self.e.save('My mix')
  restored=Engine(Store(self.e.store.path))
  self.assertEqual(restored.state(True),self.e.state(True))
  restored.apply_preset('My mix');self.assertEqual(restored.brightness,.32)
  self.assertEqual(self.post('save',{})[0],400)
  Path(self.e.store.path).write_text('{broken')
  fresh=Engine(Store(self.e.store.path));self.assertEqual(fresh.active_preset,'Moody R&B')
 def test_external_frames(self):
  with patch('engine.ticks_ms',return_value=0): self.e.frame(bytes([30])*1749)
  with patch('engine.ticks_ms',return_value=10): self.e.step(.04)
  self.assertEqual(self.e.display,bytearray([30])*1749)
  with patch('engine.ticks_ms',return_value=1100): self.e.step(.04)
  self.assertIsNone(self.e.external_at)
  self.assertEqual(self.api.handle('POST','/api/frame',b'x')[0],400)
 def test_offline_and_effect_recovery(self):
  wifi=WiFi(self.e);wifi.poll();self.assertIsNone(wifi.wlan)
  def broken(ctx): raise RuntimeError('test fault')
  self.e.contexts[0].render=broken
  self.e.step(.04);self.e.step(.04)
  self.assertIn('test fault',self.e.error)
  self.assertGreater(sum(self.e.display),0)
 def test_button_debounce(self):
  class Device:
   SWITCH_A=0
   pressed=False
   def is_pressed(self,pin): return self.pressed
  d=Device()
  with patch('controls.ticks_ms',return_value=0): controls=Controls(d)
  old=self.e.state()['effect'];d.pressed=True
  with patch('controls.ticks_ms',return_value=5): controls.poll(self.e)
  self.assertEqual(self.e.state()['effect'],old)
  with patch('controls.ticks_ms',return_value=45): controls.poll(self.e)
  new=self.e.state()['effect'];self.assertNotEqual(new,old)
  with patch('controls.ticks_ms',return_value=1000): controls.poll(self.e)
  self.assertEqual(self.e.state()['effect'],new)
 def test_wifi_failure_retries_without_blocking(self):
  from types import SimpleNamespace
  class WLAN:
   active_state=False
   attempts=0
   def isconnected(self): return False
   def active(self,value): self.active_state=value
   def connect(self,*args): self.attempts+=1
   def disconnect(self): return
  wlan=WLAN();network=SimpleNamespace(STA_IF=0,WLAN=lambda _:wlan,hostname=lambda _:None)
  with patch.dict(sys.modules,{'network':network}),patch.object(config,'WIFI_SSID','test-only'):
   wifi=WiFi(self.e)
   with patch('web.ticks_ms',return_value=0): wifi.poll()
   self.assertEqual(wlan.attempts,1)
   with patch('web.ticks_ms',return_value=13000): wifi.poll()
   self.assertFalse(wlan.active_state)
   with patch('web.ticks_ms',return_value=15000): wifi.poll()
   self.assertEqual(wlan.attempts,1)
   with patch('web.ticks_ms',return_value=74000): wifi.poll()
   self.assertEqual(wlan.attempts,2)
   self.assertGreater(sum(self.e.step(.04)),0)
 def test_audio_palette_and_disabled_reactivity(self):
  p=Palette('audio_hue');a=Audio()
  a.bands=[1.0]+[0.0]*15;p.update(a);before=p.colors[:]
  a.bands=[0.0]*15+[1.0];p.update(a)
  self.assertNotEqual(p.colors,before)
  self.e.apply({'audio_reactive':False,'palette':'audio_spectrum'},0)
  self.e.audio.push([1]*7);self.e.step(.04)
  self.assertIs(self.e.contexts[0].audio,self.e.silent)
  self.assertEqual(self.e.contexts[0].audio.level,0)
 def test_particle_pool_and_zone_layers(self):
  from particles import Pool
  pool=Pool(8)
  for _ in range(50): pool.spawn(2,2,3,1,2,.5)
  self.assertEqual(len(pool.items),8)
  self.e.apply({'layers':[{'effect':'particles','zone':'left'},{'effect':'waveform','zone':'right'}]},0)
  for _ in range(50): self.e.step(.04)
  self.assertEqual(len(self.e.contexts),3)
  self.assertEqual(self.e.contexts[1].canvas.width,26)
  self.assertEqual(self.e.contexts[2].canvas.width,27)
  self.assertIsNone(self.e.error)
 def test_preserved_orbit_math(self):
  import ast
  from effects.passing_lights import Scene,Levels
  source=ast.parse((ROOT/'legacy/passing_lights.py').read_text())
  source.body=[node for node in source.body if not(isinstance(node,ast.ImportFrom) and node.module in ('galactic','picographics'))]
  old={'__name__':'legacy_test'}
  exec(compile(source,'legacy','exec'),old)
  fast=Scene();original=old['Scene']();levels=Levels();levels.set(.7,.5,.2,.65,.6,.1,.2)
  for _ in range(100): fast.update(.04,levels);original.update(.04,levels)
  errors=[abs(a-b) for i in range(583) for a,b in zip(fast.canvas.rgb(i),original.canvas.rgb(i))]
  self.assertLessEqual(max(errors),3)
 def test_http_partial_requests_and_limits(self):
  server=Server(self.e,0)
  port=server.listener.getsockname()[1]
  def request(parts):
   client=socket.create_connection(('127.0.0.1',port));client.setblocking(False)
   result=b''
   for part in parts:
    client.sendall(part)
    for _ in range(10): server.poll()
   for _ in range(1000):
    server.poll()
    try:
     chunk=client.recv(8192)
     if not chunk: break
     result+=chunk
    except BlockingIOError: time.sleep(.001)
   client.close()
   return result
  try:
   data=request([b'POST /api/state HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: 14\r\n\r\n',b'{"speed":0.25}'])
   self.assertIn(b'200 OK',data);self.assertEqual(self.e.contexts[0].params['speed'],.25)
   self.assertIn(b'413 Error',request([b'POST /api/state HTTP/1.1\r\nContent-Length: 9000\r\n\r\n']))
   self.assertIn(b'403 Error',request([b'POST /api/state HTTP/1.1\r\nHost: local\r\nOrigin: http://elsewhere\r\nContent-Length: 2\r\n\r\n{}']))
   old=os.getcwd()
   try:
    os.chdir(ROOT/'board')
    data=request([b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n'])
   finally: os.chdir(old)
   header,body=data.split(b'\r\n\r\n',1)
   self.assertIn(b'200 OK',header);self.assertEqual(body,(ROOT/'board/www/index.html').read_bytes())
  finally: server.close()

if __name__=='__main__': unittest.main(verbosity=2)
