---
type: Operations Guide
title: Installed Models, Curated Workflows, and Findings
description: Verified local dependency inventory and the current operating conclusions for the curated ComfyUI workflows.
status: stable
tags: [operations, inventory, models, workflows, findings]
---
# Installed Models, Curated Workflows, and Findings

Verified on 2026-10-08. This records project-relevant dependencies, not every
model or personal workflow present in the live ComfyUI data directory. Model
binaries remain excluded from Git.

## Installed model assets

The active Comfy Desktop model-path configuration checks the shared model root
before the repository-local `models/` directory. `<user>` below denotes the
Windows profile name and is not part of the repository contract.

| Purpose | Installed asset | Verified size | Location |
| --- | --- | ---: | --- |
| Wan 2.2 S2V diffusion | `wan2.2_s2v_14B_fp8_scaled.safetensors` | 15.27 GiB | `C:\Users\<user>\ComfyUI-Shared\models\diffusion_models` |
| Wan text encoder | `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | 6.27 GiB | `C:\Users\<user>\ComfyUI-Shared\models\text_encoders` |
| Wan VAE | `wan_2.1_vae.safetensors` | 0.24 GiB | `C:\Users\<user>\ComfyUI-Shared\models\vae` |
| S2V audio encoder | `wav2vec2_large_english_fp16.safetensors` | 0.59 GiB | `C:\Users\<user>\ComfyUI-Shared\models\audio_encoders` |
| Four-step Wan acceleration LoRA | `wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors` | 1.14 GiB | `C:\Users\<user>\ComfyUI-Shared\models\loras` |
| Semantic target discovery | `CIDAS/clipseg-rd64-refined`, revision `999e0328d9e10b484360c477313983f9afdd7050` | 0.56 GiB weights; approximately 577 MiB snapshot | `<ComfyUI>\models\detection\clipseg-rd64-refined` |

The five Wan assets and publisher URLs are declared in
`assets/wan-s2v-models.json`. `scripts/install-wan-s2v-assets.ps1 -ListOnly`
previews their destinations without downloading. The CLIPSeg snapshot is
declared by `scripts/install_visualizer_semantic_assets.py`; workflow execution
loads it with `local_files_only=True` and never downloads weights.

No AI upscaler, SAM/SAM2 segmenter, or separate sparkle model is required by
the curated workflows. FFmpeg Lanczos performs delivery scaling, painted masks
remain the precision fallback, and the wordmark sparkle is procedural NumPy.

## Curated workflows

Only the following workflow files are tracked by this repository:

| Workflow | Status and role |
| --- | --- |
| `music_visualizer_target_builder_semantic.json` | Current five-lane semantic target workflow. Uses local CLIPSeg with heuristic fallback, optional painted corrections, per-lane **Reset saved mask**, explicit procedural motion, streamed full-song rendering, static badging, and cheap wordmark sparkle. |
| `music_visualizer_target_builder.json` | Fixed model-free target workflow retained in place. Uses color/texture proposals and the same review/configuration/render contract without loading CLIPSeg. |
| `music_visualizer_local_composite.json` | Accepted fixed six-region CPU/NumPy compositor reference; no generative model or camera motion. |
| `video_wan2_2_14B_s2v_motion_poster_guided.json` | Recommended production Wan motion-poster workflow; one generated variant is the quality default. |
| `video_wan2_2_14B_s2v_motion_poster_visualizer.json` | Deferred audio-reactive logo-spectrum experiment; coherent but too visually dominant for the current lower-right placement. |
| `video_wan2_2_14B_s2v_motion_loop.json` | Advanced short-loop asset and diagnostic workflow. |
| `video_wan2_2_14B_s2v.json` | Upstream/source Wan S2V graph consumed by builders. |
| `video_wan2_2_14B_s2v_auto_duration.json` | Early native full-song continuation experiment; not a production entry point. |
| `video_wan2_2_14B_s2v_auto_duration_windowed.json` | CPU-windowed continuation experiment with unresolved long-run memory pressure. |

Personal song workflows, unsaved graphs, source media, generated videos, temp
previews, and general `user/` state are intentionally not repository content.

## Findings that affect operation

- The accepted Wan delivery path is native 1024×576 exact 16:9 generation,
  followed by deterministic FFmpeg Lanczos scaling to 1920×1080. An AI
  upscaler is neither installed nor required.
- A single Wan variant preserves detail and lighting best. The tested
  three-variant crossfade stayed operationally stable but introduced obvious
  blend blur and suppressed flicker.
- Wan can deform embedded lettering and small or off-center faces. Add text and
  studio branding after generation; prefer source art with important faces
  large and central, or protect them with explicit regional/static masks.
- The procedural target renderer begins every frame from the unchanged source,
  changes only verified masks, and streams frames to FFmpeg. This keeps memory
  bounded and avoids global camera drift.
- `mask_verified` is an inclusion toggle. Unverified or empty lanes are skipped
  when another usable target exists; five complete lanes are the curated UI
  maximum rather than a renderer limit.
- A saved Mask Editor correction intentionally overrides later detector
  proposals for the same source. Use **Reset saved mask** and queue once when
  starting a fresh same-source discovery.
- CLIPSeg improved Bella Ciao detection for hair and red fabric. `flag` still
  confuses scarf fabric, and `sun` selects the broader sunset glow rather than
  the disk, so semantic detection remains provisional and requires review.
- Full-frame `smoke` is unreliable. Crop-first inference with
  `box .40 .18 .72 .62` and the unqualified `smoke` query successfully selected
  the intended pale background plumes because constrained smoke queries expand
  across white, gray, and black variants.
- Spatial motion is controlled by `motion_type` plus `on_beat_motion` and
  `off_beat_motion`; flicker controls do not move pixels. `billow` is the
  preferred established treatment for smoke, while `sway` anchors fabric or
  flames and `still` provides lighting-only animation.
- The wordmark sparkle is a short deterministic glint clipped to the wordmark
  alpha about every six seconds. `wordmark_sparkle_strength=0` disables it; the
  default `0.70` adds no model load and no target-lane cost.
