try:
    import micropython
except ImportError:
    from compat import micropython

import random
from utils import clamp
class Pool:
    def __init__(self,count=32):
        # x,y,vx,vy,age,life,color-position; dead slots have life=0.
        self.items=[[0.0]*7 for _ in range(count)]
        self.cursor=0
    def spawn(self,x,y,vx,vy,life=1,color=.5):
        p=self.items[self.cursor]; self.cursor=(self.cursor+1)%len(self.items)
        p[0]=x;p[1]=y;p[2]=vx;p[3]=vy;p[4]=0;p[5]=life;p[6]=color
    @micropython.native
    def update(self,ctx,gravity=0,damping=.1,bounds='kill'):
        c=ctx.canvas; dt=ctx.dt*(.3+ctx.params['speed']*2)
        for p in self.items:
            if p[5]<=0: continue
            p[4]+=dt
            if p[4]>=p[5]: p[5]=0;continue
            p[2]*=max(0,1-damping*dt);p[3]+=gravity*dt
            p[0]+=p[2]*dt;p[1]+=p[3]*dt
            if bounds=='wrap': p[0]%=c.width;p[1]%=c.height
            elif bounds=='bounce':
                if p[0]<0 or p[0]>c.width-1: p[2]=-p[2];p[0]=clamp(p[0],0,c.width-1)
                if p[1]<0 or p[1]>c.height-1: p[3]=-p[3];p[1]=clamp(p[1],0,c.height-1)
            elif not (0<=p[0]<c.width and 0<=p[1]<c.height): p[5]=0;continue
            c.point(p[0],p[1],ctx.palette.sample(p[6]),(1-p[4]/p[5])*ctx.params['intensity'])
