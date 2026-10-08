---
type: Architecture Overview
title: Architecture Overview
description: Repository boundary, ComfyUI runtime integration, workflow generation, and long-video state handling.
status: stable
tags: [architecture, comfyui, wan, video]
---
# Architecture Overview

The repository is embedded at the root of a live ComfyUI data directory but uses a deny-by-default `.gitignore`. Only explicit project-owned workflows, custom nodes, scripts, asset manifests, and `refs/` knowledge are eligible for tracking. `scripts/validate_repository.py` independently validates the Git index so ignore rules are not the sole safety boundary.

ComfyUI loads `custom_nodes/comfyui_audio_duration_plan/` directly. The primary
builder generates a guided workflow under `user/default/workflows/` that takes
one reference image, one song, editable structured motion targets, seed
controls, and two optional branding images. Wan generates a short 1024×576
exact-16:9 motion asset;
the project-owned assembler closes it into a ping-pong cycle, streams it to the
exact audio duration, applies optional branding, and writes H.264/AAC output.

The default delivery path uses FFmpeg Lanczos scaling. It preserves and scales
the complete exact-16:9 1024×576 foreground onto the 1920×1080 canvas without
padding, stretching, or cropping, then composites branding. The title/wordmark compositor can derive a
dark or light blurred halo from the PNG alpha channel before placing the clean
wordmark over it; no additional title asset is required.
Full-song encoding is streamed so the completed song is not retained as a frame
batch in Python memory.

The standalone local visualizer is a separate, compositing-first path. It uses
six explicit masks and CPU audio analysis to stream procedural cloud, candle,
warning-light, monitor, rain, and reflection effects over an otherwise static
source image. It loads no model and applies no camera transform. See
`refs/architecture/localBeatVisualizer.md` for its mappings, resource boundary,
and limitations.

The deferred visualizer remains isolated in a copied workflow and a subclassed
assembler. It performs CPU-only stereo STFT analysis across twelve logarithmic
bands per channel, renders a padded lossless-alpha radial spectrum at final
overlay dimensions, and feeds that stream into the existing FFmpeg
composition. The production assembler retains its static-logo schema and
behavior; the current spectrum is coherent but too visually dominant for the
lower-right brand position.

The older windowed continuation experiment stores completed latent chunks on
CPU and carries the latest 19 latent frames for motion continuity. Its remaining
GPU-retention and checkpoint questions are a separate experimental track and do
not block the accepted short-asset motion-poster architecture.

Models and media are external runtime dependencies. The repository stores only manifests and download/install scripts. Generated outputs, inputs, model weights, caches, logs, virtual environments, general user configuration, and third-party custom nodes must never be tracked.
