---
type: Regression Checklist
title: Regression Checklist
description: Known regression checks including mandatory cross-platform repository path safety.
status: draft
tags: [testing, regression]
---
# Regression Checklist

## Cross-platform repository paths

- [ ] The Git-index case-collision guard passes.
- [ ] New and renamed tracked paths remain unique after normalizing separators and case-folding the complete path.
- [ ] Imports, manifests, scripts, and documentation links use the exact tracked-path casing.
- [ ] Related files use semantic names rather than capitalization-only distinctions.
- [ ] Any case-only rename used a temporary intermediate filename and produced the intended Git diff.
- [ ] The collision guard is exercised by the repository's normal validation path and runs before typecheck/build where those commands exist.
- [ ] The guard has a regression test containing both a synthetic collision and a valid non-collision pair.

- TEMPLATE_TODO: Add project-specific known regressions and critical workflows to verify.
