import time,gc
from engine import Engine
from galactic import GalacticUnicorn
from picographics import PicoGraphics,DISPLAY_GALACTIC_UNICORN
from main import Display
from api import API
from audio import USBInput
from web import WiFi
from presets import Store
board=GalacticUnicorn();graphics=PicoGraphics(DISPLAY_GALACTIC_UNICORN);display=Display(board,graphics)
e=Engine(Store('/remote/nonexistent-test-settings.json'));api=API(e)
# Warm all effects used in the cycling stress check before measuring retained heap.
for name in ('plasma','particles','spectrum','fire','metaballs','cassette'):
 e.apply({'effect':name},0);e.step(.04)
e.apply_preset('Moody R&B',0)
for _ in range(50): display.show(e.step(.04),.15)
gc.collect();before=gc.mem_free();start=time.ticks_ms()
for i in range(1000):
 if i%100==0:
  e.apply({'effect':('plasma','spectrum','fire','metaballs','cassette')[(i//100)%5]},.6)
 e.audio.push([.6,.4,.2,.5,1 if i%25==0 else 0,0,.1])
 display.show(e.step(.04),.15)
 if i%125==0: gc.collect()
 if i in (249,499,749,999):
  gc.collect();print('SOAK',i+1,'HEAP',gc.mem_free(),'ERROR',e.error)
 assert e.error is None
# Compare the same final object graph with the starting state.
e.apply_preset('Moody R&B',0)
for _ in range(50): e.step(.04)
gc.collect();print('SOAK_MS',time.ticks_diff(time.ticks_ms(),start));print('HEAP_BEFORE',before,'HEAP_AFTER',gc.mem_free())
print('SOAK_OK');board.clear()
