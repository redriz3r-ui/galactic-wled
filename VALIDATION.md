# Validation — 20 September 2026

## Result

- **16 platform tests passed**, including a real loopback HTTP server.
- **9 existing music tests passed** against the archived standalone board program.
- All board modules passed Python syntax compilation and imported successfully
  in the installed MicroPython firmware during temporary hardware execution.
- Every registered effect rendered on the actual 53 × 11 display; every preset
  resolved, the legacy V2 USB greeting was emitted, malformed API state was
  rejected, and offline startup worked without Wi-Fi credentials.
- Browser UI visually inspected against the real Python API: effect selection,
  waveform-specific controls, preset changes, audio meters, and layer controls.
- Original Mac players and media were not changed. The Pico's flash files and
  saved program were not replaced; tests used `mpremote mount`.

## Hardware and timing

The connected device identified itself as:

```text
MicroPython 1.25.0 preview
Raspberry Pi Pico2 W (Galactic Unicorn) with RP2350
CPU: 150 MHz
Display: 53 × 11
```

The code targets the common Galactic Unicorn MicroPython APIs and contains no
Pico-2-only peripheral calls. **The original Pico W / RP2040 was not available for
measurement.** Do not assume the following timings or free heap apply to it.

Measurements include audio updates, engine rendering, and the actual PicoGraphics
and Galactic Unicorn display update, averaged over 20 frames per effect. They
exclude scheduler sleep and active Wi-Fi traffic. Single base layer unless noted.

| Effect | Mean frame processing, ms |
| --- | ---: |
| Plasma | 21.35 |
| Spectrum | 22.15 |
| Starfield | 22.60 |
| Metaballs | 22.50 |
| Spectral History | 23.00 |
| Particles | 24.90 |
| Fire | 25.25 |
| Center Pulse | 27.10 |
| Sunrise | 29.05 |
| Passing Lights | 30.85 |
| Rain | 37.80 |
| Cassette | 48.85 |
| FreqWave | 49.25 |
| Digital Rain | 56.40 |
| Waveform | 74.35 |
| Default plasma + particle overlay (50 frames) | **25.02** |

At the configured 25 FPS, the default has approximately 15 ms of scheduling
headroom before network/GC overhead. FreqWave and Cassette approach 20 FPS;
Waveform and Digital Rain are slower. The scheduler skips sleep when processing
exceeds the frame budget; it does not build a backlog. These are short benchmarks,
not guarantees for every parameter/layer combination.

The final all-effect run ended with **319,360 bytes free heap after GC** on Pico 2 W,
after all modules and the preserved orbit renderer had been loaded.

## Bounded stress check

A 1,000-frame on-device run cycled plasma, spectrum, fire, metaballs, and cassette,
with transitions and a particle overlay, in approximately 38.5 seconds. No effect
errors occurred. Post-GC free heap at checkpoints:

| Frame | Free bytes |
| --- | ---: |
| 250 | 331,424 |
| 500 | 331,968 |
| 750 | 331,264 |
| 1,000 | 332,112 |

Restoring the same preset left 332,256 bytes free versus 334,624 before the run.
This initial difference includes populated particle slots and warmed allocations;
checkpoint values showed no progressive decline. This short check does **not**
establish multi-hour leak freedom. The final orbit acceleration was validated
separately after this stress run.

The original orbit's fixed-point conversion was compared over 100 frames against
the archived float implementation: maximum final-frame channel difference **1/255**,
mean difference approximately **0.0086/255**. The host regression allows 3/255.

## Covered host scenarios

USB four/seven-value packets, original handshake, malformed and oversized-line
recovery, 8/16-band and waveform extensions, smoothing/timeout/onset behavior,
static/dynamic palettes, disabled audio, all effects, preset reset semantics,
looping/non-looping playlists, API atomic validation, blend arithmetic, zone
bounds, power, transitions, saved settings/corruption, external-frame expiry,
button debounce, fixed particle capacity, Wi-Fi timeout/backoff, effect fallback,
partial HTTP requests, request limits, cross-origin rejection, streamed HTML,
and preserved orbit rendering. Legacy tests retain song timing, percussion cues,
sender backpressure/recovery, and original scene behavior checks.

## Remaining hardware limits

- No Wi-Fi credentials were supplied: successful association, router/mDNS behavior,
  phone access over Wi-Fi, and sustained network traffic were not tested on-device.
  The real HTTP server was tested on localhost; failed-connect timing was tested
  with a mocked WLAN.
- Physical button presses were not exercised by a person; button APIs were checked
  against Pimoroni's documentation and debounce was tested on the host.
- USB parsing and the exact greeting ran on-device; a full Mac-song listening test
  and end-to-end sound-to-LED latency measurement were not performed.
- No RP2040/Pico W performance, multi-hour soak, or high-rate external-frame video
  throughput claim is made.
