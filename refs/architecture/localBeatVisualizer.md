---
type: Architecture
title: Beat-Aware Local Visualizer
description: Standalone procedural regional-compositing workflow for full-song animated artwork.
status: draft
tags: [architecture, comfyui, audio, compositing, visualizer]
---
# Beat-Aware Local Visualizer

## Purpose

`music_visualizer_local_composite.json` is a new architecture, not an extension
of the Wan motion-poster graph. It keeps the selected still image as the base of
every frame and modifies only six explicit masks. It has no diffusion model,
VAE, text encoder, prompt, seed search, loop variant, camera move, or dependency
on a generated video asset.

The Managed Decline prototype provides editable masks for clouds, candle
flames, red warning lights, the monitor, rain on the windows, and red
reflections. Furniture, cello, architecture, table, chairs, skyline structure,
and other foreground content stay outside those masks by default.

## Data flow

1. Native `LoadImage` and `LoadAudio` nodes load ordinary image and audio files.
2. Six `Local Visualizer Region Mask` nodes construct independent masks from
   normalized boxes, ellipses, or polygons. Optional `red`, `warm`, `bright`,
   and `neutral_bright` pixel filters refine those shapes. Each node exposes a
   preview output for inspection or connection to an ordinary image preview.
   `Suggest Local Visualizer Regions` provides a model-free first pass for a
   new image by ranking grid regions as bright highlights, warm lights, red
   accents, neutral atmosphere, or textured motion. It outputs editable
   normalized boxes, a mask, and a preview; its suggestions are assistance,
   not authoritative segmentation.
3. `Render Beat-Aware Local Visualizer` analyzes the complete audio on CPU.
   It derives normalized RMS energy, low-band energy, high-band energy,
   spectral-flux onset strength, a slow envelope, and a decaying low/onset beat
   pulse.
4. Each region uses a distinct deterministic mapping:

   | Region | Audio mapping | Procedural treatment |
   | --- | --- | --- |
   | Clouds | slow energy | moving low-frequency exposure flow with fixed source geometry |
   | Candles | high band + onsets + seeded irregular oscillator | warm core flicker plus expanded glow halo |
   | Red lights | low/onset beat pulse | red local glow |
   | Monitor | onsets + broad energy | full-display glow and scan variation |
   | Rain | slow energy plus time | denser two-pixel seeded glass streaks |
   | Reflections | beat + slow energy | stronger row-varying red shimmer |

5. Frames are streamed as raw RGB to FFmpeg. FFmpeg encodes H.264/AAC to the
   exact audio duration, so the full video is never accumulated in RAM.
6. Static upper-left wordmark and lower-right studio-badge overlays are derived
   from transparent PNG inputs. The wordmark receives the same configurable
   dark alpha-derived halo used by the guided Wan assembler.

The renderer reports native ComfyUI progress for audio analysis and every
rendered frame. This makes percentage completion visible while preserving the
streaming, bounded-memory architecture.

No effect is model-based in the MVP. Optional CLIPSeg target discovery does not
alter pixels and is not a runtime prerequisite; SAM/SAM2 and optional regional
Wan or LTX motion remain future mask/effect providers.

## Generic target-stack fork

`music_visualizer_target_builder.json` preserves the fixed-source,
bounded-memory renderer but replaces the six named inputs with a repeatable
target lane:

1. `Detect Animation Target` maps an object phrase to a lightweight
   color/texture profile, ranks candidates inside `search_area`, and emits a
   green verification preview with the active area outlined in gold. This node
   remains model-free in the fixed workflow.
2. `Verify / Edit Detection Mask` displays the detector proposal and passes it
   through unchanged by default. Opening that same node in Mask Editor and
   pressing Save persists a per-target correction and automatically uses it on
   the next queue; no separate image or mask upload is required. The correction
   is fingerprint-bound to the source artwork. A new source invalidates and
   clears it rather than displaying or applying pixels from the previous image.
   Its visible **Reset saved mask** button clears a same-source correction;
   the next queue displays and emits the latest detector proposal.
3. `Configure Animation Target` records the verified mask, object name,
   appearance description, explicit motion type, and four independent linear `0..2`
   controls. `on_beat_flicker` and `off_beat_flicker` mix beat-responsive and
   autonomous brightness/color treatments; `on_beat_motion` and
   `off_beat_motion` independently mix beat-responsive and autonomous masked
   subpixel displacement.
4. `Add Animation Target` appends the target to a typed stack. Duplicating the
   detector, editable review, configuration, and stack nodes adds
   another target; the final stack feeds one generic streaming renderer.

`music_visualizer_target_builder_semantic.json` is the separate next-pass copy.
It substitutes `Detect Animation Target (Semantic)` without changing the fixed
workflow or the downstream review/configuration/renderer contract. The semantic
node defaults to `semantic_or_heuristic`; `semantic_only` exposes missing or
runtime failures and `heuristic` explicitly selects the model-free path. The
curated graph contains five complete lanes, which is the intended practical
maximum for the current UI; unused unverified lanes are skipped.

A locally installed CLIPSeg model maps arbitrary text, including object parts,
materials, and atmospheric regions, to a semantic heatmap. Inference uses the
bounding crop of `search_area`, then maps the heatmap back into full-image
coordinates before ranking and masking. This keeps small atmospheric structure
from being erased when a 4K composition is reduced to CLIPSeg's input scale.
Within a constrained crop, an unqualified `smoke` query is evaluated together
with white, gray, and black smoke variants and the maximum response is used.
Explicitly color-qualified smoke queries remain unchanged. Full-frame smoke is
not expanded because clouds and sky otherwise dominate the response; users must
identify the plausible plume area with the gold search box and still review the
resulting mask.

The prompt resolver currently recognizes and combines drift/billow, flicker,
flash/lightning/pulse, scan/display, rain/streak, and shimmer/reflection
treatments. All are procedural and confined to the verified mask. For example,
“clouds drifting and flashing heat lightning on strong beats” resolves to slow
masked drift plus beat-weighted flashes, while “candles flickering” resolves to
warm irregular flicker plus a tighter, faster masked sway. An unrecognized
prompt falls back to atmospheric exposure. Prompts do not semantically parse
the contents of a mask. Spatial behavior comes from `motion_type`: `billow`
uses evolving multi-scale non-rigid deformation, `sway` uses a bottom-anchored
deformation, `drift` translates coherently, and `still` applies no spatial
motion. Billow uses a contracted motion interior so deformation fades before
the mask edge; lighting continues to use the full mask.

Verification is enforced as an inclusion toggle at render time. Unverified
targets are ignored even when they remain in the connected stack; at least one
usable target must be verified. Verified targets with empty masks are logged
and skipped when another verified mask is usable. Identical detector inputs
reuse a bounded in-process cache, avoiding repeated analysis until source RGB
or a detector control changes; the provider and local semantic-asset
availability are part of the cache key. Restarting ComfyUI clears that cache.
CLIPSeg is loaded from `models/detection/clipseg-rd64-refined` with
local-files-only enforcement and runs on CPU so target discovery does not
retain visualizer VRAM.
Each starter lane routes detection through `Verify / Edit Detection Mask`.
Without an edit it immediately emits the detector proposal. Saving in the
built-in Mask Editor stores that lane's painted mask and makes it the emitted
mask on later queues, so correction is optional and requires no second upload.
The review node also receives the unmodified source image and records its
fingerprint in hidden workflow state. When that fingerprint changes, the saved
mask reference is cleared and the new detector proposal is shown and emitted.
`Configure Animation Target.approved_mask` remains an optional advanced socket
for external masks and add/subtract/replace composition.
After all target layers and static badging are composited, the renderer can add
a deterministic traveling glint clipped to the wordmark alpha. The effect is a
small NumPy operation, lightly driven by the high-frequency audio envelope,
and loads no model. `wordmark_sparkle_strength=0` disables it.
The built-in detector is not an open-vocabulary vision model: it maps known
visual concepts to color, luma, neutrality, and texture statistics. Its
proposal is a starting point and may be replaced by any ComfyUI `MASK`,
including a future text-grounded detector or painted mask, without changing
the target or renderer nodes.

## Controls and correction

Mask coordinates are normalized from `0` to `1`, making plans independent of
source resolution. Supported lines are:

```text
box x0 y0 x1 y1
ellipse x0 y0 x1 y1
polygon x1 y1 x2 y2 x3 y3 ...
```

Comments start with `#`. Users can edit these shapes, adjust color filtering,
threshold, and feathering, or replace a mask connection with any standard
ComfyUI `MASK` source. The renderer exposes an independent strength control for
every region and a deterministic seed used only for procedural rain/flicker.

Coordinates use an upper-left origin: `x` runs left-to-right and `y` runs
top-to-bottom, all normalized from `0` to `1`. Thus `box 0.00 0.38 0.33 0.80`
selects from the left edge to 33% of the image width and from 38% to 80% of its
height. Green detector previews and red region/editor previews are equivalent
selection visualizations; neither changes the source artwork. Colored pixels
are included, faint edges are feathered, and darkened unselected pixels are an
editor display aid. Manual add/erase operations update the mask that feeds the
target configuration.

## Dependencies and resources

- Runtime: ComfyUI's existing Torch and Pillow packages, NumPy, and FFmpeg on
  `PATH`.
- Models: none.
- GPU: the custom nodes explicitly move image, mask, and audio tensors to CPU
  and perform no CUDA operation. Any small UI/runtime allocation belongs to
  ComfyUI itself; the effect engine does not load model weights.
- RAM: bounded by the source tensor, six masks, one output frame, cropped effect
  work buffers, audio samples, and compact per-frame feature arrays. The
  completed song is streamed, not retained.

A 12-second representative Managed Decline run produced 192 frames at 1280×720
and 16 fps with exact 12.000-second audio/video duration. It completed in about
16 seconds including Python startup, source/mask preparation, analysis, and
encoding. This is evidence for practicality, not a universal benchmark;
1920×1080, source-resolution delivery, slower CPUs, and encoder contention will
change throughput.

A subsequent complete-song run produced 3,277 frames at 1280×720 and 16 fps,
with audio present and an exact 204.840-second container. The 14.2 MB output
completed in approximately 137 seconds of wall time on the current machine,
faster than real time. The generated review artifact remains outside Git at
`output/local_visualizer_prototype/managed_decline_full_720p_00001_.mp4`.
The saved workflow's default 1920×1080 path was separately checked on the same
source for 12 seconds: 192 frames, audio present, and exact 12.000-second
duration.

After user review found only the red beat pulse readily visible, V3 increased
and differentiated the remaining treatments. A 12-second 1280×720 regression
with title and badge produced 192 frames, audio, and exact 12.000-second
duration. Mean temporal change rose to 3.48 for clouds, 8.05 for candles, 6.81
for the monitor, 3.37 for rain, and 2.47 for reflections; the unmasked control
remained 0.024. This confirms effect activity, but complete-song subjective
review remains required.

## Known limitations

- Geometric masks are intentionally simple. They are inspectable and reliable,
  but irregular targets can require several shapes or an externally painted
  mask.
- Procedural cloud motion is a bounded evolving mesh deformation plus moving
  low-frequency exposure variation, not semantic fluid simulation. Motion is
  contracted away from mask boundaries, but a loose cloud mask can still
  deform admitted skyline pixels in its interior; correct the mask before
  increasing strength.
- Rain is a stylized glass-streak layer, not physics-based condensation.
- H.264 compression means decoded pixels outside masks are not mathematically
  byte-identical, though the pre-encode frame compositor copies them unchanged.
- Audio beat inference is local and deterministic, but is not a musicological
  tempo/downbeat tracker.
- Candidate-region suggestions use lightweight image statistics and coarse
  grid grouping. They can over-select broad similarly colored areas and always
  require preview/correction.
- The optional CLIPSeg provider supplies coarse text-semantic segmentation, not
  guaranteed object identity or production mattes. Dense scenes, sketch
  treatments, ambiguous atmosphere, and similarly described distractors still
  need a constrained search area and review or painted correction. The
  heuristic fallback has the earlier, stricter color/texture limitations.
- Rendering is CPU-bound. `source` mode on a 3840×2160 input is substantially
  more expensive than the default 1080p delivery.

## Recommended next experiments

1. Paint or SAM-assist an irregular cloud-only mask and compare it with the
   checked-in geometric/color-filtered prototype.
2. Add a reusable mask-plan JSON export/import node after the GUI behavior is
   validated.
3. Test optical-flow or displacement-map cloud motion only if a future mask can
   explicitly protect skyline edges; the default keeps source geometry fixed.
4. Add optional section-aware controls after validating beat/onset response on
   several musical styles.
5. Evaluate a regional generative engine only for a target that procedural
   effects demonstrably cannot handle; keep it outside the default path.
