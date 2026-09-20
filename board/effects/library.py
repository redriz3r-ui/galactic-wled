try:
    import micropython
except ImportError:
    from compat import micropython

from math import sin, cos, pi, sqrt
import random
from utils import wave, clamp, SINE_BYTES
import pixels
from particles import Pool
import config

@micropython.native
def energy(c,name='level'):
    return clamp(getattr(c.audio,name)*c.params['audio_amount']*(.4+1.6*c.params['sensitivity']))
@micropython.native
def color(c,p,gain=1):
    rgb=c.palette.sample(clamp(p))
    gain*=c.params['intensity']
    return (int(rgb[0]*gain),int(rgb[1]*gain),int(rgb[2]*gain))

def plasma(c):
    pixels.plasma(c.canvas.data,c.palette.lut,SINE_BYTES,c.canvas.width,c.canvas.height,
                  int(c.phase*40.74),int(4+c.params['scale']*13),int(energy(c,'bass')*100),
                  int(c.params['intensity']*(.45+energy(c)*.45)*256))

@micropython.native
def waveform(c):
    w,h=c.canvas.width,c.canvas.height;mid=(h-1)/2
    amplitude=(.3+energy(c)*.7)*mid*(.25+c.params['scale']*1.5)
    live=c.audio.last_wave is not None and c.audio.connected
    if c.params['scrolling']:
        history=c.state.get('wave')
        if history is None: history=[0.0]*w;c.state['wave']=history
        for i in range(w-1): history[i]=history[i+1]
        history[-1]=(c.audio.waveform[-1]*c.params['audio_amount'] if live else wave(c.phase*6)*energy(c))
    prev=mid
    for x in range(w):
        if c.params['scrolling']: v=c.state['wave'][x]
        elif live: v=c.audio.waveform[min(52,x*53//w)]
        else: v=wave(x*.34-c.phase*3)*(.2+energy(c,'mid'))+wave(x*.83+c.phase)*energy(c,'treble')*.25
        y=mid+v*amplitude;rgb=color(c,x/max(1,w-1))
        if c.params['center_line']: c.canvas.pixel(x,mid,rgb,.12)
        c.canvas.line(max(0,x-1),prev,x,y,rgb,.7)
        if c.params['mirrored']: c.canvas.point(x,2*mid-y,rgb,.5)
        prev=y

def spectrum(c):
    w,h=c.canvas.width,c.canvas.height
    if 'peaks' not in c.state:
        c.state['peaks']=bytearray(w);c.state['bands']=bytearray(16)
    bands=c.state['bands']
    gain=c.params['audio_amount']*(.4+1.6*c.params['sensitivity'])
    for i in range(16): bands[i]=int(clamp(c.audio.bands[i]*gain)*255)
    fall=max(1,int(c.dt*(1+8*(1-c.params['decay']))*(.5+c.params['speed'])*255/h))
    pixels.spectrum(c.canvas.data,bands,c.state['peaks'],c.palette.lut,w,h,fall,int(c.params['intensity']*256))

@micropython.native
def freqwave(c):
    w,h=c.canvas.width,c.canvas.height
    for x in range(w):
        b=c.audio.bands[min(15,x*16//w)]*c.params['audio_amount']*(.4+1.6*c.params['sensitivity'])
        y=(h-1)*(.5+wave(x*.15-c.phase*2)*(.12+b*.35))
        rgb=color(c,x/max(1,w-1))
        c.canvas.point(x,y,rgb,.5+b*.5)
        c.canvas.point(x,h-1-y,rgb,.3+b*.3)

@micropython.native
def spectral_history(c):
    w,h=c.canvas.width,c.canvas.height
    c.state['clock']=c.state.get('clock',0)+c.dt*(3+c.params['speed']*25)
    if c.state['clock']<1: return
    c.state['clock']%=1
    d=c.canvas.data;right=c.params['direction']>=0
    for y in range(h):
        base=y*w*3
        if right:
            for i in range(w*3-1,2,-1): d[base+i]=d[base+i-3]
        else:
            for i in range((w-1)*3): d[base+i]=d[base+i+3]
        band=clamp(c.audio.bands[min(15,(h-1-y)*16//h)]*c.params['audio_amount']*(.4+1.6*c.params['sensitivity']))
        c.canvas.pixel(0 if right else w-1,y,color(c,1-y/max(1,h-1)),.025+band*.95)

@micropython.native
def cassette(c):
    w,h=c.canvas.width,c.canvas.height
    r=min(h*.34,w*.13)*( .85+.3*energy(c,'bass'));cy=(h-1)/2
    for side in (.21,.79):
        cx=(w-1)*side
        for i in range(24):
            a=i*pi/12
            c.canvas.point(cx+cos(a)*r,cy+sin(a)*r,color(c,i/23),.48)
        for i in range(3):
            a=c.phase*(1+energy(c)*3)+i*2*pi/3
            c.canvas.line(cx+cos(a)*r*.25,cy+sin(a)*r*.25,cx+cos(a)*r*.8,cy+sin(a)*r*.8,color(c,.65),.65)
        c.canvas.point(cx,cy,color(c,.95),.9)
    for x in range(int(w*.34),int(w*.67)):
        c.canvas.point(x,cy+wave(x*.65-c.phase*5)*energy(c,'mid')*2,color(c,.5),.6)
    if random.random()<energy(c,'treble')*.3:
        c.canvas.point(random.randrange(w),random.randrange(h),color(c,.95),.6)

@micropython.native
def center_pulse(c):
    pulses=c.state.get('pulses')
    if pulses is None: pulses=[[0.0,0.0] for _ in range(6)];c.state['pulses']=pulses;c.state['timer']=0
    c.state['timer']+=c.dt
    if energy(c,'bass_beat')>.1 or c.state['timer']>2.5:
        p=min(pulses,key=lambda p:p[1]);p[0]=0;p[1]=.35+energy(c,'bass');c.state['timer']=0
    mid=(c.canvas.width-1)/2
    for p in pulses:
        if p[1]<=.01: continue
        p[0]+=c.dt*(3+c.params['speed']*20);p[1]*=max(0,1-c.dt*(.4+1-c.params['decay']))
        for y in range(c.canvas.height):
            rgb=color(c,clamp(p[0]/max(1,mid)))
            c.canvas.point(mid-p[0],y,rgb,p[1]*.6);c.canvas.point(mid+p[0],y,rgb,p[1]*.6)

def pool(c):
    if 'pool' not in c.state: c.state['pool']=Pool(config.MAX_PARTICLES)
    return c.state['pool']
@micropython.native
def particles(c):
    p=pool(c);w,h=c.canvas.width,c.canvas.height
    rate=(1+c.params['density']*12)*(1+energy(c)*2)
    count=int(energy(c,'beat')*8)
    if random.random()<rate*c.dt: count+=1
    for _ in range(count):
        a=random.random()*pi*2;v=2+energy(c,'bass')*14
        p.spawn(w*.5,h*.5,cos(a)*v*c.params['direction'],sin(a)*v*.4,1+random.random()*2,random.random())
    if random.random()<energy(c,'treble')*c.dt*12: p.spawn(random.random()*w,random.random()*h,0,-1,.35,.95)
    p.update(c,damping=.2,bounds='bounce')

@micropython.native
def starfield(c):
    p=pool(c);w,h=c.canvas.width,c.canvas.height
    if random.random()<c.dt*(3+c.params['density']*20)*(1+energy(c)):
        direction=c.params['direction'];v=(3+c.params['speed']*14)*(1+energy(c)*2)
        p.spawn(0 if direction>0 else w-1,random.random()*(h-1),v*direction,0,12,random.random())
    p.update(c,damping=0)

@micropython.native
def digital_rain(c):
    w,h=c.canvas.width,c.canvas.height
    drops=c.state.get('drops')
    if drops is None: drops=[random.random()*h for _ in range(w)];c.state['drops']=drops
    for x in range(0,w,2):
        drops[x]=(drops[x]+c.dt*(1+c.params['speed']*10+energy(c,'treble')*10))%(h+5)
        for j in range(4):
            c.canvas.point(x,drops[x]-j,color(c,1-j/5),(1-j/4)*(.25+c.params['density']*.75))

@micropython.native
def fire(c):
    w,h=c.canvas.width,c.canvas.height
    heat=c.state.get('heat')
    if heat is None: heat=bytearray(w*h);c.state['heat']=heat;c.state['clock']=0
    c.state['clock']+=c.dt*(8+c.params['speed']*22)
    if c.state['clock']>=1:
        c.state['clock']%=1
        pixels.heat_step(heat,w,h,random.randrange(1000))
        for x in range(w): heat[(h-1)*w+x]=int(clamp(random.random()*(.5+c.params['scale']*.5)+energy(c,'bass')*.5)*255)
    pixels.heat_draw(c.canvas.data,heat,c.palette.lut,int(c.params['intensity']*256))

@micropython.native
def metaballs(c):
    w,h=c.canvas.width,c.canvas.height;t=c.phase*(.7+energy(c,'mid'))
    blobs=c.state.get('blobs')
    if blobs is None: blobs=[[0,0] for _ in range(3)];c.state['blobs']=blobs
    for i,b in enumerate(blobs):
        b[0]=(w-1)*(.5+wave(t*(.5+i*.15)+i*2)*(.35-energy(c,'bass')*.12))
        b[1]=(h-1)*(.5+wave(t*.8+i*2.4)*.35)
    radius=1+c.params['scale']*6+energy(c,'bass')*4
    pixels.blobs(c.canvas.data,c.palette.lut,w,h,int(blobs[0][0]*4),int(blobs[0][1]*4),
                 int(blobs[1][0]*4),int(blobs[1][1]*4),int(blobs[2][0]*4),int(blobs[2][1]*4),
                 int(radius*4080),int(c.params['intensity']*256),int(c.params['blur']*256))

@micropython.native
def rain(c):
    p=pool(c);w,h=c.canvas.width,c.canvas.height
    if random.random()<c.dt*(2+c.params['density']*24):
        p.spawn(random.random()*w,0,-.8,3+c.params['speed']*12,4,.4+random.random()*.5)
    p.update(c,damping=0)
    ripple=c.state.get('ripple',0)
    if energy(c,'bass_beat')>.15: ripple=1
    ripple=max(0,ripple-c.dt*1.5);c.state['ripple']=ripple
    if ripple:
        for x in range(w): c.canvas.point(x,h-1,color(c,x/max(1,w-1)),ripple*.3*(.5+.5*wave(x*.5-c.phase*4)))

@micropython.native
def sunrise(c):
    # One continuous solar orbit: lower half is night, upper half daylight.
    w,h=c.canvas.width,c.canvas.height
    angle=c.phase*.055-pi/2; altitude=sin(angle);day=clamp((altitude+.18)*1.6)
    sun_x=(w-1)*(.5+.43*cos(angle));sun_y=(h-1)*(1.05-altitude*.9)
    for y in range(h):
        horizon=y/max(1,h-1)
        rgb=color(c,.06+day*.6+horizon*.22,.07+day*.65)
        pixels.row(c.canvas.data,w,y,rgb[0],rgb[1],rgb[2])
    for y in range(h):
        for x in range(max(0,int(sun_x-4)),min(w,int(sun_x+5))):
            distance=(x-sun_x)**2+(y-sun_y)**2
            if distance<12: c.canvas.point(x,y,color(c,.97),clamp(1-distance/12)*.8)
    if day<.3:
        for i in range(12): c.canvas.point((i*17+3)%w,(i*7+1)%max(1,h-2),color(c,.9),(.3-day)*(.5+.5*wave(c.phase+i)))
