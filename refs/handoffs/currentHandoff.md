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

1. Use one guided ComfyUI graph for the ordinary workflow: choose the primary
   reference image and song, enter motion guidance, choose one to three
   variants, and queue once.
2. Generate short Wan motion assets at the native 832×480 landscape working
   resolution. Never use the earlier square proof or crop/stretch a mismatched
   source into the delivery frame.
3. Give Wan explicit physical motion guidance. Background-only is the safe
   default. Preserve identity, face, expression, mouth position, pose, framing,
   clothing, and composition.
4. Default the negative prompt against lip sync, singing, talking, mouth
   movement, facial drift, scene changes, warping, and whole-image pulsing.
5. Build closed ping-pong cycles, crossfade variants into a closed reel, stream
   it to the exact audio duration, and upscale only afterward. The legacy
   manifest and command-line renderer remain diagnostic/reproducibility tools,
   not the normal user interface.

## What Landed

- `custom_nodes/comfyui_audio_duration_plan/motion_poster_nodes.py` provides
  editable safe prompt construction, deterministic one-to-three variant seed
  planning, song-title-based naming, dual branding overlays, and full-song
  FFmpeg assembly with preview and saved output.
- `user/default/workflows/video_wan2_2_14B_s2v_motion_poster_guided.json` is the
  primary guided workflow. It generates the selected variants and assembles the
  final MP4 in one queue operation; no manifest editing or Python command is
  required for normal use. It exposes one reference-image picker, one audio
  picker, and two optional branding-image pickers; the unrelated square example
  graph inherited from the source JSON is pruned by the builder.
- `scripts/build_guided_motion_poster_workflow.py` deterministically regenerates
  and structurally validates that guided workflow.
- `scripts/build_motion_loop_workflow.py` derives a short two-chunk Wan workflow
  from the source S2V graph. It remains the base graph and an advanced
  diagnostic path, producing roughly 9.5 seconds at 832×480 / 16 fps.
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

The new guided assembler node also passed a direct synthetic three-variant
test. It accepted image tensors and stereo audio through the same interfaces
used by ComfyUI, produced a 160×96 H.264/AAC preview at 8 fps, and matched the
2.000-second test audio exactly. The generated guided graph passed structural
checks for its prompt, seed-list, image-list, audio, and assembler links. A real
Wan run subsequently validated the same path in Desktop.

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

The first real one-variant guided GUI run completed quickly and produced
`output/motion_poster/guided_motion_poster_00001_.mp4`: 832×480 at 16 fps with
a 244.080-second container matching the song. User review found the underlying
animation smooth and the overall result good. Two limitations were observed:
Wan mangles text embedded in the reference art, and the assembler's whole-frame
camera drift is visibly jerky. Text/branding can remain a post-process overlay.
The pan issue is consistent with FFmpeg crop-coordinate quantization: at the
default amplitude/period, ideal movement is substantially below one pixel per
frame, so crop positions hold and then jump.

A follow-up run with horizontal and vertical drift disabled looked materially
better and was accepted as the near-term default. Camera zoom `1.0` is neutral;
zero is not a valid scale. The guided graph now defaults to neutral zoom and
zero drift, names output files from an editable song-title field, exposes
editable positive and negative prompt fields, collapses the linked read-only
conditioning nodes, and removes stale lower-canvas groups and unused subgraph
definitions.
The workflow uses native `LoadAudio` for frontend reliability. A custom loader
was registered successfully by the backend but serialized without a
`class_type` in Desktop, producing an otherwise-unspecified missing-node error
for node 58. Output naming therefore uses a visible song-title field in the
assembler; update it when selecting different audio.

The real three-variant run was operationally successful: increased generation
time remained within tolerance, GPU utilization stayed near 95%, and no heat
problem appeared. It failed the visual quality bar. The transitions looked like
the three variants were layered together, introduced substantial blur, and
smoothed the lighting flicker until it was nearly absent. One variant remains
the default; alternative multi-variant transition strategies are pinned as
future work.

Two independent post-process branding inputs are now available. A transparent
brand logo can be enabled at lower right with a default 12% width and 72%
opacity; a transparent wordmark can be enabled at upper left with a default 35%
width and 95% opacity. Each has separate enable, size, opacity, and margin
controls. FFmpeg applies both after generation, so Wan cannot deform their text
or artwork. A synthetic dual-overlay regression test confirmed upper-left and
lower-right placement plus exact one-second video/audio duration; the user then
validated the branded result visually and accepted it.

`assets/motion-poster.last-call.json` then assembled the complete song at
`output/motion_poster/last_call_for_the_shareholders.mp4`: 3,905 frames,
832×480, 244.080 seconds, H.264/AAC, with a 0.000021-second source-duration
delta. The closed-cycle boundary luma-difference average is 5.23/255. A full
normal-speed subjective playback review is still recommended.

## Current Usage

Restart Comfy Desktop once so it discovers the new project-owned nodes, then
open `video_wan2_2_14B_s2v_motion_poster_guided.json` from the workflow menu:

1. Select the cover art in `Load Image` and the song in `Load Song`.
2. Edit the positive and negative text in `Motion Poster Guidance`; leave lip
   motion disabled. Optional lyrics or theme text can guide the atmosphere.
3. Set `variant_count` in `Motion Poster Variant Seeds`. The base seed defaults
   to `randomize` after each queued run; switch it to `fixed` to reproduce a
   known run. Keep one variant for normal quality; two or three remain
   experimental until their transition blur is fixed.
4. Set optional crossfade/camera controls in `Assemble Full Motion Poster`.
   Zoom `1.0` means no zoom and drift defaults to zero. Update the song-title
   field when changing audio; it is prepended to the output filename.
5. Optionally select transparent PNGs in the lower-right brand-logo loader and
   upper-left wordmark loader, then enable and tune either overlay in the
   assembler.
6. Queue once. The final node previews and saves the full-song MP4.

Variant frames are held in memory only until assembly begins. Full-song
encoding is streamed through FFmpeg and does not retain the completed song's
frames in memory. The older manifest workflow remains documented in `README.md`
for reproducible diagnostics.

The first reference image currently drives Wan. Additional images are retained
as project context but are not yet independently conditioned. Untimed lyrics
may inform atmosphere or a prompt summary; time-specific animation waits for
timing marks.

## Next Slice

Evaluate the 832×480-to-YouTube upscale path when a higher delivery resolution
is needed. Revisit multi-variant transitions later using short transitions,
low-motion cuts, or section-level alternation rather than the current
blur-producing crossfade. Preserve later work for optional beat-aware glow or
lighting accents; beat response must not drive lips, faces, or whole-image
motion.

## Required Reads

- `refs/planning/decisions.yaml`
- `refs/implementation/dependencyPolicy.md`
- `custom_nodes/comfyui_audio_duration_plan/motion_poster_nodes.py`
- `scripts/build_guided_motion_poster_workflow.py`
- `user/default/workflows/video_wan2_2_14B_s2v_motion_poster_guided.json`
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
- Do not make manifest editing or command-line scripts part of ordinary usage.
- Do not track models, input media, outputs, logs, caches, or general user state.
