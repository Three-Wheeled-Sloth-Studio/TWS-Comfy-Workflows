---
type: Compatibility Contract
title: Agent Academy OKF Compatibility
description: Authority boundaries and interoperability rules for the Agent Academy OKF v0.2 profile.
status: stable
tags: [agent-academy, okf, interoperability]
---
# Agent Academy OKF Compatibility

Agent Academy is an opinionated project-memory operating model. Open Knowledge Format (OKF) is a portable representation and discovery standard for knowledge. The Agent Academy OKF profile combines them without replacing the parts of Agent Academy that are deliberately stricter.

## Authority Boundary

| Concern | Authoritative representation |
| --- | --- |
| Agent reading order and operating rules | `refs/agents.yaml` |
| Deterministic project state | Existing Agent Academy YAML |
| Schemas and allowed values | `refs/schemas/schemaRegistry.yaml` and project-specific validators |
| Human-readable knowledge concepts | OKF-compatible Markdown under `refs/` |
| Portable discovery | Generated `index.md` files |
| Rich typed or directional relationships | Agent Academy structured YAML when modeled there |
| OKF trust, provenance, freshness, lifecycle | OKF frontmatter when explicitly present |

Generic OKF consumers may read the Markdown concepts, indexes, links, and OKF metadata. Agent Academy-aware consumers may additionally read the structured YAML state.

## Concept Rules

Every Markdown file under `refs/` is an OKF concept except reserved `index.md` and `log.md` files.

Each concept must:

- begin with parseable YAML frontmatter;
- contain a non-empty `type`;
- preserve any valid unknown OKF or Agent Academy extension fields;
- use `status: draft` when a template concept is intentionally incomplete.

Agent Academy does not require `generated`, `verified`, `sources`, or `stale_after`. Their absence is preferable to invented provenance.

## Trust Rules

- Creation by a human or agent does not imply verification.
- Passing tests does not imply verification.
- Passing `validate_refs.py` proves structural conformance, not factual truth.
- Git commit history is not a substitute for `generated` or `verified`.
- Add `verified` only when the named actor actually checked the concept against its source or resource.
- Add `sources` only when the concept materially derives from those sources.
- Use `stale_after` only when the knowledge has a meaningful expiration instant.

## Index Rules

`index.md` files are generated deterministically by `refs/tools/generate_okf_indexes.py`.

They are:

- committed to Git;
- a discovery surface, not a second source of truth;
- regenerated after file additions, removals, moves, or concept metadata changes;
- checked by ordinary refs validation.

The root `refs/index.md` declares the supported `okf_version`. Non-root indexes contain no frontmatter.

## Relationship Rules

OKF v0.2 expresses relationships through Markdown links. Agent Academy may already contain richer typed, directional, or domain-specific relationships in YAML. Those richer structures remain authoritative.

Do not flatten or discard richer Agent Academy relationships merely to fit OKF v0.2. If a later OKF version standardizes equivalent relationship semantics, adopt them through an explicit profile migration.

## Studio Catalog Contract

A future studio-wide catalog is a derived discovery layer, not an authority.

Catalog entries should retain at minimum:

- originating repository;
- exact commit SHA;
- bundle path;
- concept path;
- available OKF trust and lifecycle metadata.

The project repository at the recorded SHA remains the source of truth. A catalog may cache or index content for discovery, but it must not silently become the canonical copy.
