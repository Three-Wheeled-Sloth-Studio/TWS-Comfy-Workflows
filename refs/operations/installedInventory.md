---
type: Operations Guide
title: Installed Models, Curated Workflows, and Findings
description: Verified local dependency inventory and the current operating conclusions for the curated ComfyUI workflows.
status: stable
tags: [operations, inventory, models, workflows, findings]
---
# Installed Models, Curated Workflows, and Findings

Verified through 2026-10-13. This records project-relevant dependencies, not every
model or personal workflow present in the live ComfyUI data directory. Model
binaries remain excluded from Git.

## Installed model assets

The active Comfy Desktop model-path configuration checks
`D:\comfyDesktop\models\shared` before `D:\comfyDesktop\models\local`. The
repository-local `models/` path is a compatibility junction to the latter.

| Purpose | Installed asset | Verified size | Location |
| --- | --- | ---: | --- |
| Wan 2.2 S2V diffusion | `wan2.2_s2v_14B_fp8_scaled.safetensors` | 15.27 GiB | `D:\comfyDesktop\models\shared\diffusion_models` |
| Wan text encoder | `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | 6.27 GiB | `D:\comfyDesktop\models\shared\text_encoders` |
| Wan VAE | `wan_2.1_vae.safetensors` | 0.24 GiB | `D:\comfyDesktop\models\shared\vae` |
| S2V audio encoder | `wav2vec2_large_english_fp16.safetensors` | 0.59 GiB | `D:\comfyDesktop\models\shared\audio_encoders` |
| Four-step Wan acceleration LoRA | `wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors` | 1.14 GiB | `D:\comfyDesktop\models\shared\loras` |
| LTX 2.5 distilled transformer | `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` | 20.03 GiB | `D:\comfyDesktop\models\local\diffusion_models` |
| LTX 2.5 combined text encoder/projection | `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` | 14.32 GiB | `D:\comfyDesktop\models\local\text_encoders` |
| LTX 2.5 video and audio VAEs | `ltx-2.5-video-vae-bf16.safetensors`; `ltx-2.5-audio-vae-bf16.safetensors` | 1.37 GiB; 0.34 GiB | `D:\comfyDesktop\models\local\vae` |
| LTX 2.3 fast-tier transformer | `ltx-2.3-22b-distilled-1.1-Q2_K.gguf` | 7.94 GiB | `D:\comfyDesktop\models\local\unet` |
| LTX 2.3 text encoder | `gemma_3_12B_it_fp4_mixed.safetensors` | 9.45 GiB | `D:\comfyDesktop\models\local\text_encoders` |
| LTX 2.3 text projection | `ltx-2.3_text_projection_bf16.safetensors` | 2.31 GiB | `D:\comfyDesktop\models\local\checkpoints` |
| LTX 2.3 video and audio VAEs | `LTX23_video_vae_bf16.safetensors`; `LTX23_audio_vae_bf16.safetensors` | 1.45 GiB; 0.36 GiB | `D:\comfyDesktop\models\local\vae` |
| Semantic target discovery | `CIDAS/clipseg-rd64-refined`, revision `999e0328d9e10b484360c477313983f9afdd7050` | 0.56 GiB weights; approximately 577 MiB snapshot | `D:\comfyDesktop\models\local\detection\clipseg-rd64-refined` |

### Yvann audio-reactive workflow assets

The live Desktop data directory also contains the complete model set referenced
by the three `ComfyUI_Yvann-Nodes` 2.1.1 example workflows. These third-party
assets are operational state and remain excluded from Git.

| Model family | Installed assets | Location |
| --- | --- | --- |
| SD 1.5 checkpoint | `DreamShaper_8_pruned.safetensors` plus workflow-compatible `dreamshaper_8.safetensors` hardlink | `D:\comfyDesktop\models\local\checkpoints` |
| AnimateDiff | `AnimateLCM_sd15_t2v.ckpt`; `LiquidAF-0-1.safetensors` | `D:\comfyDesktop\models\local\animatediff_models`; `D:\comfyDesktop\models\local\animatediff_motion_lora` |
| LoRAs/adapters | `AnimateLCM_sd15_t2v_lora.safetensors`, `Hyper-SD15-12steps-CFG-lora.safetensors`, `v3_sd15_adapter.ckpt` | `D:\comfyDesktop\models\local\loras` |
| ControlNet | QR Monster v2, SD 1.5 lineart/depth fp16, and `v3_sd15_sparsectrl_rgb.ckpt` | `D:\comfyDesktop\models\local\controlnet` |
| VAE and upscaler | `vae-ft-mse-840000-ema-pruned.safetensors`; `2x-sudo-UltraCompact.pth` | `D:\comfyDesktop\models\local\vae`; `D:\comfyDesktop\models\local\upscale_models` |
| IP-Adapter | `ip-adapter-plus_sd15.safetensors`; `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` | `D:\comfyDesktop\models\local\ipadapter`; `D:\comfyDesktop\models\local\clip_vision` |
| Audio separation | Open-Unmix `umxl.pth`; Torchaudio Hybrid Demucs checkpoint | `D:\comfyDesktop\models\local\openunmix`; the current user's Torch Hub cache |

The bundled workflows were copied to
`user/default/workflows/Yvann Audio Reactive/`. Required supporting packs are
Advanced ControlNet, AnimateDiff Evolved, ControlNet Auxiliary Preprocessors,
FizzNodes, KJNodes, IPAdapter Plus, and VideoHelperSuite. Optional KJNodes
MiniMax and Triton-VAE features are not dependencies of these workflows.

The five Wan assets and publisher URLs are declared in
`assets/wan-s2v-models.json`. `scripts/install-wan-s2v-assets.ps1 -ListOnly`
previews their destinations without downloading. The CLIPSeg snapshot is
declared by `scripts/install_visualizer_semantic_assets.py`; workflow execution
loads it with `local_files_only=True` and never downloads weights.

No AI upscaler, SAM/SAM2 segmenter, or separate sparkle model is required by
the curated workflows. FFmpeg Lanczos performs delivery scaling, painted masks
remain the precision fallback, and the wordmark sparkle is procedural NumPy.

## Curated workflows

The untracked live workflow
`user/default/workflows/audio_reactive_loop_LTX23_Q2_8GB.json` is an evaluated
AudioLoopHelper LTX 2.3 Q2 configuration. It completed a 704x416x97
audio-conditioned test in 127.53 seconds with a measured 10,834 MiB peak. The
user accepted it as the current RTX 4070 12 GB workflow. Future tuning should
target less than 10 GiB, but is acceptable whenever generation remains wholly
GPU-resident without model or layer offloading to CPU. It is not a validated
8 GB configuration.

Only the following workflow files are tracked by this repository:

| Workflow | Status and role |
| --- | --- |
| `music_visualizer_infra_choir_enhanced.json` | Enhanced production copy. Preserves all seven reviewed target lanes and streaming output while adding cached high-resolution audio analysis, independently shaped target drivers, masked low-cost effects, section dynamics, and a genuine 256-band default EQ. |
| `music_visualizer_infra_choir_hybrid.json` | New seven-lane fixed-frame hybrid workflow. Separates organic motion, light source, illumination, and reflection roles; supports linked audio envelopes, optional stabilized short generated-motion batches, optional branding, and atomic streamed output. |
| `music_visualizer_infra_choir_production.json` | Production-polish copy of the seven-lane workflow with deterministic editable title cards, optional external-card selection, a restrained shared-analysis bottom EQ, and title-outline-confined glints. |
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

- The enhanced Infra Choir renderer performs one disk-cached STFT analysis per
  audio/configuration identity and streams one video frame at a time. A full
  287.375-second 1080p/16-fps Bella Ciao render peaked near 2.41 GiB process
  plus FFmpeg RSS and 3,310 MiB total observed GPU allocation; it does not use
  CUDA or model offloading for rendering.
- Fill-Nodes' native audio envelopes and image effects use incompatible custom
  envelope types or retain full image batches. Their Apache-2.0 algorithms were
  therefore used as design references for project-owned, streaming-compatible
  signal shaping and masked effects rather than connected directly.
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
- Explicit sun-disk/source queries use a compact warm-luminance refinement
  inside the selected search area, avoiding the Bella Ciao broad-glow false
  positive while leaving atmospheric illumination as its own target.
