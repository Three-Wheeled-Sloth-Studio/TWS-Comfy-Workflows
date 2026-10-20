---
type: Evaluation
title: Infra Choir Enhanced Visualizer Full-Song A/B
description: Complete-song performance, synchronization, regression, and visual evidence for the Fill-inspired production enhancement.
status: stable
tags: [infra-choir, visualizer, spectrum, fill-nodes, benchmark]
---
# Infra Choir Enhanced Visualizer Full-Song A/B

Date: 2026-10-13

## Acceptance result

The enhanced renderer completed the full Bella Ciao song at the required
1920x1080 and 16 fps. Visual inspection at 10, 60, 140, and 260 seconds found
the original composition intact, environmental changes bounded to their target
regions, and the bottom spectrum materially finer without becoming dominant.
The new default passed the production acceptance criteria.

## Matched outputs

| Measurement | Existing production | Enhanced production |
| --- | ---: | ---: |
| Frames | 4,598 | 4,598 |
| Resolution / fps | 1920x1080 / 16 | 1920x1080 / 16 |
| Container duration | 287.375 s | 287.375 s |
| Audio | AAC stereo, 48 kHz | AAC stereo, 48 kHz |
| End-to-end renderer | 843.93 s | 860.76 s |
| Audio analysis | 1.09 s | 9.52 s cache miss; 0.135 s subsequent hit |
| Peak process + FFmpeg RAM | 2,566,873,088 bytes (2.39 GiB) | 2,589,437,952 bytes (2.41 GiB) |
| Observed total GPU memory | 3,325 MiB | 3,310 MiB |
| Output size | 40,835,389 bytes | 44,464,676 bytes |

The enhanced pass was 16.82 seconds, or 1.99%, slower end to end. Peak tracked
RAM increased by 22.6 MB. GPU readings include the already-running Desktop and
semantic detector; the renderer itself executes on CPU and performs no model
offloading. The decoded audio MD5 is identical for A and B:
`cf708054c965af907047cbbf3fdf139b`.

## Analysis evidence

The enhanced cache contains 4,598 × 256 spectrum values. Low, mid, high,
kick, snare, hi-hat, onset, and phrase envelopes all have non-zero temporal
variance. Kick/hi-hat correlation is 0.286 and low/high energy correlation is
0.360, providing independent rather than synchronized control signals.

The high-resolution frame uses 256 direct STFT band reductions; it does not
interpolate the legacy 24 bands. At 60 seconds, visual inspection clearly shows
individual narrow spectral peaks and restrained peak markers where the legacy
side shows broad blocks. Attack/release smoothing prevents single-frame jitter.

## Regression and safety

- The original production workflow was not overwritten.
- A four-second master-disabled enhanced render and the original baseline had
  identical decoded video MD5 `ee61a3f68104dded87844324001bc959`
  and audio MD5 `dced52a7315fe74a243f7d01465f29d4`.
- Both full outputs contain exactly 4,598 video frames and finish at the same
  audio-aligned container duration; there are no chunk boundaries because the
  renderer streams one continuous timeline.
- The smoke and full runs preserved generated title cards, seven reviewed
  target masks, procedural motion, audio mux, and atomic `.part.mp4` promotion.
- Unit checks cover cache reuse, 128-band output, normalized signal bounds,
  envelope shaping, section overrides, and bottom-only EQ drawing.

## Artifacts

Local ignored comparison outputs are under
`D:\comfyDesktop\output\infra_choir_enhanced_validation`. They include
`baseline_full_00001_.mp4`, `enhanced_full_00001_.mp4`, smoke renders, the JSON
benchmark report, and early/middle/late inspection sheets.

## Limitations

Instrument and vocal energy are low-cost spectral proxies rather than separated
stems. Static contact frames prove composition and spectrum detail but cannot
fully communicate motion quality. Representative early, middle, and late
frames and the dedicated EQ crop were visually inspected for composition,
restraint, and obvious boundary failures; the complete stream was decoded and
probed for duration, frame count, and audio integrity, but was not watched
continuously in real time. Concurrent existing ComfyUI activity made this A/B
slower than earlier isolated 720p/8 fps validation, without causing memory
growth or synchronization failure.
