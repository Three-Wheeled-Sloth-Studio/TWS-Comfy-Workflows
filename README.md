# TWS Comfy Workflows

Three-Wheeled Sloth Studio's curated ComfyUI workflows, project-owned custom nodes, reproducible setup utilities, and durable agent context.

This Git worktree intentionally lives at the root of a working ComfyUI data directory. Its `.gitignore` is deny-by-default: models, inputs, outputs, temporary files, virtual environments, user-specific configuration, logs, caches, and third-party custom nodes are excluded. A repository validation script rejects forbidden tracked paths as a second safety layer.

## Current workflow

The active production direction is a bounded-memory hybrid motion-poster renderer,
with Wan 2.2 S2V retained for preparing short reusable motion clips:

- `user/default/workflows/video_wan2_2_14B_s2v.json` — source workflow.
- `user/default/workflows/video_wan2_2_14B_s2v_auto_duration.json` — first loop-based duration adaptation.
- `user/default/workflows/video_wan2_2_14B_s2v_auto_duration_windowed.json` — current CPU-state/windowed continuation experiment.
- `user/default/workflows/video_wan2_2_14B_s2v_motion_loop.json` — short native 832×480 motion-asset workflow with conservative anti-lip-sync defaults.
- `custom_nodes/comfyui_audio_duration_plan/` — duration planning and continuation-state nodes.
- `scripts/render_motion_poster.py` — deterministic full-song FFmpeg assembly.
- `assets/motion-poster.example.json` — per-song input, loop, camera, and output settings.

The Wan experiment generates 77-frame chunks at 16 fps, defaults to 832×480,
keeps completed latents in system RAM, and reuses a 19-latent-frame motion window.
The production path turns reviewed short clips into closed, crossfaded
ping-pong cycles, applies restrained camera drift, streams them for the source
audio duration, and writes a native-frame H.264/AAC result without retaining
the song's frames in memory.

## Render a motion poster

Edit a copy of `assets/motion-poster.example.json` with the source audio,
reference image(s), concrete motion guidance, negative prompt, desired number
of loop variants, and ignored `output/` destination. Paths are relative to the
manifest.

```powershell
python scripts/render_motion_poster.py assets/motion-poster.example.json --check-manifest
python scripts/build_motion_loop_workflow.py `
  --manifest assets/motion-poster.example.json `
  --output user/default/workflows/motion_poster_active.json
```

Open `motion_poster_active.json` in ComfyUI. It generates one roughly 9.5-second
832×480 asset per queue run. Review each result and queue new seeds until the
requested number of variants preserve the face, mouth position, composition,
and identity. Point the manifest's `loops` entries at the accepted outputs,
then assemble the full song:

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
