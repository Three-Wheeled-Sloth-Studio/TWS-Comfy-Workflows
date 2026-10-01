---
type: Handoff
title: Current Handoff
description: Native 16:9 guided Wan loop generation and deterministic multi-loop motion-poster assembly.
status: draft
tags: [handoff, comfyui, music-video, motion-poster, wan]
---
# Current Handoff

## Product Bar

Create a full-song 16:9 video that remains true to supplied artwork, contains
restrained plausible motion, and is engaging enough for a casual YouTube
listener. Cinematic continuity, beat synchronization, and timed lyrics are not
MVP requirements. Obvious failures—especially inaccurate lip sync, invented
mouth motion, identity drift, and damaged composition—are unacceptable.

## Accepted Architecture

1. Generate one or more short Wan motion assets natively at 832×480 from the
   primary reference image and song audio.
2. Give Wan explicit physical motion guidance. Background-only is the safe
   default. Preserve identity, face, expression, mouth position, pose, framing,
   clothing, and composition.
3. Default the negative prompt against lip sync, singing, talking, mouth
   movement, facial drift, scene changes, warping, and whole-image pulsing.
4. Review generated variants before assembly. Reject any clip that violates
   identity, composition, or mouth stability.
5. Build closed ping-pong cycles, crossfade accepted variants into a closed
   reel, stream it to the exact audio duration, and upscale only afterward.

## What Landed

- `scripts/build_motion_loop_workflow.py` derives a short two-chunk Wan workflow
  from the source S2V graph. It outputs roughly 9.5 seconds at 832×480 / 16 fps.
- `user/default/workflows/video_wan2_2_14B_s2v_motion_loop.json` is the curated
  workflow with editable motion guidance and anti-lip-sync defaults.
- The builder accepts a v2 project manifest and can write an ignored active
  workflow with the selected audio, primary image, dimensions, and prompts.
- `assets/motion-poster.example.json` v2 records audio, reference image(s),
  optional untimed lyrics, generation prompts, expected loop variants,
  crossfades, camera drift, and encoding settings.
- `scripts/render_motion_poster.py` accepts one or more loop variants, closes
  each reversal, crossfades variants into a repeating reel, and streams the
  final H.264/AAC output with bounded memory.
- The renderer rejects aspect-ratio mismatches instead of cropping or
  stretching them. The previous 640×640 proof clip is no longer an eligible
  production input.

## Validation Evidence

The earlier square proof established that closed ping-pong looping and exact
audio-duration assembly work, but its crop and unintended lip motion make it
unsuitable as a base asset.

The v2 assembler passed a synthetic three-variant test at 832×480. It produced
192 frames at 16 fps with a 12.000-second video/audio container, crossfaded all
three closed cycles, and reported zero duration delta. A direct regression test
confirmed that a 640×640 loop is rejected with a no-crop/no-stretch error.

On 2026-10-01 Comfy Desktop 0.38.1 was confirmed as the authoritative running
instance on port 8000. Its generated model-path configuration uses
`C:\Users\sloth\ComfyUI-Shared\models` first and the project `models/` directory
second. All five Wan assets are installed in the shared root and visible to the
live loader nodes. The earlier manually launched 0.21.1 backend used a stale
model-path configuration and must not be used as evidence that models are
missing.

The matching `Last Call for the Shareholders.mp3` and 1376×768 cover art in
`input/` are byte-identical to the EcoMoguls originals. Desktop successfully
generated `output/video/motion_loop_16x9_last_call_sample_00001_.mp4`: 159
frames, 832×480, 16 fps, 9.9375 seconds. Contact-sheet review shows preserved
composition and stable mouth/expression with subtle background variation.

`assets/motion-poster.last-call.json` then assembled the complete song at
`output/motion_poster/last_call_for_the_shareholders.mp4`: 3,905 frames,
832×480, 244.080 seconds, H.264/AAC, with a 0.000021-second source-duration
delta. The closed-cycle boundary luma-difference average is 5.23/255. A full
normal-speed subjective playback review is still recommended.

## Current Usage

```powershell
python scripts/build_motion_loop_workflow.py `
  --manifest assets/motion-poster.example.json `
  --output user/default/workflows/motion_poster_active.json
```

Open the generated active workflow and queue it once per desired seed. Keep two
or three good 832×480 outputs, update the manifest loop paths, then run:

```powershell
python scripts/render_motion_poster.py assets/motion-poster.example.json
```

The completed single-loop sample can be reproduced with:

```powershell
python scripts/render_motion_poster.py assets/motion-poster.last-call.json
```

The first reference image currently drives Wan. Additional images are retained
as project context but are not yet independently conditioned. Untimed lyrics
may inform atmosphere or a prompt summary; time-specific animation waits for
timing marks.

## Next Slice

Watch the completed sample at normal speed. If one repeated cycle is too
obvious, generate two additional seeds in Desktop and switch the per-song
manifest to a three-variant reel. Then decide whether automated queue
orchestration, lyric summarization, semantic masks, or upscaling gives the
highest value.

## Required Reads

- `refs/planning/decisions.yaml`
- `refs/implementation/dependencyPolicy.md`
- `scripts/build_motion_loop_workflow.py`
- `scripts/motion_poster_manifest.py`
- `scripts/render_motion_poster.py`
- `assets/motion-poster.example.json`
- `assets/motion-poster.last-call.json`

## Do Not Reopen

- Do not use the square proof clip as the production base.
- Do not crop or stretch mismatched loop assets into the delivery frame.
- Do not make native full-song Wan continuation a production prerequisite.
- Do not infer mouth, body, or whole-image motion from audio amplitude alone.
- Do not track models, input media, outputs, logs, caches, or general user state.
