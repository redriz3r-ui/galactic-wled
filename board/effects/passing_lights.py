try:
    import micropython
except ImportError:
    from compat import micropython

# Passing Lights — standalone MicroPython version.
# Run directly in Thonny, or save to the device as main.py.


class Settings:
    WIDTH = 53
    HEIGHT = 11
    FPS = 40
    BRIGHTNESS = 0.65
    # Time constants in seconds. Larger values mean softer, longer motion.
    TRAIL_SECONDS = 0.18
    ATTACK_SECONDS = 0.07
    RELEASE_SECONDS = 0.32
    BACKGROUND = (1, 0, 2)
    BURGUNDY = (115, 12, 30)
    ROSE = (205, 57, 73)
    AMBER = (215, 99, 34)
    CREAM = (245, 191, 125)
    LEFT_X = 10.0
    RIGHT_X = 42.0
    CENTER_Y = 5.0
    REEL_RADIUS = 3.55
    ROTATION_SPEED = 0.72  # radians / second

S = Settings()


"""Normalized bass, mid, treble, overall level; no audio hardware required."""
from math import sin, pi, exp
import pixels


def clamp(value):
    return max(0.0, min(1.0, value))


class Levels:
    def __init__(self):
        self.bass = self.mid = self.treble = self.level = 0.0
        self.drum = self.snare = self.hat = 0.0

    def set(self, bass, mid, treble, level, drum=0.0, snare=0.0, hat=0.0):
        self.bass = clamp(bass)
        self.mid = clamp(mid)
        self.treble = clamp(treble)
        self.level = clamp(level)
        self.drum, self.snare, self.hat = clamp(drum), clamp(snare), clamp(hat)


class DemoInput:
    """Imaginary slow R&B phrasing, not a simulated spectrum analyzer."""
    def __init__(self):
        self.levels = Levels()

    def sample(self, seconds):
        beat = (seconds * 72.0 / 60.0) % 1.0
        pulse = exp(-beat * 6.0)
        self.levels.set(
            0.16 + 0.45 * pulse,
            0.30 + 0.22 * sin(seconds * 0.59),
            0.10 + 0.12 * (0.5 + 0.5 * sin(seconds * 1.17)),
            0.34 + 0.12 * sin(seconds * 2.0 * pi / 9.0))
        return self.levels


class ExternalInput:
    """A future audio reader can call push(), then use this as the source."""
    def __init__(self):
        self.levels = Levels()

    def push(self, bass=0.0, mid=0.0, treble=0.0, level=0.0):
        self.levels.set(bass, mid, treble, level)

    def sample(self, seconds):
        return self.levels


class Envelope:
    def __init__(self):
        self.levels = Levels()

    @micropython.native
    def update(self, target, dt):
        for name in ('bass', 'mid', 'treble', 'level'):
            old = getattr(self.levels, name)
            value = clamp(getattr(target, name))
            tau = S.ATTACK_SECONDS if value > old else S.RELEASE_SECONDS
            alpha = 1.0 - exp(-dt / tau)
            setattr(self.levels, name, old + (value - old) * alpha)
        return self.levels

"""Reusable RGB buffers, bilinear light splats and time-based persistence."""
from array import array
from math import floor, exp


class Canvas:
    def __init__(self):
        self.width, self.height = S.WIDTH, S.HEIGHT
        size = self.width * self.height * 3
        self.light = array('I', [0] * size)
        self.history = array('I', [0] * size)

    @micropython.native
    def begin(self):
        pixels.clear32(self.light)

    @micropython.native
    def persist(self, dt):
        pixels.persist32(self.history,self.light,int(exp(-dt/S.TRAIL_SECONDS)*256))

    @micropython.native
    def rgb(self, pixel):
        i = pixel * 3
        return tuple(min(255, int(self.history[i + c]/256 + S.BACKGROUND[c] + 0.5))
                     for c in range(3))

    def show(self, graphics):
        for y in range(self.height):
            for x in range(self.width):
                r, g, b = self.rgb(y * self.width + x)
                graphics.set_pen(graphics.create_pen(r, g, b))
                graphics.pixel(x, y)

"""Two soft orbiting lights with percussive movement and predictive glow."""
from math import sin, cos, pi


class Scene:
    """Two lights missing each other; spring impulses ride an elliptical orbit."""
    def __init__(self):
        self.canvas = Canvas()
        self.envelope = Envelope()
        self.phase = 0.0
        self.time = 0.0
        self.kick = self.snare = 0.0
        self.last_kick = self.last_snare = 0.0
        self.springs = [[0.0,0.0,0.0,0.0], [0.0,0.0,0.0,0.0]]
        self.positions = [(8.0,S.CENTER_Y),(S.WIDTH-9.0,S.CENTER_Y)]
        self.previous = None
        self.radii = [0.75,0.75]
        self.gains = [0.0,0.0]
        # Lookup removes hundreds of exponential calls per hardware frame.
        self.gaussian = array('H', [int(exp(-i*0.05)*65535) for i in range(241)])

    @micropython.native
    def field(self, cx, cy, sigma, color, gain):
        """Sample a continuous Gaussian at LED centers, retaining fractional x/y."""
        reach = sigma * 2.8
        x0, x1 = max(0,int(floor(cx-reach))), min(S.WIDTH-1,int(cx+reach)+1)
        y0, y1 = max(0,int(floor(cy-reach))), min(S.HEIGHT-1,int(cy+reach)+1)
        pixels.gaussian(self.canvas.light,self.gaussian,x0,x1,y0,y1,int(cx*256),int(cy*256),
                        int(10.0/(sigma*sigma)*256),int(color[0]*gain*256),
                        int(color[1]*gain*256),int(color[2]*gain*256))

    @micropython.native
    def orb(self, x, y, vx, vy, radius, color, gain, sparkle):
        # Soft outer halo. Brightness grows before the core reaches the next LED.
        self.field(x+vx*0.025,y+vy*0.025,radius*1.25,color,gain*0.19)
        # Weighted past/current/future exposures create a short directional blur.
        for offset,weight in ((-0.055,0.24),(0.0,0.66),(0.045,0.10)):
            self.field(x+vx*offset,y+vy*offset,radius,color,gain*weight)
        # Compact warm core, always sub-pixel blended rather than rounded.
        self.field(x,y,max(0.42,radius*0.31),S.CREAM,gain*(0.50+sparkle*0.24))

    @micropython.native
    def update(self, dt, target):
        dt = max(0.0,min(0.1,dt))
        self.time += dt
        levels = self.envelope.update(target,dt)
        self.kick = max(target.drum,self.kick*exp(-dt/0.13))
        self.snare = max(target.snare,self.snare*exp(-dt/0.10))
        kick_edge = max(0.0,target.drum-self.last_kick)
        snare_edge = max(0.0,target.snare-self.last_snare)
        self.last_kick,self.last_snare = target.drum,target.snare
        # Kick pulls them together; snare sends them past one another vertically.
        direction = 1.0 if self.positions[0][0] < self.positions[1][0] else -1.0
        for i,side in ((0,1.0),(1,-1.0)):
            spring = self.springs[i]
            spring[2] += side*direction*(18.0*kick_edge-7.0*snare_edge)
            spring[3] += side*13.0*snare_edge
            remaining = dt
            while remaining > 0:
                step = min(0.025,remaining)
                spring[2] += (-52.0*spring[0]-11.0*spring[2])*step
                spring[3] += (-60.0*spring[1]-12.0*spring[3])*step
                spring[0] += spring[2]*step
                spring[1] += spring[3]*step
                remaining -= step
        self.phase = (self.phase+dt*(0.055+0.26*levels.level+0.11*levels.mid))%(2*pi)
        cx = (S.WIDTH-1)/2.0
        spread = (S.WIDTH-1)*(0.30+0.075*(1-levels.level))
        # Midrange is a vocal-like phrase proxy, not isolated singing.
        lift = 1.05+0.55*levels.mid
        first = self.phase+pi
        second = self.phase+0.19+0.13*levels.mid
        self.positions = []
        for i,angle in enumerate((first,second)):
            spring = self.springs[i]
            x = cx+cos(angle)*spread+spring[0]
            y = S.CENTER_Y+sin(angle)*lift+spring[1]
            self.positions.append((max(3.0,min(S.WIDTH-4.0,x)),
                                   max(1.6,min(S.HEIGHT-2.6,y))))
        body = levels.level**1.6
        self.radii = [0.68+1.10*body+0.40*levels.mid+0.65*self.kick,
                      0.68+0.95*body+0.60*levels.mid+0.48*self.snare]
        self.gains = [0.055+0.56*levels.level+0.20*self.kick,
                      0.055+0.52*levels.level+0.25*self.snare]
        self.canvas.begin()
        for i,color in ((0,S.ROSE),(1,S.AMBER)):
            x,y = self.positions[i]
            vx=vy=0.0
            if self.previous is not None and dt>0:
                vx=max(-30.0,min(30.0,(x-self.previous[i][0])/dt))
                vy=max(-18.0,min(18.0,(y-self.previous[i][1])/dt))
            self.orb(x,y,vx,vy,self.radii[i],color,self.gains[i],
                     self.snare*0.7+target.hat*0.2)
        self.previous = self.positions[:]
        self.canvas.persist(dt)
        return self.canvas



def render(ctx):
    if 'scene' not in ctx.state: ctx.state['scene']=Scene()
    scene=ctx.state['scene']
    if 'levels' not in ctx.state: ctx.state['levels']=Levels()
    target=ctx.state['levels']
    gain=ctx.params['audio_amount']*(.4+1.6*ctx.params['sensitivity'])
    target.set(*(getattr(ctx.audio,n)*gain for n in ('bass','mid','treble','level','drum','snare','hat')))
    original=scene.update(ctx.dt*(.35+ctx.params['speed']*1.5),target)
    c=ctx.canvas
    pixels.field_rgb(c.data,original.history,int(ctx.params['intensity']*256))
