# Galactic WLED

A compact, WLED-inspired visualizer for the **53 × 11 Pimoroni Galactic Unicorn**.
This is independent MicroPython software, not a WLED port. It boots into a slow
Midnight plasma field with subtle purple particles, at 45% brightness, with USB
audio enabled. Audio, Wi-Fi, and a browser are optional.

The original Mac players, song files, vocal stems, cue data, and timing settings
are unchanged. The previous board program and documentation are preserved in
`legacy/`. Its orbit animation is also available as **Passing Lights**.

## Install

Keep your working Pimoroni Galactic Unicorn MicroPython firmware. It must provide
`galactic`, `picographics`, `select`, and MicroPython native/Viper emitters. For a
fresh device use the matching **Galactic Unicorn** firmware from
[Pimoroni's releases](https://github.com/pimoroni/unicorn/releases), selecting the
correct Pico W or Pico 2 W hardware. Standard Raspberry Pi MicroPython does not
include the required display libraries.

1. Stop the Mac music player and close serial monitors.
2. Back up the Pico's current files using Thonny or `mpremote`.
3. Optionally edit `board/config.py`: set `WIFI_SSID` and `WIFI_PASSWORD` for your
   2.4 GHz network. Empty credentials disable connection attempts.
4. Copy **everything inside `board/`** to the root of the Pico filesystem. Keep
   the `effects/` and `www/` directories. Copying just `main.py` is no longer enough.
5. Close Thonny and reboot. The visualizer starts without REPL interaction.
6. Run your existing Mac launcher as before.

With `mpremote` installed, from this project directory:

```sh
mpremote connect /dev/cu.usbmodem101 fs cp -r board/. :/
mpremote connect /dev/cu.usbmodem101 reset
```

Replace the port with yours (`mpremote devs`). Upload only `board/`, not the Mac
Python environment, media files, tests, legacy backup, or `__pycache__` directories.
The code was temporarily mounted for hardware validation; this repository update
does **not** replace the program saved on your Pico.

To restore the former standalone program, copy `legacy/passing_lights.py` onto the
Pico as `main.py`. The other platform files can remain unused.

## Mac audio: preserved compatibility

`computer/Play Song.command` and `computer/play.py` still play the existing WAV
using macOS AVAudioPlayer and send timestamped envelopes with the saved timing
adjustment in `computer/timing.json`. Dependencies remain `pyserial`, `pyobjc-core`,
and `pyobjc-framework-Cocoa`. The player retains its one-packet-in-flight flow
control and bounded percussion-peak retention. Type `+`, `-`, or a millisecond
number in its terminal to adjust timing. Existing cue data belongs to its song;
changing the WAV alone does not regenerate cues.

`rnb_visualizer/send_song.py` is also unchanged. It uses Demucs vocal stems,
librosa, NumPy, sounddevice, and pyserial. Run it from its own directory with the
song path; it reacts to isolated vocals rather than capturing all Mac system audio.
Neither player is a live system-loopback recorder.

The USB protocol remains newline-delimited ASCII at 115200 baud:

```text
HELLO
→ CASSETTE_READY_V2
L bass mid treble level
L bass mid treble level drum snare hat
```

Each numeric value is an integer **0–255**. The original order matters: bass first,
overall level fourth. A `HELLO` following an `L` packet acknowledges that cue, as
required by `CueLink`. Malformed packets are discarded; an overlong line is ignored
through its next newline. Reads are limited to 256 characters per frame.

Optional backward-compatible extensions:

```text
B b0 b1 ... b7          # 8 bands, or supply 16 values
W s0 s1 ... s52         # 53 signed waveform samples encoded with zero = 128
```

Existing senders provide **three broad frequency envelopes**, not an FFT or signed
waveform. The platform interpolates their bass/mid/treble into 16 display bands.
Without `W`, Waveform draws an envelope-driven flowing wave, not a measured sound
wave. New senders can provide real bands/waveform through USB or HTTP.

Audio processing centralizes attack/release smoothing, gain, noise gate, optional
AGC, peaks, onset detection, and bass transients. Percussion decays rapidly; all
energy fades after a one-second input timeout. Ambient motion continues in silence.
AGC defaults off because both existing players already normalize their data.

## Controls

| Button | Action |
| --- | --- |
| A / B | Next / previous effect |
| C | Next palette |
| D | Next preset |
| Brightness + / − | Adjust brightness; holding repeats |
| Volume + | Toggle audio reactivity |
| Sleep | Toggle display power; processing continues |

Buttons debounce for 35 ms. Changing modes with buttons stops a running playlist.
A/B changes only the base effect: overlays remain until changed by a preset, the
web panel, or the API. Unsupported button constants are skipped on older firmware.

## Browser panel

Wi-Fi connects in the background, with a 12-second attempt timeout and 60-second
retry interval. Failure leaves the display running. Find the IP in your router's
client list or the startup serial message, then open `http://<IP>/` on the same LAN.
The hostname is `galactic`; `galactic.local` is **not guaranteed** because mDNS
support varies by firmware and router. IP access is the supported route.

The dark, phone-friendly panel controls power, brightness, effect, palette,
preset, supported effect parameters, audio reactivity, overlay layers, and zones.
It shows live level/bass/mid/treble/beat meters and measured FPS. Start showcase
plays four presets for 30 seconds each with 1.5-second transitions. Stop playlist
holds the current look.

**Save startup** persists the current look. **Save new preset** stores a named
custom preset and startup state. There are at most 12 custom presets; saving an
existing custom name replaces it. Built-in presets cannot be overwritten. Writes
are explicit, rate-limited to five seconds, and use a temporary file plus rename.
Changing sliders does not write flash. Playlist progress and transient audio are
not persisted. Credentials stay in `config.py` and are never returned by the API.

This is a local LAN controller without authentication or TLS. Do not forward its
port to the internet. Browser cross-origin writes are rejected. The web server
serves one client at a time; polling is intentionally modest to protect rendering.

## Effects and palettes

| Effect | Behavior |
| --- | --- |
| Plasma | Smooth integer 2D field; bass bends the field, level raises its glow |
| Waveform | Mirroring, scrolling, center line, trails; optional real sample input |
| Spectrum | Frequency bars with gradients and falling peaks |
| FreqWave | Frequency-space ribbons across the long matrix |
| Spectral History | Frequency rows scrolling through 53 columns of musical history |
| Cassette | Two rotating abstract reels, bass pulses, center wave, treble shimmer |
| Center Pulse | Bass/beat-triggered expanding pulses; gentle idle pulses |
| Particles | Pooled emissions, beat bursts, bass velocity, treble sparks |
| Starfield | Moving stars with audio speed and density |
| Digital Rain | Falling pixel tails adapted to eleven rows |
| Fire | Propagating heat field with bass-driven fuel |
| Metaballs | Three soft organic fields; audio changes radius and separation |
| Rain | Falling drops and bass-triggered bottom ripples |
| Sunrise | Continuous night → dawn → daylight → golden hour → sunset → twilight |
| Passing Lights | Preserved rose/amber orbit and spring-impulse renderer |

17 interpolated palettes: Midnight, Purple Haze, Warm Sunset, Sunrise, Ocean,
Fire, Matrix, Ice, Neon, Vaporwave, Pastel, Monochrome, Red Noir, Blue Noir,
Green Noir, Golden Hour, Cyberpunk. Stops are interpolated into a 64-color lookup;
`Palette.sample(0..1)` returns its nearest lookup color.

Three dynamic palettes add music response to otherwise ambient effects:
**Audio Hue** shifts with frequency centroid; **Audio Spectrum** maps 16 bands to
palette positions; **Audio BMT** mixes frequency regions into color channels.
Palette positions run horizontally in the frequency-oriented effects; organic
fields interpret them as field values. Dynamic palettes refresh at 10 Hz.
Passing Lights intentionally retains its original rose/amber colors.

Built-in presets: Moody R&B, Midnight Drive, Dreamscape, Club, Spectrum, Cassette
Night, Ambient, Cyberpunk, Sunset, Matrix, Fire, Chill, and Passing Lights.

Most controls are normalized **0–1**. Direction is **−1 or +1**; mirrored,
scrolling, and center_line are booleans. `/api/effects` lists useful controls for
each effect. Intensity affects the render; brightness controls the hardware.
Audio amount controls musical influence, while sensitivity scales its response.
The engine also keeps unsupported common parameters for cross-effect consistency.
Passing Lights uses the original motion equations with an accelerated fixed-point
Gaussian renderer; the regression sample differs by at most 1 RGB level from the
original float renderer.

## JSON API

Requests use `Content-Type: application/json` and `Content-Length`; chunked request
bodies are unsupported. Errors return JSON with HTTP 400, 404, 413, 415, or 503.
State mutations validate fully before committing, including overlay allocation.
Invalid effect names are rejected without disturbing the active look. Invalid
saved startup settings fall back to the default preset.

| Route | Purpose |
| --- | --- |
| `GET /api/state` | Live settings, parameters, audio, FPS, errors, IP, free heap, playlist |
| `POST /api/state` | Partial state update; stops playlist |
| `GET /api/effects` | Registered effects and supported controls |
| `GET /api/palettes` | Palette IDs |
| `GET /api/presets` | Built-in and user presets |
| `POST /api/preset` | Apply `{"name":"Cassette Night"}` |
| `GET /api/playlist` | Definition, running state, current index |
| `POST /api/playlist` | Start a playlist; JSON `null` stops it |
| `POST /api/save` | `{}` saves startup; `{"name":"My mix"}` also saves a preset |
| `POST /api/audio` | Normalized levels, optional bands/waveform |
| `POST /api/audio/config` | Runtime gain (0–4), gate (0–0.5), AGC boolean |
| `POST /api/frame` | Exactly 1749 RGB888 bytes, row-major, top-left first |

```sh
curl http://<IP>/api/state
curl http://<IP>/api/state -H 'Content-Type: application/json' \
  -d '{"effect":"plasma","palette":"audio_spectrum","speed":0.35}'
curl http://<IP>/api/audio -H 'Content-Type: application/json' \
  -d '{"levels":[0.7,0.4,0.2,0.6,1,0,0]}'
```

Both top-level `speed` and `params: {"speed":...}` are accepted. GET returns the
canonical nested `params` object. Incoming audio levels use the same order as USB,
but are **0–1** floats; optional waveform samples are **−1 to +1**, 53 values.
USB and HTTP share the same normalized state: the latest valid update wins.

Layers: the base effect covers the whole matrix. Up to two overlays get separate
persistent RGB buffers, independent effect parameters/palettes, opacity, and a zone.

```json
{"effect":"plasma","palette":"midnight","layers":[
  {"effect":"waveform","palette":"purple_haze","blend":"add",
   "opacity":0.55,"zone":"center","params":{"trail":0.5}}
]}
```

Blends: `replace`, `add`, `screen`, `lighten`, `alpha`. Zones: `full`, `left`,
`right`, `center`, `top`, `bottom`. Effects see local zone coordinates. Passing
Lights is base-only because its preserved field buffers are relatively large.

```json
{"items":[
  {"preset":"Moody R&B","duration":30,"transition":1.5},
  {"preset":"Cassette Night","duration":30,"transition":1.5}
],"loop":true}
```

Playlists allow 1–24 items, durations of 1–86400 seconds, and transitions up to
10 seconds. Non-looping lists hold their final look. Transitions blend a snapshot
of the last displayed frame into the evolving new scene, avoiding two simultaneous
full effect engines. Brightness itself changes immediately.

The framebuffer route is a bounded experimental path, **not DDP**: POST binary
`application/octet-stream` data. It holds incoming pixels for up to one second,
then crossfades back to the internally running scene. Global brightness/power
still apply. HTTP overhead limits throughput; it is intended for modest-rate
external frames rather than guaranteed video streaming.

## Architecture and extension

- `main.py`: proven GalacticUnicorn/PicoGraphics setup, frame scheduler, display output.
- `engine.py`: reusable contexts, runtime validation, layers, transitions, playlists.
- `audio.py`: USB receiver and normalized shared state.
- `palettes.py`: static/dynamic palette lookups.
- `compositor.py`, `pixels.py`: RGB canvases and native integer rendering kernels.
- `particles.py`: bounded reusable pool with movement, damping, gravity, fade,
  kill/wrap/bounce bounds.
- `effects/__init__.py`: metadata and resolver; `effects/library.py`: compact effect
  functions; `effects/passing_lights.py`: lazily imported preserved renderer.
- `presets.py`: defaults and explicit atomic persistence.
- `controls.py`: debounced buttons; `api.py`: hardware-independent request handling.
- `web.py`, `www/index.html`: bounded nonblocking HTTP and static vanilla-JS UI.
- `utils.py`: clock wrappers, smoothing, validation, sine lookup.
- `compat.py`: desktop-only decorator shims for tests/previews.

To add an effect, add its ID and useful parameter names to `EXTRAS` in
`effects/__init__.py`, then implement a same-named function in `effects/library.py`:

```python
def my_effect(ctx):
    ctx.canvas.point(ctx.canvas.width / 2, ctx.canvas.height / 2,
                     ctx.palette.sample(0.5), ctx.params['intensity'])
```

The context provides `dt`, speed-adjusted `phase`, `audio`, `params`, `palette`,
`canvas`, and an effect-private `state` dictionary. Allocate persistent data once
inside `state`; avoid per-frame growth. The engine supplies a silent audio state
when reactivity is disabled. Effects need no hardware or input parsers.

Add a palette by inserting a tuple of RGB stops in `PALETTES`; it appears in the
API and UI automatically. Add custom zone rectangles in `compositor.ZONES`; they
must stay inside the physical 53 × 11 display. The accelerated compositor is
intentionally specialized to this physical width.

## Performance and compromises

The scheduler targets 25 FPS and never accumulates a catch-up backlog. Complex
scenes run slower while input/network processing continues once per frame.
Animation dt is bounded after pauses. Full RGB888 color uses the existing
`create_pen`, `pixel`, and `update` hardware path; brightness is changed only when
necessary. No coarse color quantization is imposed on dim gradients.

Each full canvas is 1749 bytes. Base plus two overlays, composition output,
previous-frame snapshot, and display output use at most **10,494 pixel bytes**.
The optional external frame adds 1749 bytes. This excludes Python objects,
particle pools, effect data, compiled native code, network buffers, and the
Pimoroni driver's own buffers. Passing Lights additionally uses its fixed-point
field buffers. Pixel kernels use native/Viper integer arithmetic; buffers and
particle slots are reused. Some tuple/number allocation remains in Python effects;
garbage collection runs every 125 frames. Module imports are cached, not evicted.

Networking permits one active request, at most 1024 header bytes and 4096 body
bytes; it receives 512 and sends at most 1024 bytes per frame. Idle connections
expire after 2.5 seconds; total request lifetime is limited to 10 seconds. HTML
streams from flash in chunks. No threads, asyncio framework, recursive rendering,
large UI strings, or external JavaScript libraries are required.

See `VALIDATION.md` for measured hardware timings and known test limits. The
connected test board identified itself as a **Pico 2 W / RP2350**, not the requested
original Pico W / RP2040; original Pico W timing and heap headroom remain unmeasured.

## Troubleshooting

- **ImportError after upload:** copy all contents of `board/`, preserving directories;
  use Pimoroni firmware for the correct Galactic Unicorn hardware.
- **No USB response / port busy:** quit Thonny and other serial programs; restart
  the Mac launcher after reboot. Keep the V2 handshake unchanged.
- **Quiet-looking spectrum:** existing audio has only three broad regions; true
  detailed spectra need `B` packets or the HTTP bands field.
- **No Wi-Fi:** check 2.4 GHz SSID/password, router client isolation, and IP. The
  display should still animate. `.local` resolution is optional.
- **UI error:** check `/api/state` error and free-memory fields. One browser at a
  time works best. Reload after a device restart.
- **Slow effects:** remove overlays, use Plasma/FreqWave/History, lower density,
  or reduce `FPS`. Waveform and dense Digital Rain can run below 20 FPS.
- **Bad saved settings:** remove `settings.json` from the Pico to restore defaults.
- **Save fails:** check free flash space and wait five seconds before another save.
- **Sunrise appears stationary:** its full day/night cycle takes several minutes;
  speed controls that duration and the cycle repeats indefinitely.

## Desktop preview

Run `python3 computer/preview.py --demo-audio`, then open
`http://127.0.0.1:8895/` to test the actual browser UI/API with synthetic envelopes.
It does not connect to your Pico or play sound. Preview settings live in a temporary
folder; Control-C stops the server. For rendered effect images, install Pillow
on the Mac and run `python3 tests/render_gallery.py /path/to/output`.

## Tests

```sh
python3 tests/check_platform.py
python3 tests/check_music.py
```

The first suite uses only Python's standard library (including a loopback HTTP
server). The legacy music suite also needs pyserial and the existing media/cue
files. Tests cover effect registration, palette bounds, malformed input, USB
handshake and overflow recovery, timeouts, transients, state atomicity, persistence,
playlists, transitions, bounds/blends, controls, external frames, effect fallback,
and partial HTTP requests. Hardware measurements are separate; desktop timing is
not a claim about Pico performance.

Hardware API reference:
[Pimoroni Galactic Unicorn](https://github.com/pimoroni/pimoroni-pico/blob/main/micropython/modules/galactic_unicorn/README.md).
Network references: [MicroPython sockets](https://docs.micropython.org/en/latest/library/socket.html)
and [WLAN](https://docs.micropython.org/en/latest/library/network.WLAN.html).
