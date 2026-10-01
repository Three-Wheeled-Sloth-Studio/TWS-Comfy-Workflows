# TWS Comfy Workflows

Three-Wheeled Sloth Studio's curated ComfyUI workflows, project-owned custom nodes, reproducible setup utilities, and durable agent context.

This Git worktree intentionally lives at the root of a working ComfyUI data directory. Its `.gitignore` is deny-by-default: models, inputs, outputs, temporary files, virtual environments, user-specific configuration, logs, caches, and third-party custom nodes are excluded. A repository validation script rejects forbidden tracked paths as a second safety layer.

## Current workflow

The primary interface is a guided ComfyUI graph that generates short Wan 2.2
S2V variants and assembles a full-song motion poster in one queue operation:

- `user/default/workflows/video_wan2_2_14B_s2v_motion_poster_guided.json` — primary guided workflow.
- `custom_nodes/comfyui_audio_duration_plan/motion_poster_nodes.py` — guidance, variant planning, and full-song assembly nodes.
- `user/default/workflows/video_wan2_2_14B_s2v.json` — source workflow.
- `user/default/workflows/video_wan2_2_14B_s2v_auto_duration.json` — first loop-based duration adaptation.
- `user/default/workflows/video_wan2_2_14B_s2v_auto_duration_windowed.json` — current CPU-state/windowed continuation experiment.
- `user/default/workflows/video_wan2_2_14B_s2v_motion_loop.json` — advanced short-asset workflow.
- `scripts/render_motion_poster.py` and `assets/motion-poster.example.json` — reproducible CLI diagnostic path.

The Wan experiment generates 77-frame chunks at 16 fps, defaults to 832×480,
keeps completed latents in system RAM, and reuses a 19-latent-frame motion window.
The guided path turns one to three generated variants into closed, crossfaded
ping-pong cycles, applies restrained camera drift, streams them for the source
audio duration, and writes an H.264/AAC result without retaining the completed
song's frames in memory.

## Render a motion poster

The normal path is the guided ComfyUI workflow:

`user/default/workflows/video_wan2_2_14B_s2v_motion_poster_guided.json`

After installing or updating this repository, restart Comfy Desktop once so it
loads the project-owned custom nodes. Then open the guided workflow and:

1. Choose the reference image and song in **Load Image** and **Load Song**.
2. Edit the positive and negative prompts in **Motion Poster Guidance**. The
   supplied preservation and anti-lip-sync defaults are ordinary editable text;
   leave lip motion disabled unless it is deliberately wanted.
3. Choose one to three variants in **Motion Poster Variant Seeds**. The base
   seed randomizes after each queued run by default; select `fixed` when a run
   must be reproduced exactly.
4. Set optional camera/crossfade controls in **Assemble Full Motion Poster**.
   Camera zoom `1.0` is neutral and camera drift defaults to zero. When changing
   songs, update the adjacent song-title field used for output naming.
5. Optionally choose transparent PNGs in **Brand Logo** and **Wordmark**. Enable
   them independently in the assembler: the logo is placed subtly at lower
   right and the larger wordmark at upper left.
6. Queue the graph once. It generates the variants, closes their seams,
   crossfades them, repeats them to the full audio duration, and saves one MP4.

The final node shows the saved video in ComfyUI. Its filename begins with the
song-title field. No manifest editing or command-line rendering is required for
ordinary use.

ComfyUI reloads widget values from the saved workflow. After selecting media or
editing prompts/lyrics, use **Save As** to create a per-song workflow if those
values should persist without changing the reusable template.

One variant is the quality default. A completed three-variant test stayed within
the GPU/time budget but produced excessive blended blur and largely erased the
lighting flicker; multi-variant transitions remain future work.

### Reproducible CLI path

The manifest and Python scripts remain available for automated testing,
reproduction, and debugging. Edit a copy of
`assets/motion-poster.example.json`, then run:

```powershell
python scripts/render_motion_poster.py assets/motion-poster.example.json --check-manifest
python scripts/build_motion_loop_workflow.py `
  --manifest assets/motion-poster.example.json `
  --output user/default/workflows/motion_poster_active.json
```

The generated `motion_poster_active.json` is the older two-stage diagnostic
workflow. It remains useful when individual loop assets need to be reviewed or
reused before assembly:

```powershell
python scripts/render_motion_poster.py assets/motion-poster.example.json
```

FFmpeg and FFprobe must be available on `PATH`. The renderer uses only the
Python standard library and invokes FFmpeg as a streaming subprocess. Reference
image paths record which artwork the loops derive from. The first image drives the current Wan
workflow; additional references and untimed lyrics are retained as project
context for future conditioning. The renderer refuses non-native aspect ratios
rather than cropping or stretching them, and crossfades any accepted loop
variants into a closed repeating reel.

## Install into another ComfyUI data folder

From a clone of this repository:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-to-comfy.ps1 -ComfyRoot "C:\path\to\ComfyUI"
```

To also download the Wan S2V model set declared in `assets/wan-s2v-models.json`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-to-comfy.ps1 -ComfyRoot "C:\path\to\ComfyUI" -InstallModels
```

Large model downloads are never committed. Run the model installer with `-ListOnly` to inspect destinations and URLs without downloading.

## Agent re-entry

This repository uses the [Agent Academy](https://github.com/Three-Wheeled-Sloth-Studio/Agent-Academy) `refs/` harness. Begin routine work with:

```powershell
python refs/tools/generate_agent_context.py --focus "short task description"
```

The generated packet is orientation, not authoritative project state. Durable status, decisions, risks, validation, and handoff context live under `refs/`.

## Validation

```powershell
python scripts/validate_repository.py
python refs/tools/generate_source_catalog.py --check
python refs/tools/generate_okf_indexes.py --check
python refs/tools/validate_refs.py --mode initialized
python refs/tools/generate_agent_context.py --check
```
