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
lane follows **Detect Animation Target → Preview Image → Configure Animation
Target → Add Animation Target**. Enter an object class, inspect the green
preview, refine `search_area`/sensitivity or replace the mask if necessary,
then enable `mask_verified`. Describe the desired motion in the prompt and mix
beat-driven versus autonomous motion with `on_beat_strength` and
`off_beat_strength`. To add a target, duplicate those four nodes, connect the
new stack node to the previous stack output, and route the final stack to the
renderer. The renderer refuses to run with an unverified or empty mask.

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
`Detect Animation Target` uses green for selected pixels; `Local Visualizer
Region Mask` and the interactive mask editor normally use red. Both colors mean
“included in the mask and eligible for animation.” A faint colored edge is the
feathered transition. Depending on the editor's preview mode, unselected areas
may be darkened to make the mask easier to see. Painting in add mode includes
pixels; erasing or subtract mode removes them. Saving the editor updates the
mask, not the underlying image.

Use a broad `search_area` only to limit detection. For precise corrections,
paint or define small mask islands around the missed object parts—for example,
tight ellipses around candle flames—and connect that `MASK` output to a
`Configure Animation Target`. A separate target for missed objects is often
safer than lowering sensitivity until unrelated papers, reflections, or walls
also become animated. Avoid overlapping the original mask unless the doubled
effect is intentional.

## Workflow selection

| Workflow | Role |
| --- | --- |
| `music_visualizer_target_builder.json` | Generic repeatable detect/verify/prompt/beat-mix target workflow; model-free detector proposals. |
| `music_visualizer_local_composite.json` | Standalone lightweight regional compositor; no model or camera motion. |
| `video_wan2_2_14B_s2v_motion_poster_guided.json` | Recommended production workflow. |
| `video_wan2_2_14B_s2v_motion_poster_visualizer.json` | Deferred logo-spectrum experiment; coherent, but currently too visually dominant for the lower-right brand position. |
| `video_wan2_2_14B_s2v_motion_loop.json` | Advanced 832x480 short-loop asset and diagnostic workflow. |
| `video_wan2_2_14B_s2v.json` | Upstream/source graph used by the workflow builders. |
| `video_wan2_2_14B_s2v_auto_duration.json` | Early native full-song loop experiment, not a production entry point. |
| `video_wan2_2_14B_s2v_auto_duration_windowed.json` | CPU-windowed continuation experiment with unresolved long-run memory pressure. |

The manifest-driven scripts under `scripts/` are a reproducible diagnostic and
automation path. Ordinary guided use does not require them.
