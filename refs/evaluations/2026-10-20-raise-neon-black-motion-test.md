---
type: Evaluation
title: Raise the Neon Black Environmental Motion Test
description: One fixed-seed Wan S2V review of scene-wide environmental motion and downstream hybrid-compositing suitability.
status: stable
tags: [comfyui, infra-choir, wan, motion, evaluation]
---
# Raise the Neon Black Environmental Motion Test

## Inputs and scope

The user explicitly selected `Banner.png` and `Raise the Neon Black.flac` from
the Raise the Neon Black production directory for this test. Verified copies
were placed under Comfy's configured input directory. The 192 kHz FLAC master
was preserved unchanged; an AAC-safe lossless 48 kHz working copy is used by
the saved candidate workflow.

The separately versioned workflow is
`video_wan2_2_14B_s2v_raise_the_neon_black_candidate_v1.json`. It requests
ample smoke/fog motion, wind-driven lead hair and flags, moving waves,
independently wriggling underwater tentacles, restrained secondary motion,
stable lighting for later procedural treatment, and a locked camera/identity.
It does not modify the dual-track scaffold.

## Runtime and save recovery

The 1024x576, two-segment, four-step Wan run completed all generation in
1:25:28 on the RTX 4070 12 GB path. Dynamic model offloading dominated runtime:
the initial sampler took 46:33 and the extension sampler 14:35, with substantial
conditioning/model-load overhead. This resolution is too costly for iterative
prompt discovery; use a lower-resolution proof before future high-resolution
approval renders.

The first save failed after generation because AAC cannot encode the source
master's 192 kHz sample rate. A save-only retry omitted audio from the short
review asset and reused every generated node from cache, completing in about
2.4 seconds. The resulting silent clip was then muxed with a 48 kHz AAC review
track without regeneration. The candidate builder now selects the lossless
48 kHz working FLAC so the failure does not recur when queued normally.

## Result

The review clip is 1024x576, 16 fps, 159 frames, and 9.9375 seconds:

`D:\comfyDesktop\output\infra_choir\motion_assets\raise_the_neon_black_environment_candidate_v1_00001_with_audio.mp4`

Observed result:

- Lead hair and braid visibly stream while the face, head, raised arm, and pose
  remain visually stable.
- The large torn flag waves substantially; smaller flags receive secondary
  motion.
- Surface waves travel and reshape clearly.
- Underwater tentacles receive localized motion, but less than the water.
- Storm clouds and waterline fog evolve, but fog volume is moderate rather
  than the requested ample billowing.
- Buildings and cranes are comparatively stable; secondary motion is not
  overwhelming.
- The extension boundary is clean: adjacent-frame luma change at the join is
  0.93 times the clip's median adjacent-frame change.
- The first and last frames are not a closed loop. Full-song assembly still
  needs the established deterministic loop/crossfade treatment.

The stable composition and deliberately stable practical lights are suitable
for a later procedural, music-synchronized lighting/glow pass and deterministic
title-card overlay. Those layers were not baked into this generative test.

The later full-song hybrid render completed those downstream layers. See
`refs/evaluations/2026-10-20-raise-neon-black-full-render.md`.
