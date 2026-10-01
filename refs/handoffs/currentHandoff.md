---
type: Handoff
title: Current Handoff
description: Current music-video implementation state and the accepted hybrid motion-poster production direction.
status: draft
tags: [handoff, comfyui, music-video, motion-poster, wan]
---
# Current Handoff

## Accepted Baseline

The product need is intentionally modest: create a full-song 16:9 video in which the supplied artwork is not completely static and every visible motion makes semantic sense. Beat synchronization and lyric overlays are desirable but optional. Overnight runtime is acceptable, but unconstrained generative motion is not required.

The source Wan 2.2 14B S2V workflow generated only fixed 77-frame segments. The automatic-duration workflow calculates target frames from the entire audio and uses native StartLoop/EndLoop expansion. That work remains useful for producing short motion assets and as an experimental full-song path, but it is no longer the preferred production architecture on the 12 GB RTX 4070.

## What Landed

- Added automatic audio-duration planning and continuation-loop generation.
- Added CPU-backed continuation state with a 19-latent-frame motion tail.
- Reused reference-image conditioning from the initial pass so the VAE no longer runs between extensions.
- Defaulted the current workflow to 832×480 and removed empty lower-template groups from the saved file.
- Added a deny-by-default Git repository boundary, reproducible deployment/model scripts, and Agent Academy refs.

## Current Evidence Or Gap

On 2026-10-01 an 832×480 run started at 09:37. The VAE prepared only once, proving cached-reference conditioning landed. Initial generation took 1:40 and early extensions stayed near 1:53. Extensions 12–17 rose to approximately 2:01, 2:02, 3:04, 2:46, 2:59, and 3:42. Extension 18 then took 10:15. At 10:39 extension 19 was still running; NVIDIA reported 11,797 MiB used and 214 MiB free. No OOM or driver error had occurred yet, but progressive pressure and offloading slowdown clearly remained.

An earlier implementation failed around iteration 20/21 with a graceful PyTorch CUDA OOM. Windows also previously recorded an unrelated NVIDIA `nvlddmkm` watchdog/bugcheck while using the Game Ready driver; the machine now uses Studio driver 616.92.

The progressive slowdown shows that full-song Wan continuation is solving a substantially harder problem than the actual product requires. It also risks cumulative semantic drift, late-run failure, and loss of an overnight run. Do not make completion of a full-song native Wan loop a prerequisite for the production pipeline.

## Accepted Production Direction

Build a hybrid, manifest-driven **motion-poster renderer**:

1. Use ComfyUI to prepare reusable assets rather than every final frame: one or more subtle 6–12 second Wan motion clips, semantic masks, and optionally a depth map.
2. Render the complete song with a dedicated Python/FFmpeg pipeline that streams frames or encoded segments to disk, matches the audio duration exactly, and uses constant memory.
3. Combine restrained camera drift, depth parallax, seamless loop treatment, crossfades, and masked effects. Effects must be attached to plausible regions: for example light or neon glow, flame flicker, smoke/fog drift, water shimmer, sky movement, particles, or subtle hair/fabric motion. Never apply arbitrary whole-image pulsing merely because a beat exists.
4. Optionally analyze beat/onset strength and drive only small, smoothed changes to appropriate effects, such as light intensity, particle activity, or a roughly 1% camera pulse.
5. Optionally accept timed `.lrc`, `.srt`, or `.ass` lyrics and composite them during final assembly. Begin with tasteful line-level text; karaoke-style word highlighting can be a later enhancement.
6. Continue generating at a practical working resolution such as 832×480 and upscale the assembled, temporally stable video to 720p or 1080p afterward.

The first proof should be deliberately narrow: take a successful short Wan clip, construct a seamless ping-pong/crossfade loop without duplicated endpoint frames, add slow camera drift, repeat it to the exact song duration, mux the original audio, and emit one playable 16:9 video. A second short variant can then be introduced for chorus/section changes if repetition is conspicuous.

## Next Slice

Prototype the hybrid renderer as repository-owned scripts and a small per-song manifest. A proposed input layout is:

- source image and original audio;
- optional short loop clips;
- optional semantic masks and depth map;
- optional timed lyrics file;
- render settings for duration/FPS/output size, camera path, loop ordering, transitions, masked effects, and beat response.

The proof is complete when it renders a full song with bounded memory, exact-duration audio/video, smooth loop boundaries, and visibly sensible motion. Preserve the current Wan workflow, but defer deeper loop-memory investigation unless the hybrid result cannot meet the visual bar or the user explicitly returns to full-song generative continuation.

## Required Reads For Next Slice

- `refs/handoffs/currentHandoff.md`: authoritative scope, visual constraints, and proof-of-concept acceptance criteria.
- `refs/planning/decisions.yaml`: preserve the accepted hybrid production direction and low-resolution/upscale decision.
- `refs/implementation/dependencyPolicy.md`: check before introducing Python or media-processing dependencies.
- The selected short Wan output and its reference image/audio: inspect only when beginning the proof so transition and motion choices reflect the actual artwork.

## Relevant Files

- `user/default/workflows/video_wan2_2_14B_s2v_auto_duration_windowed.json`
- `custom_nodes/comfyui_audio_duration_plan/__init__.py`
- `build_auto_s2v_windowed_workflow.py`
- `refs/planning/todos.yaml`
- `refs/planning/roadmap.yaml`

## Do Not Reopen

- Do not return to concatenating the progressively complete latent inside each GPU loop iteration.
- Do not re-encode the unchanged reference image with the VAE on every extension.
- Do not treat full-song Wan continuation as the default production path or block the hybrid prototype on resolving its late-loop slowdown.
- Do not animate arbitrary regions from audio amplitude alone. Motion must be associated with a plausible object, material, atmosphere, or camera move.
- Do not treat models, input media, outputs, logs, or general ComfyUI user configuration as repository content.

## Validation

Python compilation, serialized workflow link validation, CPU-state concatenation tests, and cached reference extraction tests passed before this handoff. A complete long-song generation and final tiled decode have not yet passed.

No hybrid renderer exists yet. Its initial validation must include exact output duration, audio preservation, bounded RAM/VRAM use, no visible hitch at loop seams, and a manual check that all animation is semantically appropriate for the source artwork.

## Notes For Next Agent

Favor a small, inspectable script over another large Comfy graph for final assembly. ComfyUI remains valuable for generating short clips, masks, and depth assets; conventional rendering is better suited to deterministic full-song duration, resumability, subtitles, and progressive disk output. Keep the manifest simple enough that a user can identify the glowing/moving region and select an effect without editing code.
