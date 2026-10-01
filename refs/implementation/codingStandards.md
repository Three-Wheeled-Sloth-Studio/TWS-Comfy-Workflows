---
type: Coding Standards
title: Coding Standards
description: Project-specific coding standards plus mandatory cross-platform path-safety rules.
status: draft
tags: [implementation, coding-standards]
---
# Coding Standards

TEMPLATE_TODO: Define project-specific coding style, safety rules, review expectations, and quality bar.

## Mandatory source modularity

These rules apply to hand-authored implementation code in every initialized project:

- Prefer one cohesive responsibility per source module. A file should be explainable in one short sentence without joining unrelated responsibilities with "and".
- Keep functions and modules small enough that an agent or human can inspect the relevant behavior with a targeted symbol or line-range read rather than loading a large multi-purpose file.
- Do not add a new independent responsibility to a file that already mixes unrelated concerns. Split the new responsibility, or decompose the existing file first when doing so can be done safely within the task.
- Separate orchestration, domain logic, persistence, external adapters, presentation, state management, and pure transformations when they can evolve or be tested independently.
- Avoid catch-all modules such as `utils`, `helpers`, `service`, or `manager` when the contents span multiple domains. Prefer semantic module names that expose purpose and ownership.
- Prefer explicit imports and narrow public surfaces so the generated source catalog can represent dependencies and callable boundaries usefully.
- Large-file thresholds may be enforced by project-specific linting, but line count alone is not the rule. Generated code, declarative data, migrations, protocol bindings, and other cohesive artifacts may legitimately be large.
- When a file is difficult to summarize, difficult to test without unrelated setup, or repeatedly requires broad reads for small changes, treat that as evidence that the module should be decomposed.

The goal is not aesthetic file splitting. The goal is bounded reasoning: a change should normally require loading only the source units that own the behavior being changed.

## Mandatory cross-platform path safety

These rules apply to every initialized project, regardless of language or build system:

- No two tracked repository paths may differ only by letter casing. A pair that works on a case-sensitive Linux checkout can become one ambiguous path on Windows or a default macOS checkout.
- Imports, references, generated manifests, and tooling configuration must match the tracked path's casing exactly.
- Do not distinguish a component and helper only by capitalization. Use semantic filenames such as `GeographicAtlasContextMap.tsx` and `geographicAtlasContextGeometry.ts`, not `GeographicAtlasContextMap.tsx` and `geographicAtlasContextMap.ts`.
- Every project must implement an automated case-collision guard using the Git index as its source of truth. The guard must read `git ls-files`, normalize separators, case-fold each complete path, and fail if distinct tracked paths produce the same folded key.
- A filesystem-only scan is insufficient because case-insensitive filesystems may already have collapsed the conflicting paths.
- Wire the guard into the repository's ordinary validation command. Where the project has typecheck or build scripts, run it before both.
- Test the guard with at least one synthetic collision pair and one non-collision pair.
- Perform case-only renames through a temporary intermediate filename, for example `git mv OldName.ts temporary-name.ts` followed by `git mv temporary-name.ts NewName.ts`. Verify `git status` and the final diff before committing.

A change that introduces or preserves a case-folded path collision is not ready to merge, even when tests pass on Linux.
