---
type: Dependency Policy
title: Dependency Policy
description: Approval, versioning, portability, and external-tool policy for project dependencies.
status: draft
tags: [implementation, dependencies]
---
# Dependency Policy

Project-owned Python utilities should use the standard library unless a task
demonstrably requires a third-party package. Record any new package, version
constraint, installation path, and portability impact before introducing it.

The motion-poster renderer depends on the `ffmpeg` and `ffprobe` executables on
`PATH`. They are external runtime tools rather than vendored repository assets.
The renderer must fail with a clear message when either executable is absent,
must map media streams explicitly, and must stream encoded output rather than
accumulate full-song frames in Python memory.

Model weights and runtime media remain external dependencies. Never download
them during ordinary validation or track them in Git.
