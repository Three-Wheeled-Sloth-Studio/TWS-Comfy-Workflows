---
type: Evaluation
title: Raise the Neon Black Full-Song Hybrid Render
description: Production evidence for the cached-motion, title, 2048-band EQ, and localized music-lighting render.
status: stable
tags: [comfyui, infra-choir, music-video, rendering, evaluation]
---
# Raise the Neon Black Full-Song Hybrid Render

## Atmosphere gate

The attempted 640x360, 49-frame Wan cloud/smoke gate failed after 95:45 at
KSampler with `The size of tensor a (23) must match the size of tensor b (22)`.
The selected height is incompatible with this S2V latent layout. More
importantly, the long fixed conditioning and model-offload cost means a reduced
Wan pass is not a cheap iteration path on the RTX 4070 12 GB installation.
The failed workflow remains separate for audit and did not modify the accepted
motion candidate or dual-track scaffold.

A deterministic temporal-motion amplification pass was therefore applied to
the already accepted 1024x576 motion clip. It does not spatially warp pixels;
it magnifies motion already present inside broad cloud and waterline-fog
regions while explicitly protecting the lead character. Compared with the
accepted source clip, measured 75th-percentile optical-flow motion increased
about 18% in the cloud region and 72% in the waterline fog region, while the
face-region measurement was effectively unchanged.

Approved preview:

`D:\comfyDesktop\output\infra_choir\motion_assets\raise_the_neon_black_atmosphere_boost_preview_v3.mp4`

## Full render

The separate workflow
`video_raise_the_neon_black_full_visualizer_v2.json` uses the amplified clip as
a full-frame cached-motion lane. A conservative mask derived from the current
Banner artwork limits music-synchronized glow to bright/emissive practical
lights and reflections. The renderer adds a generated Infra Choir / Raise the
Neon Black title card, a persistent upper-left wordmark, and a genuine
2048-band cyan EQ. The original dual-track scaffold is not read as a mutable
output and is not overwritten.

Output:

`D:\comfyDesktop\output\infra_choir\final\raise_the_neon_black_full_v2_00001_.mp4`

Verified properties:

- H.264 video at 1920x1080, 16 fps, 3,332 frames.
- AAC stereo audio at 48 kHz.
- 208.25-second duration and 325,259,027-byte file size.
- Title card is legible during the opening five seconds; the persistent
  wordmark appears after the title transition.
- The lower-edge 2048-band EQ is present throughout and leaves the artwork
  readable.
- The practical-light mask varies across a 12.46-luma range, confirming a
  visible but bounded music-driven lighting pass.
- Downscaled motion measurement shows fog motion above cloud motion and the
  protected face region effectively static.
- Median adjacent-frame change at cached-clip boundaries is 0.84 times the
  ordinary median; the worst boundary remains below the video's 99th
  percentile of normal adjacent-frame change.

The first `v1` output was rejected after visual review: the compact manual
target adapter discarded its cached-motion fields, so lighting, title, and EQ
were composited over the still artwork. The adapter now forwards the complete
cached-clip contract, with a focused regression covering the path. A direct
eight-second production-path probe loaded 158 motion frames at a 0.959 source
match and measured 4.25 mean adjacent-frame luma change in the artwork region.

The corrected `v2` renderer completed successfully in 28:19. Motion sampling
at 8, 50, 100, 150, and 200 seconds measured 2.33–3.24 mean adjacent-frame
luma change in the artwork region, proving that cached motion remains present
throughout the song rather than only in the short preview. The scaffold stayed
byte-identical at SHA-256
`A7EE372E260DA42B609E068D38443F092C62B92351C8809CF77A0CF61FB93E7E`.
