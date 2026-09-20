try:
    import micropython
except ImportError:
    from compat import micropython

"""Copy the CONTENTS of board/ onto the Pico filesystem, then reboot."""
import gc
import time
from galactic import GalacticUnicorn
from picographics import PicoGraphics, DISPLAY_GALACTIC_UNICORN
import config
from utils import ticks_ms,ticks_diff
from engine import Engine
from audio import USBInput
from controls import Controls

class Display:
    def __init__(self,device,graphics):
        self.device,self.graphics=device,graphics
        self.brightness=None
    @micropython.native
    def show(self,data,brightness):
        if brightness!=self.brightness:
            self.device.set_brightness(brightness);self.brightness=brightness
        g=self.graphics
        for y in range(config.HEIGHT):
            for x in range(config.WIDTH):
                i=(y*config.WIDTH+x)*3
                g.set_pen(g.create_pen(data[i],data[i+1],data[i+2]))
                g.pixel(x,y)
        self.device.update(g)

def run():
    device=GalacticUnicorn()
    graphics=PicoGraphics(DISPLAY_GALACTIC_UNICORN)
    if graphics.get_bounds()!=(config.WIDTH,config.HEIGHT): raise ValueError('Expected Galactic Unicorn 53x11')
    engine=Engine();display=Display(device,graphics)
    try: usb=USBInput(engine.audio)
    except (OSError,ValueError): usb=None
    controls=Controls(device)
    wifi=None
    if config.WEB_ENABLED:
        try:
            from web import WiFi
            wifi=WiFi(engine)
        except (ImportError,OSError,MemoryError) as error: engine.error='Web disabled: '+str(error)
    frame_ms=max(1,1000//config.FPS);previous=ticks_ms();gc.collect()
    try:
        while True:
            start=ticks_ms();dt=max(1,ticks_diff(start,previous))/1000;previous=start
            if usb:
                try: usb.poll_once()
                except (OSError,ValueError): engine.error='USB read failed'
            try: controls.poll(engine)
            except (OSError,ValueError,MemoryError): engine.error='Control change failed'
            if wifi: wifi.poll()
            data=engine.step(dt)
            display.show(data,engine.brightness)
            engine.render_ms=ticks_diff(ticks_ms(),start)
            if engine.frames%125==0: gc.collect()
            remaining=frame_ms-ticks_diff(ticks_ms(),start)
            if remaining>0: time.sleep_ms(remaining)
    finally:
        if wifi and wifi.server: wifi.server.close()
        device.clear()

if __name__=='__main__': run()
