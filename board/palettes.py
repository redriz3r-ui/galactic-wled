try:
    import micropython
except ImportError:
    from compat import micropython

from utils import clamp
PALETTES = {
'midnight': ((2,0,10),(28,4,70),(105,24,130),(35,55,110)),
'purple_haze': ((9,0,25),(70,5,115),(195,55,180),(90,55,200)),
'warm_sunset': ((20,0,20),(150,18,45),(240,90,25),(255,190,90)),
'sunrise': ((6,3,28),(115,25,75),(245,105,40),(255,225,145)),
'ocean': ((0,3,20),(0,35,95),(0,155,175),(95,235,210)),
'fire': ((0,0,0),(120,0,0),(255,65,0),(255,225,85)),
'matrix': ((0,0,0),(0,35,4),(0,150,20),(130,255,145)),
'ice': ((0,10,35),(15,70,145),(85,210,245),(220,250,255)),
'neon': ((20,0,60),(240,0,100),(15,210,255),(100,255,20)),
'vaporwave': ((20,5,55),(240,55,175),(70,210,225),(135,70,220)),
'pastel': ((95,65,130),(245,145,175),(150,215,215),(245,210,140)),
'monochrome': ((0,0,0),(255,255,255)),
'red_noir': ((0,0,0),(35,0,5),(175,5,25),(245,55,65)),
'blue_noir': ((0,0,0),(0,8,40),(10,45,160),(65,140,255)),
'green_noir': ((0,0,0),(0,25,12),(5,100,45),(70,220,100)),
'golden_hour': ((20,3,0),(130,40,5),(235,120,25),(255,225,110)),
'cyberpunk': ((4,0,25),(110,0,180),(255,10,90),(0,220,240)),
'audio_hue': (), 'audio_spectrum': (), 'audio_bmt': ()}

def hsv(h,s=1,v=1):
    h=(h%1)*6; i=int(h); f=h-i
    p=v*(1-s); q=v*(1-f*s); t=v*(1-(1-f)*s)
    colors=((v,t,p),(q,v,p),(p,v,t),(p,q,v),(t,p,v),(v,p,q))
    c=colors[i%6]
    return (int(c[0]*255),int(c[1]*255),int(c[2]*255))

class Palette:
    def __init__(self,name='midnight'):
        self.name=name if name in PALETTES else 'midnight'
        self.colors=[(0,0,0)]*64
        self.lut=bytearray(192)
        self.update(None)
    def update(self,audio):
        stops=PALETTES[self.name]
        dominant=0.75
        if audio:
            total=sum(audio.bands)
            if total>.01: dominant=sum(i*audio.bands[i] for i in range(16))/(15*total)
        for i in range(64):
            p=i/63
            if stops:
                pos=p*(len(stops)-1); j=min(len(stops)-2,int(pos)); f=pos-j
                a,b=stops[j],stops[j+1]
                self.colors[i]=tuple(int(a[k]+(b[k]-a[k])*f) for k in range(3))
            elif self.name=='audio_hue':
                self.colors[i]=hsv(dominant*.8+p*.22,.8,.18+p*.72)
            elif self.name=='audio_spectrum':
                v=audio.bands[min(15,int(p*16))] if audio else 0
                self.colors[i]=hsv(.78-p*.72,.85,.12+.88*v)
            else:
                b,m,t=(audio.bass,audio.mid,audio.treble) if audio else (0,0,0)
                self.colors[i]=(int(20+210*b*(1-p)),int(5+180*m*(1-abs(2*p-1))),int(30+220*t*p))
        for i in range(64):
            c=self.colors[i];j=i*3
            self.lut[j]=c[0];self.lut[j+1]=c[1];self.lut[j+2]=c[2]
    @micropython.native
    def sample(self,p): return self.colors[min(63,max(0,int(p*63)))]
