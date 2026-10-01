# TWS Comfy Workflows

Three-Wheeled Sloth Studio's curated ComfyUI workflows, project-owned custom nodes, reproducible setup utilities, and durable agent context.

This Git worktree intentionally lives at the root of a working ComfyUI data directory. Its `.gitignore` is deny-by-default: models, inputs, outputs, temporary files, virtual environments, user-specific configuration, logs, caches, and third-party custom nodes are excluded. A repository validation script rejects forbidden tracked paths as a second safety layer.

## Current workflow

The active development line is Wan 2.2 S2V automatic song-length generation:

- `user/default/workflows/video_wan2_2_14B_s2v.json` — source workflow.
- `user/default/workflows/video_wan2_2_14B_s2v_auto_duration.json` — first loop-based duration adaptation.
- `user/default/workflows/video_wan2_2_14B_s2v_auto_duration_windowed.json` — current CPU-state/windowed continuation experiment.
- `custom_nodes/comfyui_audio_duration_plan/` — duration planning and continuation-state nodes.

The current experiment generates 77-frame chunks at 16 fps, defaults to 832×480, keeps completed latents in system RAM, and reuses a 19-latent-frame motion window. See `refs/handoffs/currentHandoff.md` for current evidence and unresolved GPU-memory behavior.

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
