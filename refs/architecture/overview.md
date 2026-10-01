---
type: Architecture Overview
title: Architecture Overview
description: Repository boundary, ComfyUI runtime integration, workflow generation, and long-video state handling.
status: draft
tags: [architecture, comfyui, wan, video]
---
# Architecture Overview

The repository is embedded at the root of a live ComfyUI data directory but uses a deny-by-default `.gitignore`. Only explicit project-owned workflows, custom nodes, scripts, asset manifests, and `refs/` knowledge are eligible for tracking. `scripts/validate_repository.py` independently validates the Git index so ignore rules are not the sole safety boundary.

ComfyUI loads `custom_nodes/comfyui_audio_duration_plan/` directly. The Python workflow builders transform the saved source workflow into automatic-duration variants under `user/default/workflows/`. The current windowed workflow calculates its target from audio duration, generates one initial Wan S2V chunk, then uses native loop nodes for continuation chunks.

The current continuation state stores completed latent chunks on CPU and carries only the latest 19 latent frames for motion continuity. Reference-image conditioning is extracted from the initial conditioning and reused, preventing a VAE encode between each extension. ComfyUI's dynamically expanded loop still appears to retain enough GPU/runtime state to trigger progressively heavier model offloading after roughly 12 extensions; that is the active architectural gap.

Models and media are external runtime dependencies. The repository stores only manifests and download/install scripts. Generated outputs, inputs, model weights, caches, logs, virtual environments, general user configuration, and third-party custom nodes must never be tracked.
