---
type: Framework Maintenance
title: Framework Maintenance
description: Rules for changing the reusable Agent Academy refs harness and its OKF-compatible profile.
status: stable
tags: [agent-academy, maintenance, okf]
---
# Framework Maintenance

Use this guide when changing the reusable refs harness itself. Do not add project-specific facts to the framework.

## Add a Refs File

1. Add the file under the most specific existing `refs/` folder.
2. Include `version: 1` and `schema: refs/schemas/schemaRegistry.yaml` for YAML files.
3. For a non-reserved Markdown knowledge document, add valid OKF frontmatter with at least a non-empty `type`.
4. Use `TEMPLATE_TODO` and `TEMPLATE_TODO_DATE` for intentional blanks.
5. Document the file in `refs/fileGuide.yaml`.
6. Add schema hints in `refs/schemas/schemaRegistry.yaml` if the file is structured YAML.
7. Add the file to `refs/templatePolicy.yaml` if it is required or has special placeholder rules.
8. Regenerate `index.md` files with `python refs/tools/generate_okf_indexes.py`.

## Agent Re-entry Context Maintenance

`refs/tools/generate_agent_context.py` is a derived orientation layer over authoritative project memory and generated source discovery. Keep the generator project-neutral and deterministic.

- Do not move project truth into generated packets; source facts remain in the normal refs and source files.
- Keep the routine default context budget bounded. If output grows, tighten handoffs, source structure, selectors, or discovery results before increasing the budget.
- Preserve progressive loading: packet first, explicit handoff required reads and source-catalog matches next, targeted file-map/search reads after that, and broad roadmap/architecture/history reads only when needed.
- Treat `Required Reads For Next Slice` as an explicit re-entry contract. Keep it narrow and explain why each path, symbol, or line range is needed.
- Support Agent Academy's canonical `fileMap.yaml` `areas` structure; compatibility with richer project extensions may be additive but must not make them mandatory.
- The blank template must remain a valid input. `TEMPLATE_TODO` values should be omitted from packets rather than emitted as apparent project facts.
- Keep git inspection local and read-only except for deterministic generated source-catalog files. The generator must not require network access, GitHub CLI, or provider credentials.
- When authoritative planning, handoff, or discovery structures change, update the generator and its `--check` validation in the same framework change.
- Generated packet files are disposable scratch artifacts and should not become committed project memory.

## Source Catalog Maintenance

`refs/tools/generate_source_catalog.py` provides a deterministic discovery layer over implementation source so agents can locate relevant code without spending model context on repository-wide reads.

- Keep the catalog derived. Source files and tests remain authoritative; catalog data is static-analysis evidence only.
- Keep generation local and deterministic. Do not require network access, model calls, language servers, provider credentials, or repository-specific build tools.
- Scan source programmatically rather than asking an agent to summarize files manually.
- Preserve stable hash-bucket sharding so changing one source file normally changes only one shard plus the compact root index.
- Store a source content hash with each file record and reuse records only when both the content hash and `FORMAT_VERSION` match.
- Increment `FORMAT_VERSION` whenever extraction semantics change in a way that requires all cached source records to be rebuilt.
- Prefer exact syntax support where the Python standard library provides it. For other languages, keep deterministic best-effort parsers conservative and label the parser used on every symbol record.
- A parser may miss dynamic behavior; it must not invent runtime dependencies or claim certainty that static analysis cannot support.
- Keep the catalog useful for bounded reads: records should expose file path, file dependencies, callable name, line range, signature, inputs, output, and static call dependencies when available.
- Exclude framework refs, CI metadata, dependency directories, and build output from normal application-source discovery.
- `refs/implementation/sourceCatalog/index.yaml` and `refs/implementation/.sourceCatalogShards/shard-*.yaml` are generated files. Never hand-edit them. The hidden shard directory keeps large generated detail out of the OKF browsing surface while remaining locally queryable.
- CI should run `python refs/tools/generate_source_catalog.py --check` before validating bounded agent context.

## Update Schemas

Schema hints should stay simple and stable. Prefer required top-level keys and allowed status values over highly specific project rules.

Agent Academy YAML schemas remain authoritative for deterministic project state. OKF compatibility is additive and must not weaken those schemas.

## OKF Profile Maintenance

- `refs/okfProfile.yaml` pins the canonical OKF repository, supported version, and reference commit.
- Upgrade the pinned OKF version only as an explicit profile migration.
- Preserve Agent Academy extensions when OKF does not yet express equivalent semantics.
- Never infer `verified` from authorship, automated validation, test results, or Git history.
- Keep generated `index.md` files committed and exactly synchronized with the generator.
- Do not add `log.md` merely for conformance; Git history and existing Agent Academy logs remain authoritative until a concrete OKF consumer requires a log surface.

## Versioning

Keep existing paths stable whenever possible. When a breaking layout change is unavoidable, update this file with a migration note and preserve compatibility guidance for projects that already copied the harness.

## Migrations

Migration notes should include the old path, new path, reason for change, and the safest copy/update sequence. Avoid destructive instructions.

For OKF alignment, preserve existing YAML state and project-specific taxonomies. Mature repositories may adopt the OKF profile without importing blank Agent Academy files they do not otherwise need.
