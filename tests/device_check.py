import gc,time
import config
from galactic import GalacticUnicorn
from picographics import PicoGraphics,DISPLAY_GALACTIC_UNICORN
from main import Display
from engine import Engine
from effects import NAMES
from audio import USBInput
from web import WiFi
from api import API
from presets import Store
board=GalacticUnicorn();graphics=PicoGraphics(DISPLAY_GALACTIC_UNICORN);display=Display(board,graphics)
e=Engine(Store('/remote/device-test-no-settings.json'));api=API(e)
import machine
print('CPU_HZ',machine.freq())
print('BOUNDS',graphics.get_bounds());gc.collect();print('START_HEAP',gc.mem_free())
for name in NAMES:
 e.apply({'effect':name,'layers':[]},0)
 start=time.ticks_ms()
 for i in range(20):
  e.audio.push([.7,.5,.3,.6,1 if i%10==0 else 0,0,.2])
  data=e.step(.04);display.show(data,.18)
 elapsed=time.ticks_diff(time.ticks_ms(),start)
 gc.collect()
 print('EFFECT',name,'MS',elapsed/20,'HEAP',gc.mem_free(),'ERROR',e.error)
 assert e.error is None
 assert len(data)==1749
for p in e.store.all():
 e.apply_preset(p['name'],0);e.step(.04)
e.apply_preset('Moody R&B',0)
start=time.ticks_ms()
for i in range(50): display.show(e.step(.04),.18)
print('SHOWCASE_MS',time.ticks_diff(time.ticks_ms(),start)/50)
usb=USBInput(e.audio);usb.receive_line('HELLO');usb.receive_line('L 255 128 64 200 255 0 10')
assert e.audio.raw[0]==1
assert api.handle('POST','/api/state',b'{"speed":0.4}')[0]==200
assert api.handle('POST','/api/state',b'{"speed":2}')[0]==400
wifi=WiFi(e);wifi.poll()
print('OFFLINE_OK',wifi.wlan is None)
gc.collect();print('FINAL_HEAP',gc.mem_free());print('DEVICE_CHECK_OK')
board.clear()
