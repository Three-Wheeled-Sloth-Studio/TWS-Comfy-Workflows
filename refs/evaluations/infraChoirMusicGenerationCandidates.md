---
type: Evaluation
title: Infra Choir Music Generation Candidate Spike
description: Installation and runtime evidence for pytraveler/YuE2-ComfyUI and Remiqora.
status: stable
tags: [infra-choir, comfyui, yue2, ace-step, music-generation]
---
# Infra Choir Music Generation Candidate Spike

Date: 2026-10-12

## Runtime boundary

- ComfyUI Desktop data root: `C:\Users\sloth\Documents\ComfyUI`
- Live custom-node root: `C:\Users\sloth\Documents\ComfyUI\custom_nodes`
- Desktop Python: `C:\Users\sloth\Documents\ComfyUI\.venv\Scripts\python.exe`
- ComfyUI source: `C:\Users\sloth\ComfyUI-Installs\ComfyUI\ComfyUI`
- Desktop model-path configuration: `C:\Users\sloth\AppData\Roaming\Comfy Desktop\instance-model-paths\inst-1780666292822.yaml`
- Primary shared model root: `C:\Users\sloth\ComfyUI-Shared\models`; repository-local `models` is second.
- Verified runtime: ComfyUI 0.39.2, Python 3.12.9, Torch 2.10.0+cu130, RTX 4070 12 GB, 97 GB system RAM.

## pytraveler/YuE2-ComfyUI

Recommendation: **BUILD AROUND**, subject to the non-commercial model license.

### Installation

- Maintenance checkout: `D:\Apps\Tools\YuE2-ComfyUI`, commit `1ebdfc771e89970f7d1e9129bd7c0413dc3381d8`.
- Runtime junction: `C:\Users\sloth\Documents\ComfyUI\custom_nodes\YuE2-ComfyUI` -> maintenance checkout.
- Required packages are `tiktoken>=0.7` and `requests>=2.28`; Desktop already had tiktoken 0.14.0 and requests 2.34.2, so no Python package was added.
- The pack registered 13 nodes: `YuE2GenerateSong`, `YuE2WriteSong`, `YuE2Transcribe`, `YuE2LoadMidi`, `YuE2VocalsOnly`, `YuE2EditTrack`, `YuE2LoRA`, `YuE2Options`, `YuE2Plan`, `YuE2PlanBatch`, `YuE2SelectPlan`, `YuE2RenderPlan`, and `YuE2DecodeLatents`.
- All 12 supplied templates remain in the linked pack and are available through Comfy's template discovery. The score, sheet, ABC, piano-roll, track-editor, MIDI, LoRA, and song-editor web extensions all registered; direct requests for the score/roll/editor modules returned HTTP 200.

### Models and duplicate avoidance

- Reused `C:\Users\sloth\ComfyUI-Shared\models\checkpoints\yue2_3b_int8_convrot.safetensors` (3.69 GiB).
- Reused `C:\Users\sloth\ComfyUI-Shared\models\audio_encoders\sheetsage2_bf16.safetensors` (1.29 GiB).
- These exact shared files are also visible in the existing native YuE2 loader nodes, so the new pack and prior nodes share one copy.
- Added only `C:\Users\sloth\ComfyUI-Shared\models\loras\YuE2\ar_lora_inst_v3abc.safetensors` (278,962,592 bytes) for the supplied instrumental template.
- Generation tests set `download=off` and `quantization=int8`; no implicit model download occurred.

### Smoke results

- Clean load: the pack imported in 0.4 seconds with no pack-specific missing dependency or node error. The live registry contains its 13 nodes alongside the existing YuE2 nodes.
- ABC planning: produced a 710-token, structured two-voice ABC score in 48.59 seconds. The score was returned in Comfy history and is editable text.
- ABC override: changed the planned tempo from 93 to 94 and one vocal note, then supplied the edited ABC to `YuE2GenerateSong`. The log confirmed that it sang the supplied score without writing a replacement.
- New song: rendered 11.998667 seconds, 48 kHz stereo FLAC in 36.77 seconds; mean/max volume -18.3/-4.2 dB.
- Cover/remix: a 12-second source was transcribed by the reused SheetSage2 model in 8.09 seconds, then rendered from its score in 38.40 seconds; output is 11.998667-second 48 kHz stereo FLAC, mean/max -19.5/-6.2 dB.
- Instrumental: the Mothersuperior adapter was found and applied to AR at 1.0. The generated ABC vocal staff contains rests only and the 11.998667-second stereo FLAC is non-silent (mean/max -23.2/-11.5 dB). The short forced-length run took 91.46 seconds and hit the score-token budget before audio generation; this is a caveat for artificially short instrumental tests, not a node-load failure.
- Score UI: ABC, sheet, piano-roll, MIDI and track-edit client modules are registered and served. The API smoke proved score visibility and edited-ABC override; interactive mouse editing was not automated.
- Edit Track: the node and template load, and generated songs were persisted in the pack's session memory for editing. Destructive retake/cut/move operations were not exercised in this focused smoke.
- Outputs: `output/infra_choir_spike/yue2_new_song_abc_override_00001.flac`, `yue2_cover_smoke_00001.flac`, and `yue2_instrumental_smoke_00001.flac`.

### Resources and compatibility

- Instrumental run sampling observed 7,927 MiB maximum total GPU memory, 100% utilization, and 53 C. No OOM occurred.
- With explicit offload, the pack reported a 2.63 GiB active model half, about 10.6 GiB free before performance work, and stage swaps through CPU RAM. No system-RAM pressure was observed on the 97 GB host.
- The existing native YuE2 loaders list the same INT8 checkpoint and SheetSage2 encoder, confirming compatible shared-model operation.
- Pre-existing startup warnings remain for KJNodes/Triton and a VRGDG LTX submodule; neither came from this candidate.

### License

- Node-pack code: Apache-2.0.
- YuE2 and SheetSage2 weights: CC BY-NC 4.0.
- Instrumental LoRA: CC BY-NC 4.0.
- This is unsuitable for commercial Infra Choir releases without separate permission; it is technically strong for evaluation, demos, and non-commercial work.

## Remiqora

Classification: **C, primarily standalone**. Recommendation: **MINE FOR IDEAS** for the Comfy-centered production stack; use it separately if its DAW/orchestrator experience is desired.

### Installation and boundary

- Source checkout: `D:\Apps\Tools\remiqora`, commit `b4d4afe6494f5aa9a259c63a37f53788c3d67501`.
- Nothing was added to Comfy's `custom_nodes`, model folders, workflows, or Python environment.
- Installed a dedicated backend venv at `D:\Apps\Tools\remiqora\backend\.venv` with FastAPI, Uvicorn, HTTPX, Pydantic, multipart, and dotenv dependencies.
- Installed frontend and desktop npm dependencies; the production Vue bundle built successfully. Remiqora served its UI and API on `http://127.0.0.1:9000`.
- Configuration in `backend/.env` points to the existing `D:\Apps\Tools\ACE-Step-1.5`, `D:\Apps\Tools\audio.cpp`, shared FFmpeg, and CUDA 13.1 tools. Remiqora's cancellation patch was applied to the clean ACE-Step checkout as the small compatibility change its source install requires.

### Reuse and duplicate avoidance

- Reused the exact pinned ACE-Step commit, its CUDA venv, and 10.68 GiB of existing ACE checkpoints. No ACE model or environment was downloaded again.
- Comfy's native ACE-Step files cannot replace the standalone engine's directory-form checkpoint set, but the already installed standalone set avoided that duplication in this machine.
- Remiqora's YuE2 engine requires an `audio.cpp` CUDA server and its GGUF YuE2, SheetSage2, and MuScriptor files. The existing Comfy safetensors are not compatible substitutes. The local `audio.cpp` checkout has neither a server binary nor weights; the app therefore correctly reports YuE2 unavailable and returns HTTP 409 rather than pretending the Comfy model is usable.
- No `audio.cpp` build, roughly 10 GiB GGUF download, Demucs environment, ACE base, or ACE XL model was added during this spike.
- Remiqora supplies no Comfy workflow or template because it does not execute inside Comfy. Interchange is file-level audio/MIDI/ABC, not node-graph interoperability.

### Smoke results

- Backend and built frontend launched cleanly; home page, status, configuration, resource, and feature endpoints returned HTTP 200.
- Feature inventory correctly reported ACE-Step available; YuE2, Demucs, ACE base, and ACE XL unavailable.
- The orchestrator started the reused ACE-Step API on port 8001, loaded the existing turbo DiT plus 1.7B LM without a download, and exposed a healthy proxy.
- A Remiqora-proxied text-to-music job produced a 10.000-second, 48 kHz stereo FLAC in 13.70 seconds (10.83-second LM phase, 2.86-second DiT phase).
- Peak sampled total GPU memory was 11,001 MiB; ACE's allocator reported 7.96 GB. Peak sampled utilization was 36% and temperature 35 C. After orchestrator stop, VRAM returned from 7.87 GB used to 2.61 GB used.
- Remiqora attributed about 5.25 GB VRAM and 9.11 GB system RAM to ACE while the loaded engine was idle; its own backend used about 66 MB RAM.
- Orchestrator stop completed cleanly, left both models stopped, and Comfy remained healthy on port 8000. The Remiqora UI/backend remains available on port 9000 with no model resident.
- Desktop unit tests: 36/36 passed. Frontend build passed. Backend byte-compilation passed.

### Errors and concerns

- Expected unavailable feature: YuE2 returns HTTP 409 until the separate `audio.cpp` binary and GGUF weights are installed.
- ACE logs warn that TorchAO extensions do not match Torch 2.7.1, Flash Attention is unavailable, Triton/vLLM is unavailable on Windows, and bitsandbytes is absent. ACE falls back to supported SDPA/PyTorch/AdamW paths and completed generation.
- The desktop npm tree reports eight moderate-severity advisories; frontend npm reported zero. Review before distributing a packaged desktop build.
- Remiqora code is MIT. ACE-Step code/weights are MIT. `audio.cpp` code is Apache-2.0. YuE2 weights remain CC BY-NC 4.0, including when used through Remiqora.

## Recommendation

- **YuE2-ComfyUI: BUILD AROUND.** It satisfies the Comfy-native requirement, shares the existing model set, exposes the requested score/editor workflow, and ran every focused generation path on the RTX 4070. Keep a hard non-commercial boundary unless YuE2 licensing is separately cleared.
- **Remiqora: MINE FOR IDEAS.** Its DAW, mutually-exclusive model lifecycle, resource display, stem/MIDI/arranger UX, and file library are useful reference material, and its reused ACE path works. It is a separate application rather than an extension of the existing Comfy graph/runtime, and enabling its YuE2 path would require a second inference stack and duplicate-format weights.
