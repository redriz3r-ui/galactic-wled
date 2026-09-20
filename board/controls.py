from utils import ticks_ms,ticks_diff,clamp
from effects import NAMES
from palettes import PALETTES
class Controls:
    def __init__(self,device):
        self.device=device;self.buttons=[]
        for name,action in (('SWITCH_A','next'),('SWITCH_B','previous'),('SWITCH_C','palette'),
                            ('SWITCH_D','preset'),('SWITCH_BRIGHTNESS_UP','up'),
                            ('SWITCH_BRIGHTNESS_DOWN','down'),('SWITCH_VOLUME_UP','audio'),('SWITCH_SLEEP','power')):
            pin=getattr(device,name,None)
            if pin is not None: self.buttons.append([pin,action,False,False,ticks_ms(),ticks_ms()])
    def poll(self,engine):
        now=ticks_ms()
        for b in self.buttons:
            raw=self.device.is_pressed(b[0])
            if raw!=b[2]: b[2]=raw;b[4]=now
            if ticks_diff(now,b[4])>=35 and raw!=b[3]:
                b[3]=raw
                if raw: self.act(engine,b[1]);b[5]=now
            elif raw and b[3] and b[1] in ('up','down') and ticks_diff(now,b[5])>180:
                self.act(engine,b[1]);b[5]=now
    def act(self,e,action):
        state=e.state(True)
        if action in ('next','previous'):
            i=NAMES.index(state['effect']);e.apply({'effect':NAMES[(i+(1 if action=='next' else -1))%len(NAMES)]})
        elif action=='palette':
            names=tuple(PALETTES);i=names.index(state['palette']);e.apply({'palette':names[(i+1)%len(names)]})
        elif action=='preset':
            names=[p['name'] for p in e.store.all()];i=names.index(e.active_preset) if e.active_preset in names else -1
            e.apply_preset(names[(i+1)%len(names)])
        elif action=='audio': e.audio_reactive=not e.audio_reactive
        elif action=='power': e.power=not e.power
        else: e.brightness=clamp(e.brightness+(.05 if action=='up' else -.05))
        e.playlist_running=False
