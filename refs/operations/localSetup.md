---
type: Operations Guide
title: Local Setup
description: How to install the curated workflows, custom nodes, and Wan S2V assets into a ComfyUI data directory.
status: stable
tags: [operations, local-setup]
---
# Local Setup

## Prerequisites

- A current ComfyUI or ComfyUI Desktop installation with the native Wan S2V
  nodes available.
- Windows PowerShell and Python 3.
- FFmpeg and FFprobe on `PATH`. Confirm with `ffmpeg -version` and
  `ffprobe -version`.
- An NVIDIA GPU suitable for Wan 2.2 S2V. The accepted 1024x576 path was
  validated on an RTX 4070 with 12 GB VRAM; other hardware may require lower
  settings and is not yet characterized.
- Enough free disk space for the five large model assets declared in
  `assets/wan-s2v-models.json`.

## Inspect before installing

From a clone of this repository, preview the file installation without making
changes:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-to-comfy.ps1 `
  -ComfyRoot "C:\path\to\ComfyUI" -WhatIf
```

Inspect model filenames, destinations, and download URLs without downloading:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-wan-s2v-assets.ps1 `
  -ComfyRoot "C:\path\to\ComfyUI" -ListOnly
```

## Install

Install the project-owned custom node and all curated workflows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-to-comfy.ps1 `
  -ComfyRoot "C:\path\to\ComfyUI"
```

Add `-InstallModels` to download the declared Wan S2V model set as part of the
same operation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-to-comfy.ps1 `
  -ComfyRoot "C:\path\to\ComfyUI" -InstallModels
```

The installer places assets in ComfyUI's standard `models/diffusion_models`,
`models/text_encoders`, `models/vae`, `models/audio_encoders`, and
`models/loras` folders. Model binaries, personal media, outputs, and general
ComfyUI user configuration are deliberately not part of this repository.

When the repository already occupies the target ComfyUI data directory, the
installer reports project files as already in place; use the model installer
separately if models are still needed.

## First run

1. Restart the ComfyUI backend or ComfyUI Desktop after installation. A browser
   refresh alone does not load new Python custom nodes.
2. Open
   `user/default/workflows/video_wan2_2_14B_s2v_motion_poster_guided.json`.
3. Replace the intentionally nonexistent `select_*` media placeholders with
   your own reference image, song, transparent logo, and transparent wordmark.
   The two branding effects are optional, but their connected loader nodes
   still need valid image selections when ComfyUI validates the graph.
4. Update `song_name`; it controls the output filename and is not derived from
   the selected audio yet.
5. Leave the accepted defaults at 1024x576, 77 frames, four steps, one variant,
   neutral camera, and `1080p` delivery for the production path.
6. Queue once. The result is written beneath
   `output/motion_poster/<song_name>_guided_motion_poster_*.mp4`.

Use ComfyUI **Save As** for per-song workflow copies. Do not add source media or
rendered output to this repository.

## Local visualizer prototype

The standalone procedural path needs ComfyUI's existing Torch, NumPy, and
Pillow environment plus FFmpeg on `PATH`; it requires no model files. After the
same backend restart, open
`user/default/workflows/music_visualizer_local_composite.json`. Select the
local Managed Decline image and audio to use the tuned prototype masks. For
another song, select any ordinary still and audio file, edit the six normalized region-shape
fields, use the mask preview outputs when tuning them, and queue **Render
Beat-Aware Local Visualizer**. Keep `1080p` for normal delivery; use `720p` for
fast iteration and avoid `source` with very large artwork until the masks and
strengths are accepted.

For a new image, duplicate or retune **Suggest Local Visualizer Regions**, pick
a candidate type, inspect its preview, then connect `candidate_mask` to the
desired renderer slot or copy its normalized boxes into a region-mask node.
Select a transparent track wordmark and studio badge in the two overlay loaders;
their enable, size, opacity, margin, and wordmark-halo controls live on the V3
renderer. Progress is reported during audio analysis and frame rendering.

For arbitrary target stacks, open
`user/default/workflows/music_visualizer_target_builder.json`. Each starter
lane includes **Detect Animation Target → Verify / Edit Detection Mask →
Configure Animation Target → Add Animation Target**. This is the fixed
model-free workflow and always uses the lightweight color/texture detector.

For the next semantic-detection pass, open the separate
`user/default/workflows/music_visualizer_target_builder_semantic.json`. Its
starter lanes use **Detect Animation Target (Semantic)**. Enter an object
class, choose `semantic_or_heuristic`, `semantic_only`, or `heuristic`, inspect
the green review, and refine `search_area`/sensitivity. The default uses local
CLIPSeg when installed and reports when it falls back to color/texture
heuristics. In either workflow, the detector mask is usable immediately. For a
persistent correction, open the review node
itself in Mask Editor, use the first tool (Mask Pen), and press Save; the next
queue automatically uses that lane's painted mask. A correction belongs only
to the source artwork on which it was painted; changing the source clears stale
review state on the next queue. To discard a correction without changing the
source, click **Reset saved mask** and queue once; the node returns to the
latest detector proposal. The semantic starter graph provides five complete
lanes, with unused unverified lanes skipped automatically. Then enable
`mask_verified`. Describe the
desired lighting/appearance behavior in the text field and select spatial
behavior with `motion_type`. Use
`on_beat_flicker` and `off_beat_flicker` for brightness/color modulation, and
`on_beat_motion` and `off_beat_motion` for actual masked-pixel displacement.
All four are linear `0..2` controls: `0` disables that component, `1` is the
designed amplitude, and `2` doubles it. To add a target, duplicate the complete lane, connect the
new stack node to the previous stack output, and route the final stack to the
renderer. Unverified targets remain connected but are skipped, so targets can
be reviewed and enabled incrementally without rewiring the stack. The renderer
also skips verified targets whose detector produced an empty mask, and only
stops when no usable verified target remains.

`motion_type` is the actual motion-shape control. `billow` applies evolving
multi-scale non-rigid deformation and protects a contracted mask boundary;
`sway` anchors the bottom of the mask so flame tips move more than their bases;
`drift` translates coherently; and `still` disables spatial motion while
leaving flicker/pulse active. `auto` chooses among these from simple keywords,
not image understanding. The starter clouds and candles deliberately use
`on_beat_motion=0`: their autonomous motion continues independently while
lighting remains beat responsive.

Detection is constrained by `search_area` before candidates are ranked, and
the verification preview draws that area with a gold outline. Identical source
RGB and detector settings reuse a small in-process result cache; changing the
source, object query, search area, sensitivity, region count, or padding
intentionally runs detection again. The cache resets when ComfyUI restarts.

For small semantic targets, `search_area` is also the inference crop, not only
a final mask boundary. Keep it tight enough that the target remains legible at
the model's input scale. Smoke receives special assistance only in a constrained
crop: plain `smoke` compares white, gray, and black smoke responses. On the
Bella Ciao artwork, `box .40 .18 .72 .62` isolates the pale background plumes
behind the central figures at the default `0.65` sensitivity. Full-frame smoke
still confuses atmosphere with sky and should not be treated as verified.

The optional semantic provider expects its pinned model snapshot at
`models/detection/clipseg-rd64-refined`. Preview the files and destination
without downloading:

```powershell
.venv\Scripts\python.exe scripts/install_visualizer_semantic_assets.py --comfy-root . --list-only
```

For installation, use the repository `.venv`/ComfyUI Python and omit
`--list-only`. The download is approximately 577 MiB. Restart ComfyUI after
installation; the loader is deliberately local-only and never downloads model
files while a workflow is running.

The generic renderer's `wordmark_sparkle_strength` adds a cheap procedural
glint after compositing the wordmark. `0` disables it; the default `0.70` makes
one brief deterministic pass about every six seconds and lightly responds to
high-frequency audio energy. It requires no additional model or mask lane.

### Reading and correcting masks

Region coordinates are normalized to the complete image and use an upper-left
origin:

```text
box x0 y0 x1 y1
```

`x` increases from `0` at the left edge to `1` at the right edge. `y`
increases from `0` at the top edge to `1` at the bottom edge. Therefore:

```text
box 0.00 0.38 0.33 0.80
```

starts at the left edge and 38% down the image, then ends 33% across and 80%
down. It is a search rectangle in the left third of the frame, not a rectangle
measured upward from the lower-left corner. On a 1435×831 image it corresponds
approximately to `x=0..474`, `y=316..665`.

Preview colors are diagnostic overlays and do not recolor the source artwork.
`Detect Animation Target` uses green for automatically selected pixels. In the
current Mask Editor, the first toolbar tool is **Mask Pen**; with black mask
blending it appears to darken the image, but it is writing the mask. The second
tool is **Paint Pen**; its default red strokes modify the RGB paint layer and
are not mask pixels. Use Mask Pen for selection and use Eraser while the Mask
Layer is active to remove selection. Saving commits those mask pixels to the
review node's hidden persistent state.

The detector's gold outline shows `search_area`; it is not part of the mask.
The review node passes the recomputed detector mask through until an edit is
saved. A saved edit then replaces that lane's proposal on later queues without
requiring a separate file selection. If the source artwork changes, the review
node discards the old saved edit, displays the new preview, and falls back to
the new detector mask. For advanced composition, connect an
external mask to `Configure Animation Target.approved_mask`; its
`approved_mask_mode` can `add`, `subtract`, or `replace` the review result.

Use a broad `search_area` only to limit detection. For precise corrections,
paint the full desired target mask on the review node—for example, tight regions
around candle flames. To perform additive or subtractive adjustments, connect
an external mask to the optional `approved_mask` socket and choose the matching
mode. A separate
target for missed objects is often
safer than lowering sensitivity until unrelated papers, reflections, or walls
also become animated. Avoid overlapping the original mask unless the doubled
effect is intentional.

## Workflow selection

| Workflow | Role |
| --- | --- |
| `music_visualizer_target_builder.json` | Generic repeatable detect/verify/prompt/beat-mix target workflow; model-free detector proposals. |
| `music_visualizer_target_builder_semantic.json` | Five-lane semantic copy using optional local CLIPSeg detection with heuristic fallback, per-lane mask reset, and wordmark sparkle. |
| `music_visualizer_local_composite.json` | Standalone lightweight regional compositor; no model or camera motion. |
| `video_wan2_2_14B_s2v_motion_poster_guided.json` | Recommended production workflow. |
| `video_wan2_2_14B_s2v_motion_poster_visualizer.json` | Deferred logo-spectrum experiment; coherent, but currently too visually dominant for the lower-right brand position. |
| `video_wan2_2_14B_s2v_motion_loop.json` | Advanced 832x480 short-loop asset and diagnostic workflow. |
| `video_wan2_2_14B_s2v.json` | Upstream/source graph used by the workflow builders. |
| `video_wan2_2_14B_s2v_auto_duration.json` | Early native full-song loop experiment, not a production entry point. |
| `video_wan2_2_14B_s2v_auto_duration_windowed.json` | CPU-windowed continuation experiment with unresolved long-run memory pressure. |

The manifest-driven scripts under `scripts/` are a reproducible diagnostic and
automation path. Ordinary guided use does not require them.
