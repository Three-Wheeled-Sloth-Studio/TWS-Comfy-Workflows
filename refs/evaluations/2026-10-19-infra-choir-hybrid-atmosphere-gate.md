---
type: Evaluation
title: Infra Choir Hybrid Atmosphere Review Gate
description: Capability inventory and one-candidate Wan integration plan for the preserved dual-track scaffold.
status: draft
tags: [comfyui, infra-choir, wan, smoke, hybrid, evaluation]
---
# Infra Choir Hybrid Atmosphere Review Gate

## Production-state warning

Production moves faster than this evaluation. Image, audio, masks, prompts,
effect settings, branding, and output names recorded here are audit evidence,
not production defaults. Before generating or editing a production workflow,
inspect the user-designated live workflow and bind every media-specific value
to that saved state. Never restore the audit image or song merely because this
document or its candidate builder names them.

## Baseline

The preserved baseline is
`user/default/workflows/music_visualizer_infra_choir_dual_track_scaffold.json`
at SHA-256
`A7EE372E260DA42B609E068D38443F092C62B92351C8809CF77A0CF61FB93E7E`.
It remained untouched during this evaluation. Its artwork, audio, manual
boxes, masks, effect values, node layout, and presentation settings describe
the recovered audit snapshot only, not necessarily current production state.

## Capability inventory

| Capability | State | Evidence or limitation |
| --- | --- | --- |
| Seven independent manual lanes | Working | Detector-side inclusion, reviewed masks, compact effect cards, and target stacking pass schema tests. |
| Discovery preview and approval | Working | Discovery produces a preview; one-click approval saves an image-bound manifest. |
| Manual/automatic merge | Working | Deterministic policies and collision tests pass. The live graph intentionally selects `manual_only`. |
| Source-bound saved masks | Working | Four approved masks matched the audit-time `Photo.png` fingerprint exactly. |
| Disabled-target exclusion | Working | Disabled red-hair and red-fabric lanes do not enter the active target collection. |
| Procedural lighting, title, wordmark, EQ | Working | Focused tests and an eight-second real-image/audio render pass. |
| Procedural smoke | Partial | Safe and inexpensive, but cannot create genuinely new volumetric detail. It is not the artistic target. |
| Decoded IMAGE generated motion | Implemented | Stabilized, bounded short batches are accepted by the full target node schema. Compact manual cards do not expose this socket. |
| Cached external motion clips | Implemented and hardened | Decode, stabilization, loop crossfade, mask confinement, and cache reuse work. Explicit `cached_clip` now fails loudly when blank/unusable instead of silently reverting. |
| Cached-clip source binding | Implemented heuristic | First-frame large-scale structure must correlate with the selected artwork. A different-image clip is rejected before compositing. A durable sidecar registry remains future work. |
| Wan generation inside full-song render | Intentionally absent | Diffusion remains a separate approval step so lighting/title/EQ changes stay cheap. |
| Multi-variant and motion-aware looping | Missing | Current compositor uses one tail/head crossfade. Ping-pong and multiple independent variants remain unimplemented. |
| Full-scene protected-region restoration | Missing | The first vertical slice confines one full-scene Wan clip to reviewed atmosphere masks; broad scene replacement is deferred until visual review. |

## Candidate approaches

### A. Full-scene replacement plus protected restoration

Highest potential scene coherence, but also highest identity, geometry, and
camera risk. It requires reliable protected mattes and temporal alignment before
it is safe for figures and architecture.

### B. Independently generated regional crops

Efficient for isolated opaque objects, but smoke and fog lose context and expose
crop/matte seams. This is not the first choice for translucent atmosphere.

### C. One full-scene generation, mask-confined atmosphere, procedural lighting

This is the selected first quality gate. Wan sees the complete scene and can
create contextual smoke; the compositor uses only reviewed smoke regions from
that clip. Static source geometry remains the base. Lights, illumination,
reflections, title, wordmark, EQ, and audio synchronization remain deterministic
and inexpensive.

## Prepared candidate

`video_wan2_2_14B_s2v_infra_choir_atmosphere_candidate_v1.json` is a
snapshot-specific review workflow derived from the retained motion-loop
reference. It records `Photo.png` and `Static in the Champagne Room.mp3` as the
inputs observed during that audit, uses fixed seeds,
832x480 Wan S2V at 77-frame chunks, the installed four-step LightX2V path, a
smoke-specific positive prompt, and strong camera/identity/geometry negatives.
It saves below `output/infra_choir/motion_assets/` and does not reference or
modify the dual-track scaffold.

Structural generation, compile checks, focused enhanced/dual-track tests,
manifest checks, installer list-only checks, source/OKF freshness checks, and
initialized-reference validation all pass in the isolated validation worktree.
No validation command queued media generation.

Only one candidate should be queued initially. Do not batch speculative seeds.
Review it for:

- cigarette-smoke and piano-smoke volume, turbulence, and independent motion;
- face, head, hand, piano, lamp, chandelier, and building stability;
- camera translation or perspective drift;
- exposure pulsing and invented objects;
- whether a short masked excerpt clearly beats the procedural baseline.

Do not queue this saved candidate until its media, prompts, and output prefix
have been checked against the user-designated live workflow and updated in a
new version if necessary. Historical output cadence suggests a several-minute Wan job on this machine,
but it is not a controlled runtime benchmark. Record wall time and peak VRAM/RAM
when the candidate is actually queued.

## Stop condition

The candidate has not been queued. Generation is the explicit human-review
gate because it consumes substantial GPU time and can materially change the
visual result. If approved, the next step is to create a new hybrid compositor
workflow version pointing both smoke lanes at the reviewed clip, then render a
matched short A/B comparison. The preserved scaffold remains the rollback.
