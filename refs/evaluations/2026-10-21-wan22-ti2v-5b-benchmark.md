---
type: Evaluation
title: Wan 2.2 TI2V 5B Local Benchmark
description: Fixed-seed native ComfyUI benchmark of the official 5B image-to-video model on the studio RTX 4070.
status: stable
tags: [evaluation, wan, ti2v, video, performance, motion]
---
# Wan 2.2 TI2V 5B Local Benchmark

## Scope

Test whether Wan 2.2 TI2V 5B is a practical replacement for the two-stage Wan
2.2 S2V 14B motion generator on the local RTX 4070 12 GB system. The source was
read from the current saved generic workflow at test time:
`The Logo and the Maw - banner.png` (1672x941). This is benchmark input, not a
production default.

The graph used only native ComfyUI nodes with the official Comfy-Org FP16 5B
transformer, Wan 2.2 VAE, and the already-installed FP8 UMT5 encoder. It was
image-conditioned only. Audio-reactive lighting, title, EQ, branding, and final
audio deliberately remain downstream compositor responsibilities.

## Results

| Gate | Settings | Wall time | Result |
| --- | --- | ---: | --- |
| Load/smoke | 832x480, 17 frames, 4 steps, 24 fps | 25.60 s | Passed; model load, sampling, decode, and H.264 save completed. |
| Quality | 832x480, 81 frames, 20 steps, 24 fps | 85.22 s | Passed; strong motion, but the unconstrained prompt produced overly pale fog. |
| Production-shaped | 1024x576, 77 frames, 20 steps, 16 fps | 129.84 s | Passed; darker atmospheric treatment, stable framing, 4.8125-second H.264 clip. |

The production-shaped output is:

`D:\comfyDesktop\output\infra_choir\tests\wan22_ti2v5b_production_gate_1024x576_77f_20step_00001_.mp4`

It contains 77 frames at 1024x576 and 16 fps. Regional temporal luma ranges
were 38.50 for clouds, 35.84 for platform fog, 64.65 for water, 34.82 for the
banner region, and 95.20 for the foreground sea structure. These are motion
measurements, not subjective quality scores.

Whole-frame adjacent phase correlation found 0.258 px maximum horizontal
translation, 0.595 px maximum vertical translation, 0.145 px median vertical
translation, and 0.430 px vertical 95th percentile, with minimum correlation
response 0.916. There is no evidence of the prior periodic approximately
10-pixel vertical screen jump.

## Model assets

- `D:\comfyDesktop\models\shared\diffusion_models\wan2.2_ti2v_5B_fp16.safetensors`
  - 9,999,658,848 bytes
  - SHA-256 `456f901338bd9eadbded3828b819109a9b68e8a525ca5cf8d0049a69fcfeca1e`
- `D:\comfyDesktop\models\shared\vae\wan2.2_vae.safetensors`
  - 1,409,400,960 bytes
  - SHA-256 `e40321bd36b9709991dae2530eb4ac303dd168276980d3e9bc4b6e2b75fed156`

Both hashes match the official Hugging Face linked ETags. The active model
tree exposes them through same-volume hard links, so there is no duplicate
binary allocation.

## Decision and remaining gate

Wan 2.2 TI2V 5B is practical on this installation and is preferred over S2V
14B and VACE 1.3B for generic artwork motion. The recommended architecture is:

1. Generate and save one short image-conditioned motion clip.
2. Construct a measured no-jump loop or sequence from that persisted clip.
3. Apply music-synchronized lighting, title, EQ, branding, and final audio in
   the deterministic full-song compositor.

This benchmark did not modify the user-arranged workflow and did not prove an
end-to-start loop. The next implementation must be a separately reviewed,
generic workflow revision and must not write benchmark media, prompts, or
track-specific values back into the live workflow.

## 2026-10-22 integration follow-up

The separate generic integration now exists at
`user/default/workflows/music_visualizer_ti2v5b_full.json`. Its builder reads
but never writes `music_visualizer_cached_motion_full.json`, removes only nodes
tagged as the older Wan generation stage, and preserves the current image,
audio, compositor widgets, and retained-node positions. A new project-owned
output node atomically persists the decoded short motion clip before forwarding
the identical IMAGE batch to the full-song renderer. Focused tests verify graph
wiring, zero compositor stabilization, preserved user state, and a real tiny
H.264 persistence pass. Subjective full-song review remains open.

The first integrated fixed-seed run used `20261021` and progressively darkened,
so it was rejected. The builder now uses the previously accepted benchmark seed
`22102026` and explicitly protects source exposure/contrast against fade or
drift. The repeat completed in 137.53 seconds and atomically saved
`ti2v5b_integrated_persist_gate_accepted_seed_00001_.mp4` with 77 frames at
1024x576/16 fps. Contact-frame review retained scene exposure while showing
strong atmospheric, water, banner, and foreground organic motion. Its maximum
adjacent vertical phase shift was 0.271 pixels. The compositor's 13-frame loop
overlap produced a simulated boundary luma change of 7.38 against a 6.83 median
ordinary adjacent change, so the loop boundary is within ordinary motion scale.

## User review

The subsequent full workflow run was accepted as production-workable. The
workstation remained responsive, runtime was reasonable, cloud/smoke/fog motion
was very dynamic, and music-synchronized lighting behaved appropriately. Wave
motion was somewhat aggressive, but can be tuned through the behavioral prompt.
Future evaluation may spend more time or frames on a longer motion asset, but
must first instrument generation, lighting/compositing, and encoding separately;
the user's initial subjective impression was that downstream lighting and
composition occupied most of the run time.
