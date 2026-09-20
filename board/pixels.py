try:
    import micropython
except ImportError:
    from compat import micropython
    def ptr8(value): return value
    def ptr16(value): return value
    def ptr32(value): return value


@micropython.viper
def fade(data, keep: int):
    p=ptr8(data)
    for i in range(int(len(data))): p[i]=(p[i]*keep)>>8

@micropython.viper
def mix(out, old, new, amount: int):
    a=ptr8(out);b=ptr8(old);c=ptr8(new)
    for i in range(int(len(out))): a[i]=(b[i]*(256-amount)+c[i]*amount)>>8

@micropython.viper
def blend(out, src, ox: int, oy: int, width: int, height: int, mode: int, alpha: int):
    a=ptr8(out);b=ptr8(src)
    for y in range(height):
        base=((y+oy)*53+ox)*3
        row=y*width*3
        for x in range(width*3):
            old=int(a[base+x]);v=int(b[row+x])
            if mode==0: v=(old*(256-alpha)+v*alpha)>>8
            elif mode==1: v=old+((v*alpha)>>8)
            elif mode==2:
                v=(v*alpha)>>8
                if old>v: v=old
            else: v=255-(((255-old)*(255-((v*alpha)>>8)))//255)
            if v>255: v=255
            a[base+x]=v

@micropython.viper
def point(data, width: int, height: int, x: int, y: int, r: int, g: int, b: int):
    p=ptr8(data);ix=x>>8;iy=y>>8;fx=x&255;fy=y&255
    for dy in range(2):
        yy=iy+dy
        if yy<0 or yy>=height: continue
        wy=256-fy
        if dy: wy=fy
        for dx in range(2):
            xx=ix+dx
            if xx<0 or xx>=width: continue
            wx=256-fx
            if dx: wx=fx
            weight=wx*wy;index=(yy*width+xx)*3
            value=p[index]+((r*weight)>>16)
            if value>255: value=255
            p[index]=value
            value=p[index+1]+((g*weight)>>16)
            if value>255: value=255
            p[index+1]=value
            value=p[index+2]+((b*weight)>>16)
            if value>255: value=255
            p[index+2]=value

@micropython.viper
def plasma(data, palette, sine, width: int, height: int, phase: int, scale: int, bass: int, gain: int):
    out=ptr8(data);pal=ptr8(palette);lut=ptr8(sine)
    for y in range(height):
        bend=(int(lut[(y*29-phase)&255])-128)*(32+bass)>>6
        for x in range(width):
            value=(int(lut[(x*scale+phase+bend)&255])+int(lut[(y*18-phase*7//10+x*2)&255])+int(lut[(x*5+y*12+phase*4//10)&255]))//12
            if value>63: value=63
            j=value*3;i=(y*width+x)*3
            out[i]=(pal[j]*gain)>>8;out[i+1]=(pal[j+1]*gain)>>8;out[i+2]=(pal[j+2]*gain)>>8

@micropython.viper
def heat_step(heat, width: int, height: int, seed: int):
    p=ptr8(heat)
    for y in range(height-1):
        below=(y+1)*width
        for x in range(width):
            left=x-1
            if left<0: left=width-1
            right=x+1
            if right>=width: right=0
            v=(p[below+x]*2+p[below+left]+p[below+right])>>2
            v-=3+(x*13+y*7+seed)%20
            if v<0: v=0
            p[y*width+x]=v

@micropython.viper
def heat_draw(data, heat, palette, gain: int):
    out=ptr8(data);values=ptr8(heat);pal=ptr8(palette)
    for i in range(int(len(heat))):
        v=int(values[i]);index=(v>>2)*3;scale=v*gain
        out[i*3]=(pal[index]*scale)>>16
        out[i*3+1]=(pal[index+1]*scale)>>16
        out[i*3+2]=(pal[index+2]*scale)>>16

@micropython.viper
def spectrum(data, bands, peaks, palette, width: int, height: int, fall: int, gain: int):
    out=ptr8(data);b=ptr8(bands);p=ptr8(peaks);pal=ptr8(palette)
    for x in range(width):
        v=int(b[x*16//width]);peak=int(p[x])-fall
        if v>peak: peak=v
        if peak<0: peak=0
        p[x]=peak
        level=v*height
        for y in range(height):
            strength=level-y*255
            if strength<0: strength=0
            if strength>255: strength=255
            position=(x*38//width+y*25//height)*3
            intensity=(strength*gain*(128+128*y//height))>>16
            index=((height-1-y)*width+x)*3
            out[index]=(pal[position]*intensity)>>8
            out[index+1]=(pal[position+1]*intensity)>>8
            out[index+2]=(pal[position+2]*intensity)>>8
        if peak>3:
            y=height-1-peak*(height-1)//255;index=(y*width+x)*3
            out[index]=(pal[180]*gain)>>9
            out[index+1]=(pal[181]*gain)>>9
            out[index+2]=(pal[182]*gain)>>9

@micropython.viper
def blobs(data,palette,width: int,height: int,x0: int,y0: int,x1: int,y1: int,x2: int,y2: int,radius: int,gain: int,blur: int):
    out=ptr8(data);pal=ptr8(palette)
    for y in range(height):
        for x in range(width):
            dx=x*4-x0;dy=y*4-y0
            value=radius//(16+dx*dx+dy*dy)
            dx=x*4-x1;dy=y*4-y1
            value+=radius//(16+dx*dx+dy*dy)
            dx=x*4-x2;dy=y*4-y2
            value+=radius//(16+dx*dx+dy*dy)
            if value>255: value=255
            j=(value>>2)*3;index=(y*width+x)*3
            brightness=(value*blur+((value*value)>>8)*(256-blur))>>8
            brightness=(brightness*gain)>>8
            out[index]=(pal[j]*brightness)>>8
            out[index+1]=(pal[j+1]*brightness)>>8
            out[index+2]=(pal[j+2]*brightness)>>8

@micropython.viper
def row(data,width: int,y: int,r: int,g: int,b: int):
    out=ptr8(data);start=y*width*3
    for x in range(width):
        i=start+x*3;out[i]=r;out[i+1]=g;out[i+2]=b

@micropython.viper
def clear32(data):
    out=ptr32(data)
    for i in range(int(len(data))): out[i]=0

@micropython.viper
def persist32(history, light, keep: int):
    out=ptr32(history);src=ptr32(light)
    for i in range(int(len(history))):
        old=(int(out[i])*keep)>>8;v=int(src[i])
        if old>v: v=old
        out[i]=v

@micropython.viper
def gaussian(data,lut,x0: int,x1: int,y0: int,y1: int,cx: int,cy: int,scale: int,r: int,g: int,b: int):
    out=ptr32(data);table=ptr16(lut)
    for y in range(y0,y1+1):
        dy=y*256-cy
        for x in range(x0,x1+1):
            dx=x*256-cx
            position=((((dx*dx+dy*dy)>>8)*scale)>>8)
            n=position>>8
            if n>=240: continue
            f=position&255
            v=(table[n]*(256-f)+table[n+1]*f)>>12
            i=(y*53+x)*3
            out[i]+=((v*r)>>12);out[i+1]+=((v*g)>>12);out[i+2]+=((v*b)>>12)

@micropython.viper
def field_rgb(data,history,gain: int):
    out=ptr8(data);src=ptr32(history)
    for i in range(int(len(data))):
        background=0
        if i%3==0: background=1
        elif i%3==2: background=2
        value=((int(src[i])+(background<<8))*gain)>>16
        if value>255: value=255
        out[i]=value
