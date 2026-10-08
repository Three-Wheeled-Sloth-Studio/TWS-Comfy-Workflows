---
type: Release Checklist
title: Release Checklist
description: Project release validation and packaging checklist.
status: stable
tags: [operations, release]
---
# Release Checklist

- Regenerate all curated workflow JSON files with their builders, including the
  separate experimental visualizer copy.
- Run every command in `refs/testing/validationCommands.yaml`.
- Confirm the guided assembler input schema matches the generated workflow.
- Keep model weights, media, outputs, caches, and general user configuration
  outside Git.
- Confirm curated workflows and example manifests contain only neutral media
  selectors, never studio source filenames or media-specific output names.
- For runtime releases, verify one source-resolution assembly and one 1920×1080
  assembly with exact audio duration.
- Review a representative output for identity, mouth stability, composition,
  loop seams, branding placement, and edge-fill behavior.
- Preserve the documented production defaults: one variant, neutral camera,
  anti-lip-sync guidance, 1024×576 generation, and Lanczos 1080p delivery.
- Record newly accepted limitations or future work in the current handoff and
  planning refs before closing the release.
