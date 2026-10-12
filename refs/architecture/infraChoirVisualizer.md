---
type: Architecture
title: Infra Choir Hybrid Music Visualizer
description: Fixed-frame, target-gated procedural and generated-motion compositor with linked local lighting.
status: stable
tags: [architecture, comfyui, audio, compositing, visualizer, segmentation]
---
# Infra Choir Hybrid Music Visualizer

## Entry point

Open `user/default/workflows/music_visualizer_infra_choir_production.json`
after restarting ComfyUI. It is a production-polish copy; the original hybrid,
local, generic, and semantic workflows remain intact. Select artwork and audio, inspect each
green detection preview, correct a mask in **Verify / Edit Detection Mask** when
needed, then enable `mask_verified` on the corresponding **Configure Infra Choir
Target** node. Queue the renderer once. Disabled, incomplete, empty, and
unverified lanes remain connected and are skipped with a diagnostic.

The starter graph has seven independent lanes: red hair, red fabric, industrial
smoke, clouds, sun source, sunlit atmospheric illumination, and river
reflection. The last three use the shared `sunlight` envelope group while
keeping separate masks, roles, luminance bounds, saturation/hue controls, and
glow behavior. Lanes can be duplicated; the stack has no five-target engine
limit.

## Static-frame invariant

Every output frame starts as a fresh copy of the source artwork. Procedural or
generated pixels are blended only through a verified target mask. Organic
targets may use the renderer's bounded `organic_motion_expansion_percent`
support mask (2.5% by default, 8% maximum) so warped smoke, hair, fabric, and
cloud pixels can cross their original matte edge. Non-organic targets remain
strictly clipped; light-source glow uses its separate bounded expansion. There is no camera transform,
global exposure modulation, zoom, crop animation, or whole-frame displacement.

An optional short generated `IMAGE` batch can be connected to any target and
selected with `generated_clip` or `generated_then_procedural`. The renderer
estimates and removes whole-frame translation from every generated frame,
rejects clips longer than 161 frames, loops them with a ping-pong index, and
still composites them only inside the target mask. A missing or one-frame clip
falls back to procedural motion with an explicit diagnostic. This lets a cached
Wan decode provide local organic pixels without passing Wan camera drift or
full-frame deformation into delivery.

## Target configuration format

Each target node emits `configuration_json` matching
`assets/infra-choir-target.schema.json`; a concrete example is
`assets/infra-choir-target.example.json`. Masks and optional generated motion
remain typed ComfyUI connections. The JSON captures enable/verification state,
semantic role, linked envelope, audio driver, motion source/profile, four
beat/autonomous controls, and bounded light controls.

Image changes invalidate saved review masks through the existing source RGB
fingerprint. Detector inputs and image identity form the bounded in-process
semantic cache key. Audio is downstream of targeting and optional generated
motion, so changing only the song recomputes audio analysis/rendering while
ComfyUI can reuse unchanged image stages. Control changes invalidate their
target and downstream render without forcing unrelated detector nodes to run.

## Targeting

The local-only CLIPSeg provider remains optional and falls back to the existing
heuristic provider in `semantic_or_heuristic` mode. `semantic_only` returns an
actionable missing-model/runtime error. Crop-first query expansion handles
neutral smoke. Explicit `sun disk`, `sun orb`, and `sun source` queries add a
model-independent compact warm-luminance locator inside the user search area;
this separates the Bella Ciao emitting disk from the broad sunset haze.

Automatic output is never silently approved. `mask_verified` is false in every
starter lane, so a semantically wrong proposal cannot render until a person
inspects it. Mask Editor corrections are optional, source-bound, persistent,
and individually resettable.

## Production title and EQ layers

The production renderer generates its title card from `band_name` and
`song_title` by default. Text is uppercased to match the supplied art direction,
automatically shrinks and wraps, and stays inside a central safe area above the
EQ. The card uses a deterministic dim, mostly desaturated copy of the source
artwork with dark-crimson fill and a thin pale outline;
`title_card_source_visibility` controls its restrained background level.
`title_card_image` is an upload-capable input-image selector; choosing
an image overrides generation, while `(generate from text)` needs no file or
connection. Start time, duration, fade, and upper/center/lower placement are
editable. Missing external files fall back to generated text with a diagnostic.

Georgia is loaded from the local Windows font installation and is not
redistributed by this repository. DejaVu Serif is the documented local fallback
on systems that provide it. Pillow's built-in font is the final functional
fallback.

The optional EQ uses the same per-frame FFT already used by target envelopes.
That pass now retains 24 log-spaced frequency bands, and the renderer smooths
them once for either bottom-anchored spectrum bars or a continuous treatment.
Default height is 11% with 0.46 opacity and a restrained crimson glow. It never
transforms the source or enters the environmental target compositor.

When `apply_wordmark` is enabled without a connected wordmark image/mask, the
renderer generates a persistent transparent upper-left band/song wordmark from
the same two text fields. A connected image and mask remain an explicit external
override. Title glints use generated text's actual stroke-minus-fill mask for
both the opening card and generated wordmark. For an
external image, a conservative pale, low-saturation outline detector is used;
implausibly sparse or broad detections disable sparkle and explain why in the
QA report. Glints are stationary, sparse, short-lived, and clipped to that
outline mask. Title, EQ, and sparkle have independent enable controls.

## Rendering and recovery

Audio features are deterministic CPU RMS, low-band, high-band, onset, slow, and
beat envelopes. Frames stream to FFmpeg as RGB and the original audio is muxed
to exact duration as AAC. A render is written to a `.part.mp4` sibling and
atomically promoted only after FFmpeg succeeds. An interrupted partial never
replaces a valid result and is overwritten automatically on retry; no cache or
intermediate cleanup is required.

Brand logo remains a truly optional input. Enabling an absent logo produces a
skip diagnostic instead of a validation failure. `brand_logo_image` provides a
direct input-folder selector, while connected logo image/mask sockets override
it. An absent wordmark input now
selects deterministic text generation rather than skipping the requested layer.

## Validation evidence (2026-10-09)

- 2026-10-12 correction pass: the generated card retained the source at 20%
  visibility, the persistent wordmark was produced from band/song text without
  an asset, and two repeat previews completed without reconnection. A 2.5%
  organic expansion produced 5.691 mean temporal delta in the ring outside the
  original mask versus 0.016 in the far field. The equal six-second expanded
  motion render took 2.19 seconds versus 1.90 seconds for strict clipping. The
  corrected full-song run rendered 2,299 frames in 53.71 seconds and preserved
  the 287.36-second source as a 287.375-second H.264/AAC container.

- Production polish: long Unicode text wrapped and stayed above the reserved
  EQ safe area; the supplied `Bella Ciao - underlay.png` was accepted as an
  external override with 2.039% reliable outline coverage. Sparkle validation
  changed 17 pixels and every changed pixel was inside the thresholded outline.
  Full-strength EQ changed only the bottom region and averaged 1.389 RGB levels
  across the whole frame, confirming the restrained default treatment.
- Independent title-off, EQ-off, and sparkle-off renders, an external-override
  render, and two consecutive complete preview renders all produced H.264/AAC
  output without reconnection or cleanup. Equal 6-second baseline/polish runs
  were 2.82/2.37 seconds, within codec/startup variance and showing no measured
  overhead regression at this scale.
- The 287.36-second Bella Ciao validation rendered 2,299 1280x720 frames at
  8 fps in 39.75 seconds. Output duration was 287.375 seconds with AAC audio.
  Environmental inside-mask temporal delta was 19.968 versus 0.017 outside,
  preserving local motion and the fixed-frame invariant.

- Bella Ciao: seven semantic/guided masks produced non-empty candidates. Mask
  coverage was hair 1.503%, fabric 2.697%, smoke 0.437%, clouds 2.805%, sun
  source 0.026%, illumination 1.983%, and river reflection 0.386%. The compact
  sun refinement visually isolated the disk. A 2-second 1280x720, 8 fps render
  produced 16 H.264 frames plus AAC and exact 2.000-second duration.
- Static-base check: decoded first/last-frame mean temporal delta was 0.020
  outside all seven conservative search areas versus 0.434 inside; the outside
  99th percentile was 1.0, consistent with codec noise rather than scene
  motion.
- Managed Decline generalization: candle, cloud, and monitor candidates were
  found without engine changes. A stack of seven lanes with only three enabled
  rendered 8 frames at 1280x720 plus AAC with exact 1.000-second duration; four
  unconfigured disabled lanes were skipped.
- Missing semantic assets fell back with the expected diagnostic; strict mode
  raised the documented install instruction. An injected interrupted partial
  was overwritten and absent after successful atomic promotion.
- Bella detection plus 2-second render completed in 21.5 seconds in the direct
  validation harness. Observed process RSS after the run was about 1.80 GiB and
  peak working set about 2.30 GiB while CLIPSeg was resident. Rendering performs
  no CUDA operation; an optional upstream Wan clip generator owns its own VRAM.

Ignored local QA artifacts are under `output/infra_choir_validation/`, including
mask contact sheets and both short MP4s.

## Known limitations

- CLIPSeg proposals are coarse. Bella hair and fabric remain usable review
  candidates rather than production mattes; the reflection lane selects the
  brightest river strip, not every reflected pixel. Keep verification false
  until the preview is acceptable or painted.
- Procedural billow/sway is stable and bounded but not a learned fluid
  simulation. Higher-fidelity organic pixels require an optional short decoded
  Wan clip connected to the target; the starter workflow deliberately avoids
  loading the 14B model merely to remain operational on every run.
- Translation stabilization removes generated camera drift, not arbitrary
  perspective change. Generated organic pixels can leave the original matte
  only within the configured bounded expansion; clips with severe scene warping
  should still be rejected rather than hidden with a loose mask.
- Georgia and DejaVu Serif are local font dependencies, not bundled assets. A
  different fallback font can alter line breaks slightly while preserving
  deterministic fitting, safe areas, and the black/crimson/outline treatment.
