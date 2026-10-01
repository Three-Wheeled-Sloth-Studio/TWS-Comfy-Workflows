---
type: Migration Guide
title: Adopt Agent Academy OKF Compatibility
description: Non-destructive adoption guidance for existing Agent Academy and mature custom refs repositories.
status: stable
tags: [agent-academy, okf, migration]
---
# Adopt Agent Academy OKF Compatibility

The OKF alignment is additive. Do not replace deterministic YAML or rearrange a mature repository merely to make it look like the blank Agent Academy template.

## Existing Agent Academy Project

1. Sync `refs/okfProfile.yaml`, the updated validator, and `refs/tools/generate_okf_indexes.py`.
2. Add OKF frontmatter to every non-reserved Markdown document under `refs/`.
3. Mark intentionally incomplete template documents `status: draft`.
4. Preserve existing YAML files and schemas as authoritative state.
5. Run `python refs/tools/generate_okf_indexes.py`.
6. Run the project's normal refs validation.
7. Review the generated indexes and Git diff before committing.

Do not invent `generated`, `verified`, `sources`, or `stale_after` values during migration.

## Mature Custom Refs Repository

A mature repository may adopt the Agent Academy OKF profile without importing the entire blank Agent Academy taxonomy.

Keep the project's established `refs/` organization when it is already useful. Apply the compatibility contract to the knowledge surface that exists:

- preserve existing deterministic YAML;
- make Markdown concepts OKF-compatible;
- add the pinned OKF profile;
- generate committed indexes;
- extend the local validator with equivalent conformance checks;
- document any project-specific exceptions.

This avoids duplicate state and unnecessary maintenance surface.

## Updating OKF Versions

Treat a new OKF version as a profile migration:

1. review the canonical OKF specification and active compatibility concerns;
2. update `refs/okfProfile.yaml` with the new version and exact reference commit;
3. update validation and generation logic only where required;
4. preserve backward-compatible Agent Academy extensions unless the new standard cleanly replaces them;
5. validate against at least one real downstream project before broad rollout.

## Studio Catalog Readiness

After Agent Academy itself is green, pilot the profile in one current downstream repository. Once both generic OKF discovery and Agent Academy-specific structured-state discovery work there, a studio-wide catalog repository can be created.

The catalog must index project truth, not copy and replace it.
