---
type: Evaluation
title: Wan 2.2 TI2V 5B 121-Frame Long-Loop Gate
description: Controlled longer-duration fork of the accepted generic TI2V 5B workflow.
status: stable
tags: [evaluation, wan, ti2v, video, performance, loop]
---
# Wan 2.2 TI2V 5B 121-Frame Long-Loop Gate

## Scope

The accepted `music_visualizer_ti2v5b_full.json` was treated as user-owned and
preserved at SHA-256
`AFC2FFA9CB51D4178F72CFC51E316B389E66F548B06E7DC8BBC82AD22B2DC0DD`.
The separate `music_visualizer_ti2v5b_long_loop_experiment.json` changes the
Wan latent length from 77 to 121 frames and uses experiment-specific motion and
final-output prefixes. It retains the current artwork, audio, prompts, accepted
seed, 20 steps, CFG 5, 1024x576 resolution, 16 fps, 0.8-second loop overlap,
zero compositor stabilization, lighting, title, EQ, and branding settings.

## Result

The isolated generation/persistence output completed successfully with no node
errors in 233.98 seconds:

`D:\comfyDesktop\output\infra_choir\tests\ti2v5b_121f_long_loop_gate_00001_.mp4`

It is a 7.5625-second, 121-frame, 1024x576, 16 fps H.264 asset. This is 1.57
times the frames and 1.69 times the wall time of the accepted 77-frame live
integration gate (137.53 seconds), which is a moderate near-proportional cost
increase rather than a performance cliff.

Contact-frame review found stable exposure and composition, continued strong
cloud/fog motion, and substantially more time for the atmosphere and foreground
organic forms to develop. Adjacent phase correlation measured 0.098 pixels
maximum absolute vertical shift and 0.022 pixels median absolute vertical shift.

With the production 13-frame overlap, the effective period is 108 frames, or
6.75 seconds. The blended loop-boundary luma change was 3.80; ordinary adjacent
motion had a 2.75 median and 3.76 95th percentile. A two-cycle review file is:

`D:\comfyDesktop\output\infra_choir\tests\ti2v5b_121f_long_loop_blended_preview.mp4`

The preview is 216 frames and 13.5 seconds. The raw end-to-start difference was
larger, so overlap remains necessary.

## Interpretation

The 121-frame setting is the first preferred longer-loop candidate for user
review. Regional temporal range increased from 34.24 to 58.40 in the broad fog
region. Measured water range decreased from 73.93 to 66.09, but this cannot be
attributed solely to frame count: the saved user prompt now explicitly asks for
gentler water and adds subtle crane motion. Runtime scaling remains comparable
because those prompt changes do not materially alter sampler cost.

Do not promote the longer setting over the accepted 77-frame default until the
user reviews the saved clip or blended preview. A later timing pass should
instrument conditioning/model load, sampling, VAE decode, persistence, light
detection, and full-song composition independently.
