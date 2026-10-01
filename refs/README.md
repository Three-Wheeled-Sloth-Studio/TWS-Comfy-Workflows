---
type: Framework Guide
title: Refs Initialization Guide
description: Initialize and maintain the Agent Academy project-memory harness and its OKF discovery surface.
status: stable
tags: [agent-academy, project-memory, okf]
---
# Refs Initialization Guide

This folder is a reusable project-memory harness for coding agents and human collaborators. It is intentionally generic until copied into a real project.

The `refs/` directory is also an Open Knowledge Format (OKF) v0.2 bundle. Agent Academy keeps deterministic YAML state where exact schemas and machine behavior matter, while Markdown knowledge documents use OKF frontmatter and generated `index.md` files provide portable discovery.

Agent Academy also maintains a deterministic, generated source catalog under `refs/implementation/sourceCatalog/`. The catalog gives coding agents a compact file and callable-symbol discovery surface so routine implementation work can locate relevant code without first reading large portions of the repository.

## Setup Workflow

1. Copy this `refs/` folder into the target project root.
2. Read `refs/templatePolicy.yaml` to identify required bootstrap files and allowed template placeholders.
3. Replace `TEMPLATE_TODO` and `TEMPLATE_TODO_DATE` in required bootstrap files with project facts.
4. Generate the source catalog:

   ```powershell
   python refs/tools/generate_source_catalog.py
   ```

5. Regenerate the OKF discovery indexes:

   ```powershell
   python refs/tools/generate_okf_indexes.py
   ```

6. Run validation from the project root:

   ```powershell
   python refs/tools/generate_source_catalog.py --check
   python refs/tools/validate_refs.py --mode initialized
   python refs/tools/generate_agent_context.py --check
   ```

7. Keep durable project knowledge in `refs/` instead of only in chat.
8. Do not store secrets, API keys, tokens, passwords, or machine-only credentials in `refs/`.

## Routine Coding-Agent Re-entry

For routine continuation or after a coding-agent context reset, do not begin by rereading the full roadmap, decision history, architecture set, accumulated handoffs, or source tree. Generate a bounded orientation packet first:

```powershell
python refs/tools/generate_agent_context.py --focus "short description of the current task"
```

For routine runs, the context generator first refreshes the source catalog programmatically. This scan consumes local CPU and file I/O, not model context. The packet then derives compact context from authoritative refs, the source catalog, and local git state. It may include the current branch and commit, changed paths, explicit handoff required reads, relevant handoff highlights, accepted decisions, active todos and roadmap items, source-catalog matches, file-map hints, and validation commands.

The packet is deliberately **not** authoritative. Use it to decide what to read next. Start with the explicit required reads and source-catalog matches. Expand into deeper roadmap, architecture, history, tests, or source only when a concrete dependency, ambiguity, failing test, system boundary, or authoritative reference requires it.

If the packet does not locate the implementation you need, query the catalog before broad repository search:

```powershell
python refs/tools/generate_source_catalog.py --query "domain fit scoring"
```

Query results include source paths, callable symbols, line ranges, signatures, inputs, outputs, and static call dependencies where the language parser can determine them. Prefer reading the reported symbol or line range instead of the entire source file.

The context generator prints to stdout by default. A local scratch file is optional:

```powershell
python refs/tools/generate_agent_context.py --focus "..." --output .agent-context.md
```

Do not commit generated re-entry packets as project state. The default packet budget is 8,000 characters; if routine output exceeds that budget, tighten the authoritative handoff, source structure, or selectors rather than simply increasing reset context.

## Source Catalog

`refs/tools/generate_source_catalog.py` scans Git-tracked and non-ignored untracked implementation source without using an LLM. It excludes `refs/`, `.github/`, dependency folders, build output, and other non-application paths. Supported languages receive best-effort static extraction of imports/dependencies and callable symbols. Python uses its AST; common compiled and scripting languages use deterministic syntax patterns.

The generated catalog is sharded into stable hash buckets so a change to one source file updates only the relevant shard in normal cases. Catalog records include source content hashes, allowing unchanged records to be reused without reparsing. The root `index.yaml` remains a compact discovery surface.

The catalog is derived evidence, not runtime truth. Dynamic dispatch, reflection, generated code, dependency injection, framework wiring, and other runtime behavior may require targeted source or test inspection. Never hand-edit the catalog or shards. Regenerate them after source changes and require `python refs/tools/generate_source_catalog.py --check` before finalizing.

## Required Bootstrap Files

Fill these first after copying the harness:

- `refs/project.yaml`: project identity, purpose, stack summary, source-of-truth links.
- `refs/agents.yaml`: instructions agents must follow before editing the project.
- `refs/planning/roadmap.yaml`: current direction and sequence.
- `refs/planning/todos.yaml`: durable task list.
- `refs/architecture/overview.md`: how the system is shaped.
- `refs/implementation/fileMap.yaml`: where important code lives.
- `refs/handoffs/currentHandoff.md`: concise accepted baseline, recent delta, current gap, next slice, explicit required reads, constraints, and validation.
- `refs/testing/validationCommands.yaml`: commands agents should run before finishing work.

The generated source catalog is required framework infrastructure but is not manually bootstrapped.

## OKF Compatibility

- `refs/okfProfile.yaml` pins the supported OKF version and defines where Agent Academy is intentionally stricter or richer.
- Every non-reserved Markdown file under `refs/` is an OKF concept and must retain a non-empty `type` in YAML frontmatter.
- `index.md` files are deterministic generated discovery artifacts. Commit them, but do not hand-edit them.
- Structured YAML remains the authoritative representation for deterministic Agent Academy state.
- Passing tests, Git history, or refs validation does not by itself make a concept `verified` in OKF terms.
- See `refs/implementation/okfCompatibility.md` for the authority boundary and `refs/operations/okfMigration.md` for adoption guidance.

## Template Placeholders

Use only these sentinel placeholders in the blank harness:

- `TEMPLATE_TODO`: value intentionally left blank for the destination project.
- `TEMPLATE_TODO_DATE`: date intentionally left blank for the destination project.

Use `refs/fileGuide.yaml` for file-by-file guidance and `refs/MAINTENANCE.md` for framework maintenance.
