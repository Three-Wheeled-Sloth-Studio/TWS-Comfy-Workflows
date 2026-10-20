---
type: Evaluation
title: LTX 2.3 Q2 AudioLoopHelper Benchmark
description: Compatibility and memory evidence for the smallest LTX 2.3 Video Studio tier in the AudioLoopHelper workflow.
status: stable
tags: [comfyui, ltx, audio-loop, gguf, benchmark, vram]
---
# LTX 2.3 Q2 AudioLoopHelper Benchmark

Date: 2026-10-13

## Outcome

Classification: **accepted 12 GB GPU baseline**.

`user/default/workflows/audio_reactive_loop_LTX23_Q2_8GB.json` completed a
real audio-conditioned 704x416, 97-frame, 24 fps generation on the RTX 4070
12 GB. The fastest retained configuration took 127.53 seconds and peaked at
10,834 MiB (10.58 GiB) total GPU memory. The user accepted approximately
11 GB for this workflow. The optimization target for future work remains less
than 10 GiB, but the operative acceptance requirement is fully GPU-resident
generation without model or layer CPU offloading.

## Model and loader compatibility

The bundled AudioLoopHelper example originally used:

- `UNETLoader` with the LTX 2.3 FP8 transformer;
- `DualCLIPLoader` with Gemma 3 12B mixed precision and a separate projection;
- `VAELoaderKJ` with the LTX 2.3 video and audio VAEs; and
- 25 fps timing.

The repaired LTX 2.5 workflow had substituted an INT8 ConvRot transformer,
the combined Gemma 4/projection text encoder, LTX 2.5 VAEs, core loaders, and
24 fps timing. Those substitutions were not copied blindly.

The new workflow uses architecture-matched LTX 2.3 components:

- `UnetLoaderGGUF`: `ltx-2.3-22b-distilled-1.1-Q2_K.gguf`;
- `LTXAVTextEncoderLoader`: `gemma_3_12B_it_fp4_mixed.safetensors` plus
  `ltx-2.3_text_projection_bf16.safetensors`;
- core `VAELoader`: `LTX23_video_vae_bf16.safetensors` and
  `LTX23_audio_vae_bf16.safetensors`; and
- `ComfyUI-GGUF` commit `6ea2651f3266613034c67221f84f979c58de87db`
  with `gguf==0.19.0`.

The five verified model assets occupy approximately 21.5 GB on disk under
`D:\comfyDesktop\models\local`. The larger Q3 checkpoint was not downloaded.

## Preserved loop and audio behavior

The graph retains TensorLoopOpen/TensorLoopClose, AudioLoopController, the
full-song pre-encoded audio latent, and the controller stop link. For the
benchmark, a real four-second input was trimmed, encoded by the LTX 2.3 audio
VAE, noise-masked, concatenated with the video latent, and sampled with all 48
audio-to-video attention blocks enabled at scale 2.5. The muxed output contains
AAC stereo audio at 48 kHz. This verifies that the conditioning path executes;
subjective rhythmic responsiveness was not independently A/B scored.

## Measurements

| Configuration | Time | Peak GPU memory | Observation |
| --- | ---: | ---: | --- |
| Initial Q2 graph, NAG enabled, FFN chunks 2, no pre-decode cleanup | 314.45 s | 11,625 MiB | Sampler completed; decode was dominated by retained transformer memory. |
| Retained graph: NAG bypassed, FFN chunks 4, pre-decode cleanup, 2x2 tiled decode | 127.53 s | 10,834 MiB | Best measured result; eight sampler steps completed in about 47 s. |
| FFN chunks 8 | 144.52 s | 11,070 MiB | Slower and higher peak than chunks 4. |
| Dynamic VRAM with 2.5 GB reserve, chunks 8 | 229.23 s | 11,631 MiB | Slower initialization and no peak-memory improvement. |

`ffprobe` reported 704x416, 24 fps, 97 frames, and 4.041667 seconds for the
video stream. The audio-muxed derivative was four seconds with AAC stereo at
48 kHz. Outputs are under `D:\comfyDesktop\output\benchmarks`.

## Structural validation

The retained workflow has 100 nodes and 138 links. The AudioLoopHelper audit
reported 42 passes, one intentional warning for disabled SageAttention, and
three known compatibility limitations: two checks are hard-coded for the old
25 fps example even though all nine timing sites coherently use 24 fps, and
the source tracer does not recognize `UnetLoaderGGUF` as a model-source class.
Graph link, acyclic dependency, and loop checks passed.

## Recommendation

Use this graph as the accepted RTX 4070 12 GB baseline. For future experiments:

- target peak GPU memory below 10 GiB;
- accept any result that runs generation fully on the GPU without model or
  layer offloading to CPU, including the current 10.58 GiB result;
- do not count a lower GPU-memory number as an improvement if it introduces
  CPU offloading or materially slower model swapping; and
- continue to test at 704x416x97 unless an experiment explicitly studies the
  quality/performance effect of changing geometry.

Do not claim that this complete AudioLoopHelper graph fits an 8 GB card, and
do not revert silently to the LTX 2.5 22B INT8 configuration.
