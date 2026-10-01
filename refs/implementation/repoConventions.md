---
type: Repository Conventions
title: Repo Conventions
description: Repository layout, naming, generated-file, contribution, and cross-platform path conventions.
status: draft
tags: [implementation, repository]
---
# Repo Conventions

TEMPLATE_TODO: Describe project-specific repository layout, naming conventions, generated files, and contribution expectations.

## Path and module naming baseline

- Repository paths are portable identifiers, not presentation text. Preserve their exact casing in imports, scripts, manifests, documentation links, and generated output.
- Never add paths that become identical after case-folding the full path. This rule applies across directories, filenames, stems, and extensions.
- Use semantic suffixes to distinguish related modules, such as `Component`, `Geometry`, `Model`, `State`, `Controller`, `Adapter`, `View`, `Schema`, or `Utils`. Capitalization alone is not a valid distinction.
- Before committing file additions or renames, run the project's Git-index case-collision guard.
- The standard guard must inspect tracked paths from `git ls-files`; do not rely solely on `find`, directory enumeration, IDE search, or the current machine's filesystem behavior.
- Case-only renames must use a temporary intermediate path so Git records the rename reliably on case-insensitive systems.
