try:
    import micropython
except ImportError:
    from compat import micropython

"""RGB888 reusable canvases; a layer's coordinates are local to its zone."""
from utils import clamp
import pixels
MODES=('replace','add','lighten','screen','alpha')
ZONES={'full':(0,0,53,11),'left':(0,0,26,11),'right':(26,0,27,11),
       'center':(16,0,21,11),'top':(0,0,53,5),'bottom':(0,5,53,6)}
class Canvas:
    def __init__(self,width=53,height=11):
        self.width,self.height=width,height
        self.data=bytearray(width*height*3)
    @micropython.native
    def fade(self,keep):
        pixels.fade(self.data,int(keep*256))
    @micropython.native
    def pixel(self,x,y,color,gain=1):
        x,y=int(x),int(y)
        if 0<=x<self.width and 0<=y<self.height:
            i=(y*self.width+x)*3
            for k in range(3): self.data[i+k]=min(255,max(0,int(color[k]*gain)))
    @micropython.native
    def point(self,x,y,color,gain=1):
        pixels.point(self.data,self.width,self.height,int(x*256),int(y*256),
                     max(0,int(color[0]*gain)),max(0,int(color[1]*gain)),max(0,int(color[2]*gain)))
    @micropython.native
    def line(self,x0,y0,x1,y1,color,gain=1):
        steps=max(1,int(max(abs(x1-x0),abs(y1-y0))*1.5))
        for i in range(steps+1):
            f=i/steps; self.point(x0+(x1-x0)*f,y0+(y1-y0)*f,color,gain)

def composite(out,src,zone,mode='add',alpha=1):
    ox,oy,w,h=zone
    code=0 if mode in ('replace','alpha') else 1 if mode=='add' else 2 if mode=='lighten' else 3
    pixels.blend(out.data,src.data,ox,oy,w,h,code,int(alpha*256))
