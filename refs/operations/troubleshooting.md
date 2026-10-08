---
type: Operations Guide
title: Troubleshooting
description: Common setup, workflow, generation, and assembly failure modes with fixes.
status: stable
tags: [operations, troubleshooting]
---
# Troubleshooting

## A custom node appears as `UNKNOWN`

Restart the ComfyUI backend or ComfyUI Desktop, then reopen the workflow. A
browser refresh does not reload Python modules. If the node remains unknown,
confirm that `custom_nodes/comfyui_audio_duration_plan/` exists beneath the
active ComfyUI data root and inspect the startup log for its import error.

## A model is missing from a loader

List the expected assets and destinations:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-wan-s2v-assets.ps1 `
  -ComfyRoot "C:\path\to\ComfyUI" -ListOnly
```

Install the missing assets without committing them to Git. If ComfyUI uses
additional model roots, verify its configured paths and restart after adding a
model.

## A `select_*` input file cannot be found

The committed workflows intentionally contain neutral, nonexistent selectors
instead of studio source media. Choose or upload your own image/audio files in
the titled loader nodes before queueing. Logo and wordmark inputs are optional
and remain disabled by default, but their connected loader nodes still need
valid image selections when ComfyUI validates the graph.

## The MP4 has the wrong song name

Set `song_name` in **Assemble Full Motion Poster** whenever the selected song
changes. The field is deliberately manual for now and does not auto-update from
the audio selector.

## FFmpeg or FFprobe fails

Run `ffmpeg -version` and `ffprobe -version` in the same environment that starts
ComfyUI. Install FFmpeg or correct `PATH` until both commands succeed. The
assembler and CLI renderer depend on these executables.

## A local-visualizer region affects the wrong object

Connect the mask node's `mask_preview` output to a standard preview node, then
tighten its normalized boxes, ellipses, or polygon points. Use `red` for warning
lights/reflections, `warm` for flame cores, or `neutral_bright` for clouds, and
adjust threshold before increasing feathering. Any standard ComfyUI mask may
replace a generated mask connection when a painted or external segmentation is
more precise.

## The local visualizer is slow

Use `720p` while tuning masks and strengths, then switch to `1080p` for the
final render. The workflow is CPU-bound and streams one frame at a time; it does
not consume diffusion-model VRAM. Avoid `source` delivery for a 4K still unless
the additional CPU and encode cost is intentional.

The V3 renderer shows native ComfyUI progress during analysis and per-frame
generation. Low GPU utilization is expected because the current procedural
compositor is CPU/NumPy based; it is not evidence that a model failed to load.

## Candidate-region suggestions select too much

Suggestions are coarse statistical proposals, not semantic segmentation. Raise
`sensitivity`, lower `max_regions`, reduce padding, or choose a more specific
candidate type. Always inspect the preview and correct the generated boxes or
substitute a painted mask before a full-song render.

## CUDA out-of-memory or unacceptable runtime

Return to the accepted guided settings: 1024x576 generation, 77 frames, four
steps, batch size one, and one variant. Close unrelated GPU workloads. Native
full-song continuation workflows remain experimental and can accumulate memory
pressure late in a run; use the guided short-generation plus streaming assembly
path for production.

## Wan invents a face or ignores smoke, lights, or tentacles

Keep `allow_lip_motion` off, preserve the anti-duplicate-face negative prompt,
and describe each existing moving region precisely in `motion_targets`, for
example `left smoke plume — billow slowly; red light bars — pulse locally;
background tentacles — sway in place`. This improves targeting but is not a
guarantee. Reject a seed that invents a face. Regional motion masks or a
protected static foreground are the robust future fix.

## A face is soft or distorted

Review a `source` delivery to distinguish generation damage from delivery
scaling. Lanczos preserves the generated frame but cannot reconstruct a face
Wan already altered. Prefer source artwork where important faces are larger in
frame, and reject unstable seeds.

## Several variants look blurry

Use `variant_count = 1`. The current long crossfade between independently
generated variants can look layered and suppress useful lighting flicker.

## The logo spectrum draws too much attention

Use the primary guided workflow and its static logo. The separate visualizer
workflow passes coherence testing but is intentionally deferred because the
current radial spectrum visually overweights the lower-right corner. Future
tuning should reduce its footprint, contrast, or opacity before promotion.

## Text inside the generated art warps

Prefer textless source artwork. Add titles and logos afterward with the
post-process wordmark and brand-logo inputs, which Wan cannot deform. The
wordmark halo is generated from its alpha channel and can be disabled or
softened in the assembler.

## Framing is cropped or padded unexpectedly

Use true 16:9 source artwork and the accepted 1024x576 generation with `1080p`
delivery. That route scales directly to 1920x1080. `1080p_fill` exists only for
non-16:9 diagnostic inputs and may crop slightly.
