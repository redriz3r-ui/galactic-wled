try:
    import micropython
except ImportError:
    from compat import micropython

import time
from math import sin, pi
try:
    ticks_ms = time.ticks_ms
    ticks_diff = time.ticks_diff
except AttributeError:
    def ticks_ms(): return int(time.monotonic() * 1000)
    def ticks_diff(a, b): return a - b

@micropython.native
def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))
def number(v, lo=0.0, hi=1.0):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
        raise ValueError('Number outside allowed range')
    return v

def smooth(old, target, dt, attack=0.06, decay=0.3):
    tau = attack if target > old else decay
    return old + (target-old) * min(1.0, dt / max(0.001, tau))

SINE = tuple(sin(i * 2*pi/256) for i in range(256))
@micropython.native
def wave(phase): return SINE[int(phase * 40.743665) & 255]

SINE_BYTES=bytearray(int((v+1)*127.5) for v in SINE)
