try:
    import micropython
except ImportError:
    from compat import micropython

import gc
import pixels
import config
from utils import ticks_ms,ticks_diff,number,clamp
from audio import Audio
from palettes import Palette,PALETTES
from compositor import Canvas,composite,ZONES,MODES
from effects import DEFAULTS,NAMES,resolve
from presets import Store,SHOWCASE

class Context:
    def __init__(self,spec):
        self.spec=spec
        self.zone=ZONES[spec['zone']]
        self.canvas=Canvas(self.zone[2],self.zone[3])
        self.palette=Palette(spec['palette'])
        self.params=spec['params']
        self.render=resolve(spec['effect'])
        self.state={};self.phase=0.0;self.dt=0.04;self.audio=None
        self.palette_clock=0.0

def params(values):
    if not isinstance(values,dict): raise ValueError('params must be an object')
    result=DEFAULTS.copy()
    for k,v in values.items():
        if k not in DEFAULTS: raise ValueError('Unknown parameter: '+str(k))
        if isinstance(DEFAULTS[k],bool):
            if not isinstance(v,bool): raise ValueError(k+' must be boolean')
        elif k=='direction':
            if v not in (-1,1) or isinstance(v,bool): raise ValueError('direction must be -1 or 1')
        else: number(v)
        result[k]=v
    return result

def layer(value,base=False):
    if not isinstance(value,dict): raise ValueError('Layer must be an object')
    if set(value)-set(('effect','palette','params','zone','blend','opacity')): raise ValueError('Unknown layer field')
    effect=value.get('effect','plasma');palette=value.get('palette','midnight')
    if effect not in NAMES: raise ValueError('Unknown effect')
    if palette not in PALETTES: raise ValueError('Unknown palette')
    zone=value.get('zone','full');blend=value.get('blend','replace' if base else 'add')
    if zone not in ZONES or blend not in MODES: raise ValueError('Invalid zone or blend')
    return {'effect':effect,'palette':palette,'params':params(value.get('params',{})),
            'zone':zone,'blend':blend,'opacity':number(value.get('opacity',1))}

class Engine:
    def __init__(self,store=None):
        self.audio=Audio();self.silent=Audio();self.store=store or Store()
        self.output=Canvas();self.previous=bytearray(len(self.output.data));self.display=bytearray(len(self.output.data))
        self.power=True;self.brightness=config.BRIGHTNESS;self.audio_reactive=True
        self.active_preset=None;self.contexts=[];self.transition=0;self.transition_age=0
        self.playlist=None;self.playlist_index=0;self.playlist_age=0;self.playlist_running=False
        self.fps=0;self.render_ms=0;self.error=None;self.ip=None;self.frames=0
        self.external=None;self.external_at=None
        self.last_save=None
        self.apply({'effect':'plasma','palette':'midnight'},0)
        try: self.apply_preset(config.DEFAULT_PRESET,0)
        except (ValueError,TypeError,KeyError,MemoryError): self.error='Default preset unavailable'
        if self.store.saved:
            try: self.apply(self.store.saved,0)
            except (ValueError,TypeError,KeyError,MemoryError): self.error='Invalid saved settings; using default'
        # Drop invalid user entries before they can appear in playlists/UI.
        valid=[]
        for p in self.store.user:
            try:
                if not isinstance(p,dict) or not isinstance(p.get('name'),str): continue
                self.prepare({k:v for k,v in p.items() if k!='name'})
                valid.append(p)
            except (ValueError,TypeError,KeyError,MemoryError): continue
        self.store.user=valid

    def state(self,persistent=False):
        base=self.contexts[0].spec
        result={'power':self.power,'brightness':self.brightness,'effect':base['effect'],
                'palette':base['palette'],'params':base['params'].copy(),'audio_reactive':self.audio_reactive,
                'layers':[c.spec for c in self.contexts[1:]]}
        if not persistent:
            result.update(preset=self.active_preset,audio=self.audio.state(),fps=round(self.fps,1),
                          render_ms=self.render_ms,ip=self.ip,error=self.error,
                          playlist={'running':self.playlist_running,'index':self.playlist_index,'definition':self.playlist})
            try: result['free_memory']=gc.mem_free()
            except AttributeError: result['free_memory']=None
        return result

    def prepare(self,patch):
        if not isinstance(patch,dict): raise ValueError('State must be an object')
        allowed=('power','brightness','effect','palette','params','audio_reactive','layers')
        if set(patch)-set(allowed)-set(DEFAULTS): raise ValueError('Unknown state field')
        current=self.state(True) if self.contexts else {'effect':'plasma','palette':'midnight','params':{},'layers':[],
            'power':True,'brightness':config.BRIGHTNESS,'audio_reactive':True}
        p=current['params'].copy()
        if 'params' in patch:
            if not isinstance(patch['params'],dict): raise ValueError('Invalid params')
            p.update(patch['params'])
        for k in DEFAULTS:
            if k in patch: p[k]=patch[k]
        current.update({k:v for k,v in patch.items() if k in allowed and k!='params'})
        current['params']=params(p)
        for k in ('power','audio_reactive'):
            if not isinstance(current[k],bool): raise ValueError(k+' must be boolean')
        number(current['brightness'])
        layers=current['layers']
        if not isinstance(layers,list) or len(layers)>=config.MAX_LAYERS: raise ValueError('At most two overlay layers')
        base=layer({'effect':current['effect'],'palette':current['palette'],'params':current['params']},True)
        specs=[base]+[layer(s) for s in layers]
        # The preserved float-buffer effect is intentionally restricted to the base layer.
        if any(s['effect']=='passing_lights' for s in specs[1:]): raise ValueError('Passing Lights is base-only')
        return current,specs

    def apply(self,patch,transition=None):
        settings,specs=self.prepare(patch)
        duration=config.TRANSITION if transition is None else number(transition,0,10)
        contexts=[]
        for i,spec in enumerate(specs):
            old=self.contexts[i] if i<len(self.contexts) else None
            if old and old.spec['effect']==spec['effect'] and old.spec['palette']==spec['palette'] and old.spec['zone']==spec['zone']:
                contexts.append(old)
            else: contexts.append(Context(spec))
        # All validation/allocation has succeeded before live state changes.
        self.previous[:]=self.display
        for i,c in enumerate(contexts): c.spec=specs[i];c.params=specs[i]['params']
        self.contexts=contexts
        self.power=settings['power'];self.brightness=settings['brightness'];self.audio_reactive=settings['audio_reactive']
        self.transition=duration;self.transition_age=0
        self.active_preset=None

    def apply_preset(self,name,transition=None):
        value=self.store.get(name)
        patch={k:v for k,v in value.items() if k!='name'}
        patch['params']=params(patch.get('params',{}))
        self.apply(patch,transition)
        self.active_preset=name

    def set_playlist(self,value):
        if value is None: self.playlist_running=False;return
        if not isinstance(value,dict) or set(value)-set(('items','loop')): raise ValueError('Invalid playlist')
        items=value.get('items');loop=value.get('loop',True)
        if not isinstance(items,list) or not 1<=len(items)<=24 or not isinstance(loop,bool): raise ValueError('Invalid playlist')
        clean=[]
        for item in items:
            if not isinstance(item,dict) or set(item)-set(('preset','duration','transition')): raise ValueError('Invalid playlist item')
            self.store.get(item.get('preset'))
            duration=number(item.get('duration',30),1,86400)
            fade=number(item.get('transition',1),0,min(10,duration))
            clean.append({'preset':item['preset'],'duration':duration,'transition':fade})
        self.apply_preset(clean[0]['preset'],clean[0]['transition'])
        self.playlist={'items':clean,'loop':loop};self.playlist_index=0;self.playlist_age=0;self.playlist_running=True

    def save(self,name=None):
        now=ticks_ms()
        if self.last_save is not None and ticks_diff(now,self.last_save)<5000: raise ValueError('Wait five seconds between saves')
        previous=self.store.user[:]
        if name is not None:
            if not isinstance(name,str) or not 1<=len(name)<=40: raise ValueError('Preset name must be 1-40 characters')
            from presets import DEFAULTS as builtins
            if any(p['name']==name for p in builtins): raise ValueError('Choose a new preset name')
            value=self.state(True);value['name']=name
            self.store.user=[p for p in self.store.user if p.get('name')!=name]
            if len(self.store.user)>=12: self.store.user=previous;raise ValueError('Maximum 12 user presets')
            self.store.user.append(value)
        try: self.store.write(self.state(True))
        except OSError:
            self.store.user=previous
            raise
        self.last_save=now

    def frame(self,data):
        if len(data)!=config.WIDTH*config.HEIGHT*3: raise ValueError('Expected 1749 RGB888 bytes')
        if self.external is None: self.external=bytearray(len(data))
        self.external[:]=data;self.external_at=ticks_ms()

    @micropython.native
    def step(self,dt):
        dt=clamp(dt,.001,.2)
        self.audio.update(dt)
        if self.playlist_running:
            self.playlist_age+=dt
            item=self.playlist['items'][self.playlist_index]
            if self.playlist_age>=item['duration']:
                nxt=self.playlist_index+1
                if nxt>=len(self.playlist['items']):
                    if self.playlist['loop']: nxt=0
                    else: self.playlist_running=False
                if self.playlist_running:
                    item=self.playlist['items'][nxt]
                    try: self.apply_preset(item['preset'],item['transition'])
                    except (ValueError,MemoryError): self.error='Playlist preset failed';self.playlist_running=False
                    self.playlist_index=nxt;self.playlist_age=0
        self.output.fade(0)
        for c in self.contexts:
            c.dt=dt;c.audio=self.audio if self.audio_reactive else self.silent
            c.phase+=dt*(.12+c.params['speed']*2)
            c.palette_clock-=dt
            if c.palette_clock<=0 and c.palette.name.startswith('audio_'):
                c.palette.update(c.audio);c.palette_clock=.1
            # History scroll owns its persistent canvas; other trails decay with time.
            if c.spec['effect']!='spectral_history':
                keep=c.params['trail']**(dt*25) if c.params['trail'] else 0
                c.canvas.fade(keep)
            try: c.render(c)
            except Exception as error:
                self.error='Effect '+c.spec['effect']+': '+str(error)
                c.render=resolve('plasma');c.state={}
            composite(self.output,c.canvas,c.zone,c.spec['blend'],c.spec['opacity'])
        self.transition_age+=dt
        mix=min(1,self.transition_age/self.transition) if self.transition else 1
        pixels.mix(self.display,self.previous,self.output.data,int(mix*256))
        if self.external_at is not None:
            age=ticks_diff(ticks_ms(),self.external_at)
            if age<1000: self.display[:]=self.external
            else:
                # Fade from the last external frame back to the live scene.
                self.previous[:]=self.external;self.transition_age=0;self.transition=1;self.external_at=None
        if not self.power:
            pixels.fade(self.display,0)
        self.frames+=1
        self.fps=self.fps*.95+(1/dt)*.05
        return self.display
