---
type: Architecture
title: Infra Choir Enhanced Production Visualizer
description: Fill-inspired cached musical analysis, target-local envelopes, bounded effects, and a genuine high-resolution spectrum in the existing streaming compositor.
status: stable
tags: [architecture, comfyui, audio, spectrum, visualizer, fill-nodes]
---
# Infra Choir Enhanced Production Visualizer

## Entry point and compatibility

Open `user/default/workflows/music_visualizer_infra_choir_enhanced.json` after
restarting ComfyUI. The file is built from, but does not overwrite,
`music_visualizer_infra_choir_production.json`. The original node classes and
workflow remain registered and behaviorally unchanged. The enhanced graph uses
`InfraChoirAnimationTargetEnhanced` and `InfraChoirVisualizerEnhanced` while
retaining the seven detect → review → configure → stack lanes, fixed-frame
renderer, title card, branding, atomic output, and full-song streaming.

The master `enhancements_enabled` switch is the regression path. When false,
the enhanced node restores the production spectrum mode, height, and opacity
and ignores every enhanced target/effect setting. A four-second decoded A/B
produced identical video and audio MD5 values to the original renderer.

## Fill-Nodes audit and integration decision

The installed `ComfyUI_Fill-Nodes` checkout is Apache-2.0. Its implementations
were inspected rather than inferred from node labels.

| Registered node / implementation | Inputs → outputs | Dependencies and memory behavior | Decision |
| --- | --- | --- | --- |
| `FL_Audio_Drum_Detector` | `AUDIO`, three sensitivities, detection mode → drum-times `STRING` | NumPy, Torch, librosa; loads the whole waveform and computes STFT/onset arrays | Adapt the positive spectral-flux and band-transient concept into the renderer's one cached pass. Direct use would add a second full-song analysis and JSON adapter. |
| `FL_Audio_Reactive_Envelope` | drum-times `STRING`, fps, per-drum ADSR controls → three `FL_AUDIO_ENVELOPE` values | Python lists; full-song frame envelopes, low memory | Adapt ADSR/hold semantics. The custom envelope type is not compatible with `LOCAL_VISUALIZER_TARGET`, and three fixed drum outputs do not cover the required shared drivers. |
| `FL_Audio_BPM_Analyzer` | `AUDIO`, half-time, offset → `AUDIO`, BPM, beat JSON, preview `IMAGE` | librosa, Matplotlib, Torch; full-song beat analysis plus preview allocation | Do not connect. The enhanced shared pass derives beat phase/confidence without a redundant preview or analysis pass. |
| `FL_Audio_Beat_Prompt_Envelope` | beat JSON, prompt, stride/phase, attack/hold/release → prompt envelope, `FL_AUDIO_ENVELOPE`, preview | Beat-indexed Python envelope; intended for diffusion prompt masking | Adapt subdivision/accent and envelope-curve ideas; do not introduce diffusion prompt types. |
| `FL_Audio_Reactive_Brightness` / `Saturation` | full `IMAGE` batch plus `FL_AUDIO_ENVELOPE` and optional mask → full `IMAGE` batch | Torch/Pillow/NumPy; input and output batches remain resident | Exclude. Equivalent bounded luminance/saturation behavior already exists inside the frame streamer. |
| `FL_Audio_Reactive_Edge_Glow` | full `IMAGE` batch, envelope, optional edge frames/settings → full `IMAGE` batch | Torch Sobel; CPU chunks computation by four but still requires complete input/output batches | Adapt selective mask-edge treatment and compute the edge once per approved mask. Apply only the local crop per streamed frame. |
| `FL_Ripple` | full `IMAGE` batch, optional envelope and `IMAGE` mask, displacement controls → full `IMAGE` batch | NumPy meshgrids, Pillow and Torch concatenation; builds ripple and output batches | Exclude direct use. A restrained reflection shimmer is applied within the approved mask and current frame only. |
| `FL_Shadertoy` | dimensions/frame count/source and up to four `IMAGE` channels → `IMAGE` batch | PyOpenGL/GLFW plus Torch concatenation; creates the complete rendered batch | Exclude: hidden OpenGL context and full-song image accumulation conflict with Desktop portability and bounded memory. |
| `FL_Audio_Music_Video_Sequencer` | audio, beat JSON and shot patterns → sequence JSON/count | Full audio plus edit-list construction; no image batch | Exclude by design. It would replace the established renderer/timeline responsibilities rather than enhance them. |
| `FL_Audio_Separation` | full audio and separation controls → stems | Demucs/Open-Unmix class workloads and additional memory/model cost | Optional future input only. The default uses inexpensive vocal/instrument spectral proxies and never requires source separation. |

No Fill node is connected directly. The adapted analysis/envelope concepts are
attributed here and in the implementation docstring. No cloud API, generative
model, OpenGL shader, or Fill sequencer is involved.

## Shared analysis and cache

One Hann-window STFT pass computes frame-aligned values for RMS, low/mid/high
energy, positive-flux kick/snare/hi-hat accents, general onset strength, beat
confidence, beat phase, phrase intensity, slow intensity, and inexpensive
vocal/instrument energy proxies. Drum labels are spectral transient proxies for
a full mix, not isolated-stem classification.

The default spectrum is 256 genuinely computed logarithmic bands from 20 Hz to
20 kHz, bounded by Nyquist, using an 8192-point FFT and 2048-sample hop. Options
cover 32/64/128/256/512 bands, 4096/8192/16384 FFT, four hop sizes, linear/log
mapping, range, sensitivity, dynamic range, noise floor, transient emphasis,
and gain. Analysis frames are interpolated once to absolute output timestamps.

The cache key hashes mono audio samples, sample rate, duration, fps, and every
analysis parameter. Compressed NumPy arrays are stored under Comfy's temporary
directory in `infra_choir_audio_analysis`; purely visual changes reuse them.
The Bella Ciao cache changed analysis time from 9.517 seconds on miss to 0.135
seconds on a fresh-process hit.

## Target envelopes and linked lighting

Version-2 targets retain every version-1 field and add primary/secondary
drivers, driver mix, attack, decay, hold, sustain, release, smoothing,
minimum/maximum, sensitivity, response curve, rhythmic subdivision, accent,
group gain/delay, section response, and target-local edge/shimmer switches.
`assets/infra-choir-target-enhanced.example.json` is a concrete reusable
configuration. The schema accepts both target versions.

Targets with the same `envelope_group` reuse the same parent driver. Per-target
gain, delay and shaping distinguish the emitting sun, delayed illumination,
and higher-frequency river shimmer. Hair and fabric favor slow continuous
motion, atmosphere favors phrase/energy response, and direct transients remain
restrained. Optional `section_override_json` accepts a list of
`{"start": seconds, "end": seconds, "gain": 0..2}` objects.

## Effects and spectrum

Selective edge glow is derived once from the approved mask and applied only to
its local crop. Reflection shimmer and atmospheric modulation are likewise
mask-bounded. Global and target-local toggles are independent, default
strengths are restrained, and no camera transform is introduced.

Spectrum modes are legacy bars, fine bars, line, filled curve, and mirrored.
Independent attack/release smoothing, peak hold/decay, accent color, placement
margin, height, opacity, and the production crimson `#8E1325` are configurable.
Peak highlights default to `#D9B5A2`. The renderer consumes cached frame rows
and never performs an FFT inside the video-frame loop.

## Runtime contract and limitations

Frames continue to stream one at a time to FFmpeg; no full-song image tensor is
allocated. Cancellation closes/kills FFmpeg, partial files never replace valid
outputs, and progress uses the existing Comfy progress bar. The original audio
is muxed once and both A/B outputs decode to the same audio MD5.

Known limitations:

- source-separated vocal/instrument envelopes are proxies unless a user
  deliberately supplies a separate analysis path;
- spectral kick/snare/hat labels are reliable accents, not semantic stem labels;
- 512 bands can exceed one output pixel per bar after margins at small delivery
  widths, so line/filled modes are preferable there;
- mask quality remains the limiting factor for every spatial effect; and
- renderer cost is CPU/FFmpeg-bound. It performs no CUDA work, but concurrent
  Comfy activity can lengthen wall time.
