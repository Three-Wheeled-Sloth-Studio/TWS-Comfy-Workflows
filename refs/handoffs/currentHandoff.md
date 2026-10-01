---
type: Handoff
title: Current Handoff
description: Current Wan S2V long-song implementation state, runtime evidence, known gap, and next diagnostic slice.
status: draft
tags: [handoff, comfyui, wan, gpu-memory]
---
# Current Handoff

## Accepted Baseline

The source Wan 2.2 14B S2V workflow generated only fixed 77-frame segments. The automatic-duration workflow calculates target frames from the entire audio and uses native StartLoop/EndLoop expansion. The current target is full-song, minimally animated 16:9 video on an RTX 4070 with 12 GB VRAM; overnight runtime is acceptable.

## What Landed

- Added automatic audio-duration planning and continuation-loop generation.
- Added CPU-backed continuation state with a 19-latent-frame motion tail.
- Reused reference-image conditioning from the initial pass so the VAE no longer runs between extensions.
- Defaulted the current workflow to 832×480 and removed empty lower-template groups from the saved file.
- Added a deny-by-default Git repository boundary, reproducible deployment/model scripts, and Agent Academy refs.

## Current Evidence Or Gap

On 2026-10-01 an 832×480 run started at 09:37. The VAE prepared only once, proving cached-reference conditioning landed. Initial generation took 1:40 and early extensions stayed near 1:53. Extensions 12–17 rose to approximately 2:01, 2:02, 3:04, 2:46, 2:59, and 3:42. Extension 18 then took 10:15. At 10:39 extension 19 was still running; NVIDIA reported 11,797 MiB used and 214 MiB free. No OOM or driver error had occurred yet, but progressive pressure and offloading slowdown clearly remained.

An earlier implementation failed around iteration 20/21 with a graceful PyTorch CUDA OOM. Windows also previously recorded an unrelated NVIDIA `nvlddmkm` watchdog/bugcheck while using the Game Ready driver; the machine now uses Studio driver 616.92.

## Next Slice

Capture the current run outcome. If GPU pressure persists or OOM recurs, instrument allocated/reserved/free memory after each loop body and determine which dynamically expanded ComfyUI outputs remain live. Prefer a disk-backed external chunk runner or separate prompt per chunk if native loop caching cannot release iteration state safely.

## Required Reads For Next Slice

- `custom_nodes/comfyui_audio_duration_plan/__init__.py`: inspect continuation state, conditioning creation, and cache cleanup.
- `build_auto_s2v_windowed_workflow.py`: inspect the native loop graph and per-iteration node outputs.
- `refs/planning/decisions.yaml`: preserve accepted repository and continuity decisions.
- Current ComfyUI log entries from the active prompt: establish whether the run crossed iteration 21 or failed.

## Relevant Files

- `user/default/workflows/video_wan2_2_14B_s2v_auto_duration_windowed.json`
- `custom_nodes/comfyui_audio_duration_plan/__init__.py`
- `build_auto_s2v_windowed_workflow.py`
- `refs/planning/todos.yaml`

## Do Not Reopen

- Do not return to concatenating the progressively complete latent inside each GPU loop iteration.
- Do not re-encode the unchanged reference image with the VAE on every extension.
- Do not treat models, input media, outputs, logs, or general ComfyUI user configuration as repository content.

## Validation

Python compilation, serialized workflow link validation, CPU-state concatenation tests, and cached reference extraction tests passed before this handoff. A complete long-song generation and final tiled decode have not yet passed.
