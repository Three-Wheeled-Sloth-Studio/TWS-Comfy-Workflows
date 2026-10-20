---
type: Architecture
title: Infra Choir Dual-Track Target Workflow
description: Setup-time reviewed target discovery merged deterministically with manual lanes, plus fixed-bound titles, ultra-band EQ, and offline atmospheric clips.
status: draft
tags: [architecture, comfyui, visualizer, segmentation, manifests, spectrum]
---
# Infra Choir Dual-Track Target Workflow

## Production-state authority

The production workflow is a fast-moving user-owned artifact. Documentation,
builders, examples, recovery snapshots, timestamps, and previously generated
candidates must never be used to infer the current base image, audio, boxes,
prompts, settings, or output naming. Read those values from the
user-designated live workflow for each task, preserve unrelated saved state,
and create a new workflow version for experiments instead of rebuilding the
live workflow from an older baseline.

## Entry point and rollback

The implementation candidate is
`user/default/workflows/music_visualizer_infra_choir_dual_track_scaffold.json`.
It does not overwrite `music_visualizer_infra_choir_enhanced.json`; that workflow
remains the rollback baseline. The dual-track graph still needs a Comfy Desktop
restart, import check, and real visual/runtime validation before promotion.

## Setup-only discovery and review

`InfraChoirAutoDiscover` is an explicit output action node. Its default `idle`
action performs no analysis or file write, so a normal full-song queue does not
rediscover targets. `discover` proposes first-class smoke, light-source,
illumination, generic atmosphere, flame, and reflection masks. Hair, fabric, and person proposals require the
optional profile; they are low priority, disabled by default, and carry no
lip-sync assumption. For discovery, apply, or reset, select this node and use
ComfyUI's **Queue Selected Output Nodes** action so the renderer is not queued.

The primary dropdown label names its scope directly: lights, reflections,
smoke/fog/flame. Smoke is not folded into generic atmosphere: its semantic pass
combines independently normalized thin-plume and broad-fog responses, uses a
finer spatial grid, may retain eight disconnected regions, and receives its own
slow-billow preset. Generic fog/mist/cloud atmosphere remains separate. Every
action updates a non-serialized status field and raises a toast. Discover shows
the annotated mask image on the node. Idle shows only its safety no-op status
and never creates a preview, manifest, or analysis result.

Discovery returns an image-bound JSON manifest and a colored mask preview.
After checking that preview, **Push this discovery into flow** is the normal
one-click approval path. It marks every visible target enabled, verified, and
approved; validates each embedded PNG mask; optionally preserves reviewed
targets for the same source image; and atomically saves below the Comfy user
directory without queuing the full renderer. The next normal workflow run loads
the targets automatically, and the button returns the setup action to `idle`.
The JSON editor is hidden by default and retained
only for advanced per-target overrides. Reset remains explicit.

Automatic targets have runtime-enforced behavior contracts. Light sources and
illumination are spatially still and change only luminance/color/glow;
reflections are spatially still and may shimmer. People, faces, hair, and fabric
remain static because mesh deformation cannot produce credible articulated
human motion. A dilated semantic person mask is also subtracted from every
environmental discovery mask before persistence. Smoke remains a non-rigid
billow, with stronger slow response, but deformation displacement is capped
independently from atmosphere-mask expansion so expanded support cannot turn
into hundred-pixel translation of adjacent scene content.

## Runtime loading and merge

`InfraChoirApprovedTargets` reads only the saved manifest. Missing, invalid,
disabled, unreviewed, or stale-image data produces an empty collection by
default. Strict mode can raise on stale or invalid input. Every loaded target
contains the real decoded mask and complete version-2 target parameters.

`InfraChoirTargetMerge` supports manual-only, auto-only, keep-both, manual-wins,
and auto-wins modes. The discovery scaffold defaults to auto-only because its
seven inherited manual lanes are image-specific and can otherwise reinterpret
heads, clothing, or fixtures in unrelated artwork. Manual modes remain explicit
fallbacks. Collision-resolving modes compare stable IDs first, then normalized
class plus mask intersection-over-union. Ordering is stable.
Reviewed/edited/locked targets absent from a later apply payload are retained
when preservation is enabled.

## Titles and spectrum

Title text alignment is applied inside the same pre-existing 86%-width title
box. Left, center, and right alignment do not move or resize the overlay. The
default is center, matching the former hard-coded behavior.

The ultra-band selector adds genuine 1024- and 2048-band STFT analysis. Every
band owns at least one distinct FFT bin; an incompatible band/FFT/frequency
combination fails with an actionable error. When bands outnumber available
output columns, contiguous analyzed bands are peak, RMS, or mean aggregated to
pixel density. Lower-resolution spectra are never interpolated and relabeled.
The existing 512-and-lower render path is unchanged.

## Atmospheric motion boundary

Only `InfraChoirAtmosphericTargetEnhanced` exposes expansive atmosphere and
offline-clip controls, leaving the established target schema intact for the
other five lanes. Procedural expansion can reject high-detail edge pixels to
protect foreground structure. Optional cached clips are decoded from Comfy
input/output/temp, stabilized, frame-limited, mask-confined, and looped with a
tail/head crossfade. The renderer never loads a diffusion model or creates a
Wan clip; those assets must be generated and benchmarked in a separate step.
The manual atmospheric node defaults its explicit boxed mask to active. A blank
`generated_clip_path` means procedural rendering; it is not an output field and
does not become populated after a render. Automatic discovery remains governed
by its reviewed, image-bound manifest rather than this manual-lane default.
All seven manual lanes use a compact node surface and a linked inclusion toggle
on the box/detection node. Smoke cards expose intensity, boundary expansion,
billow amount, and foreground protection; other cards keep the most frequently
tuned role, motion, flicker, luminance, and glow controls. Each card has an
**Advanced Settings…** button that opens a modal editor for target IDs and
groups, audio drivers, ADSHR shaping, detailed appearance controls, and cached
atmosphere clips. Those values serialize in one hidden per-card field: the
advanced UI adds no nodes, sockets, or graph wires. Non-geometric haze
computes motion inside binary mask support, then applies the soft mask once at
final composite, avoiding prior alpha-squared attenuation without translating
source people or fixtures.

The editor is role-aware. Smoke presents its on-card intensity, expansion, and
billow controls as primary and limits the modal to response shaping plus an
optional cached clip. Generated-motion blend controls are not shown on compact
nodes that cannot accept a generated IMAGE. Shimmer is shown only for
reflections, glow only where the renderer consumes it, and on-beat motion only
for organic targets. Enhanced procedural smoke transports fine and broad
texture already present in the source image rather than painting a synthetic
pale density field. This keeps average colour stable and produces rolling
local structure without moving the underlying source geometry. It remains a
still-image fallback: genuinely new smoke detail requires a short Wan-generated
IMAGE batch or cached clip, which the renderer stabilizes and confines to the
reviewed mask. Lighting transfer compensates for soft-mask attenuation but
remains clamped by maximum luminance and glow limits.

## Validation boundary

Automated coverage currently verifies JSON/node positional schemas, link
routing, manifest apply/load and stale-image behavior, deterministic merge
policies, density rendering, and 1024/2048-band analysis. Still required:
Desktop import with zero missing nodes, visual discovery review on a new image,
manual-only/auto-only/both full-song renders, centered multi-line title review,
seam and foreground inspection for cached clips, and an RTX 4070 12 GB offline
Wan clip benchmark.

## Wan-quality atmosphere vertical slice

The first generative quality gate uses one full-scene Wan S2V clip as contextual
source material, but composites it only through reviewed atmosphere masks. This
preserves full-scene context during generation without replacing figures,
architecture, lighting controls, title, wordmark, or EQ in the final render.
The generated clip remains an offline, reusable asset; changing audio-response
or presentation settings never queues Wan again.

Explicit `cached_clip` mode is fail-closed. A missing, undecodable, or visibly
different-source clip raises an actionable error rather than silently reverting
to procedural smoke. Cached clips are checked against the selected artwork by
first-frame structural correlation after decode and stabilization. The
separately versioned candidate generator is
`video_wan2_2_14B_s2v_infra_choir_atmosphere_candidate_v1.json`; it must pass
human visual review before a new hybrid compositor workflow points at its
output.
