"""Legacy USB protocol plus optional B (8/16 bands) and W (53 waveform samples)."""
import sys
import select
from math import exp
import config
from utils import ticks_ms, ticks_diff, clamp, smooth, number

NAMES = ('bass', 'mid', 'treble', 'level', 'drum', 'snare', 'hat')
class Audio:
    def __init__(self):
        self.raw = [0.0]*7
        self.bands = [0.0]*16
        self.raw_bands = [0.0]*16
        self.waveform = [0.0]*53
        self.last_wave = self.last_bands = self.last = None
        self.gain, self.gate, self.agc = config.AUDIO_GAIN, config.AUDIO_GATE, config.AUDIO_AGC
        self.peak = self.beat = self.bass_beat = self.baseline = 0.0
        self.cooldown = self.bass_cooldown = 0.0
        self.previous_drum = self.previous_snare = 0.0
        self.connected = False
        for n in NAMES: setattr(self, n, 0.0)

    def push(self, values, bands=None, waveform=None):
        if len(values) not in (4, 7): raise ValueError('Expected 4 or 7 levels')
        for v in values: number(v)
        if bands is not None:
            if len(bands) not in (8,16): raise ValueError('Expected 8 or 16 bands')
            for v in bands: number(v)
        if waveform is not None:
            if len(waveform) != 53: raise ValueError('Expected 53 waveform samples')
            for v in waveform: number(v,-1,1)
        now = ticks_ms()
        for i in range(7): self.raw[i] = values[i] if i < len(values) else 0.0
        self.last = now
        if bands is not None:
            for i in range(16): self.raw_bands[i] = bands[i*len(bands)//16]
            self.last_bands = now
        if waveform is not None:
            for i in range(53): self.waveform[i] = waveform[i]
            self.last_wave = now

    def update(self, dt):
        now = ticks_ms()
        age = ticks_diff(now,self.last) if self.last is not None else 10000
        self.connected = age <= 1000
        self.peak = max(self.raw[3] if self.connected else 0, self.peak * exp(-dt/4))
        gain = self.gain * (min(3.0, 0.8/max(0.25,self.peak)) if self.agc else 1)
        old_level, old_bass = self.level, self.bass
        for i,n in enumerate(NAMES):
            v = self.raw[i] if self.connected else 0.0
            v = 0.0 if v < self.gate else clamp(v*gain)
            if i >= 4: v *= exp(-max(0,age)/65)
            setattr(self,n,smooth(getattr(self,n),v,dt,config.AUDIO_ATTACK,config.AUDIO_DECAY) if i<4 else v)
        self.cooldown = max(0,self.cooldown-dt)
        self.bass_cooldown = max(0,self.bass_cooldown-dt)
        self.beat = self.bass_beat = 0.0
        if not self.cooldown and (self.level-old_level > .07 or self.drum-self.previous_drum > .25 or self.snare-self.previous_snare > .3):
            self.beat = max(self.drum,self.snare,clamp((self.level-old_level)*5))
            self.cooldown = .18
        if not self.bass_cooldown and (self.bass-old_bass > .065 or self.drum-self.previous_drum > .25):
            self.bass_beat = max(self.drum,clamp((self.bass-old_bass)*6))
            self.bass_cooldown = .20
        self.previous_drum,self.previous_snare=self.drum,self.snare
        true_bands = self.last_bands is not None and ticks_diff(now,self.last_bands)<1000
        for i in range(16):
            if true_bands:
                v = self.raw_bands[i]
                v = 0 if v < self.gate else clamp(v*gain)
            else:
                p=i/15*2; j=int(p); f=p-j
                a=(self.bass,self.mid,self.treble)
                v=a[j]*(1-f)+a[min(2,j+1)]*f
            self.bands[i]=smooth(self.bands[i],v,dt)
        if self.last_wave is None or ticks_diff(now,self.last_wave)>250:
            self.last_wave=None
            for i in range(53): self.waveform[i] *= max(0,1-dt*8)

    def state(self):
        result={n:getattr(self,n) for n in NAMES}
        result.update(beat=self.beat,bass_beat=self.bass_beat,peak=self.peak,connected=self.connected)
        return result

class USBInput:
    def __init__(self, audio, stream=None, poller=None):
        self.audio = audio
        self.stream = stream or sys.stdin
        self.poll = poller or select.poll()
        self.poll.register(self.stream,select.POLLIN)
        self.line = ''
        self.overflow = False

    def receive_line(self,line):
        if line == 'HELLO':
            print('CASSETTE_READY_V2')
            return
        fields=line.split()
        if not fields: return
        try:
            values=[int(v) for v in fields[1:]]
            if not all(0<=v<=255 for v in values): return
            if fields[0]=='L' and len(values) in (4,7):
                self.audio.push([v/255 for v in values])
            elif fields[0]=='B' and len(values) in (8,16):
                self.audio.push(self.audio.raw, bands=[v/255 for v in values])
            elif fields[0]=='W' and len(values)==53:
                self.audio.push(self.audio.raw, waveform=[(v-128)/128 for v in values])
        except (ValueError,TypeError):
            return

    def poll_once(self):
        for _ in range(256):
            if not self.poll.poll(0): break
            char=self.stream.read(1)
            if not char: break
            if char=='\n':
                if not self.overflow: self.receive_line(self.line.strip())
                self.line=''; self.overflow=False
            elif not self.overflow:
                if len(self.line)<224: self.line+=char
                else: self.line=''; self.overflow=True
