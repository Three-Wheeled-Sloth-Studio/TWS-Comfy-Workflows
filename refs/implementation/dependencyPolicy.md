---
type: Dependency Policy
title: Dependency Policy
description: Approval, versioning, portability, and external-tool policy for project dependencies.
status: draft
tags: [implementation, dependencies]
---
# Dependency Policy

Project-owned Python utilities should use the standard library unless a task
demonstrably requires a third-party package. Record any new package, version
constraint, installation path, and portability impact before introducing it.

The motion-poster renderer depends on the `ffmpeg` and `ffprobe` executables on
`PATH`. They are external runtime tools rather than vendored repository assets.
The renderer must fail with a clear message when either executable is absent,
must map media streams explicitly, and must stream encoded output rather than
accumulate full-song frames in Python memory.

Model weights and runtime media remain external dependencies. Never download
them during ordinary validation or track them in Git.

## Wan 2.2 TI2V 5B benchmark assets

The user authorized a D:-resident Wan 2.2 TI2V 5B benchmark on 2026-10-21.
The following official Comfy-Org files are installed under
`D:\comfyDesktop\models\shared` and exposed to the active D:-resident local
model tree by hard links. They remain ignored external runtime state:

- `diffusion_models/wan2.2_ti2v_5B_fp16.safetensors`
  (9,999,658,848 bytes; SHA-256
  `456f901338bd9eadbded3828b819109a9b68e8a525ca5cf8d0049a69fcfeca1e`)
- `vae/wan2.2_vae.safetensors` (1,409,400,960 bytes; SHA-256
  `e40321bd36b9709991dae2530eb4ac303dd168276980d3e9bc4b6e2b75fed156`)

The existing `text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors` is reused.
The model is a portable optional motion-generation dependency, not a
requirement for the deterministic compositor. Its generated short clip must be
saved before full-song assembly so a later failure does not discard completed
diffusion work.

ACE-Step 1.5 uses ComfyUI's native nodes and built-in `Text to Audio
(ACE-Step 1.5)` blueprint; no third-party custom node or additional Python
package is required. On 2026-10-01 the following Comfy-Org assets were
installed in the Desktop-managed shared model root
`C:\Users\sloth\ComfyUI-Shared\models` so the shipped blueprint works without
filename changes:

- `diffusion_models/acestep_v1.5_turbo.safetensors` (4,787,825,604 bytes;
  SHA-256 `3f6e0797fad420a39bd33979eb6e840e30989e34a3794e843d23b60ec6e422d7`)
- `text_encoders/qwen_0.6b_ace15.safetensors` (1,191,588,248 bytes;
  SHA-256 `fd4590c82153b8ddb67e15a2e7aaa8afa8b83a858c8a9b82a4831063156aa7a7`)
- `text_encoders/qwen_4b_ace15.safetensors` (8,379,154,232 bytes;
  SHA-256 `ffe5ffb855086c2ab55e467e9859fb01894781020a0376484dd19de166b79873`)
- `vae/ace_1.5_vae.safetensors` (337,431,732 bytes; SHA-256
  `6de92e3a862acd287e08b024ac90f0783a8635451b728721a33ff03565bcb2bb`)

These model files are external runtime state and remain excluded from Git.
The 2B turbo model was selected over the optional XL family because the local
RTX 4070 has 12 GB VRAM and upstream recommends the standard 2B family for the
8-16 GB tier; the installed 4B planning LM matches ComfyUI's shipped blueprint
and can be offloaded by ComfyUI.

The guided motion-poster's default 1080p delivery upscale uses FFmpeg Lanczos
scaling and does not require an upscale model. As of 2026-10-01 no AI upscaler
weight is installed or declared for this workflow. If an optional AI mode is
added later, record its exact model filename, source, destination model folder,
and portability impact before installation; keep the weight ignored by Git.

The experimental logo visualizer adds no package or model dependency. It uses
Torch and NumPy from the existing ComfyUI runtime for CPU audio analysis,
Pillow for the already-supported transparent logo conversion, and FFmpeg's
built-in lossless `qtrle` encoder for the temporary alpha overlay.

The standalone local-composite visualizer also adds no package or model
dependency. It uses Torch, NumPy, and Pillow already present in ComfyUI for
CPU-side mask, audio, and frame work, then streams frames to the existing
FFmpeg dependency. It must not make SAM/SAM2, Wan, LTX, or any model weight
mandatory; those may only be optional future mask or effect providers with
separately documented assets.
