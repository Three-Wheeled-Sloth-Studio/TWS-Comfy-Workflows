---
type: Handoff
title: Current Handoff
description: Standalone beat-aware local compositor prototype plus the retained guided Wan baseline.
status: draft
tags: [handoff, comfyui, music-video, compositing, visualizer, wan]
---
# Current Handoff

## 2026-10-07 Lightweight Visualizer Prototype

A new standalone path now exists at
`user/default/workflows/music_visualizer_local_composite.json`. It does not
modify, extend, or depend on the Wan workflow. Native image/audio loaders feed
six editable mask nodes and one CPU procedural renderer. The renderer derives
low-beat, onset, high-band, slow-energy, and broad-energy features; maps them
independently to clouds, candles, red lights, monitor glow, rain, and
reflections; keeps the source as the static frame base; applies no camera
transform; and streams H.264/AAC output through FFmpeg.

`custom_nodes/comfyui_audio_duration_plan/local_visualizer_nodes.py` contains
`VisualizerRegionMask` and `BeatAwareLocalVisualizer`.
`scripts/build_local_music_visualizer_workflow.py` deterministically builds the
graph with Managed Decline defaults. No model or new Python package was added.

Node-level synthetic validation produced an exact one-second 320×180 H.264/AAC
file. A representative real-source render used the Managed Decline image and
first 12 seconds of its audio, producing 192 frames at 1280×720/16 fps and an
exact 12.000-second container in about 16 seconds including setup and encoding.
Mask contact-sheet review confirmed separate coverage for all six target
classes. The cloud treatment was changed from pixel displacement to restrained
spatial exposure flow so skyline geometry does not move.

The complete Managed Decline track also rendered successfully: 3,277 frames at
1280×720/16 fps, audio present, exact 204.840-second duration, 14.2 MB, and
about 137 seconds wall time. The ignored local review file is
`output/local_visualizer_prototype/managed_decline_full_720p_00001_.mp4`.
A separate real-source default-resolution check produced 192 frames at
1920×1080/16 fps with audio and exact 12.000-second duration.

The next review is subjective: inspect the complete-song prototype, then tune
individual masks and strengths. Geometric/color-refined masks are intentionally
simple; painted masks or optional SAM assistance are the leading next step for
irregular cloud/reflection boundaries. Full design and limitations are in
`refs/architecture/localBeatVisualizer.md`.

The initial serialized graph omitted ComfyUI's frontend-only
`control_after_generate` value after the renderer seed. Desktop consequently
shifted every later widget left and tried to parse `output_prefix` as
`reflection_strength`. The builder now writes `"fixed"` after the seed and
asserts the final widget positions before saving the workflow.

A subsequent Desktop retry showed that relying on this hidden widget remained
fragile for an already-open graph. The renderer schema now calls the
deterministic integer `pattern_key`, which does not trigger seed-widget
special handling, and the regenerated graph uses the fresh
`BeatAwareLocalVisualizerV2` node type so cached V1 layout cannot be reused.

User review of the completed V2 render found the beat-aware red-light pulse
good, but no other motion perceptually obvious. Measurement showed those masks
were active but weak: clouds 0.11, rain 0.39, reflections 0.51, and monitor 1.30
mean temporal delta versus 0.024 outside all masks. V3 keeps the successful red
pulse, adds moving cloud exposure, candle halos, full-screen monitor
variation, denser rain, and stronger reflection shimmer. Its 12-second 720p
regression raised those deltas to 3.48, 8.05, 6.81, 3.37, and 2.47 respectively
while leaving the unmasked control at 0.024.

V3 also adds native ComfyUI progress reporting, a model-free candidate-region
assistant with editable box output/mask preview, and the guided Wan workflow's
post-process badging pattern: upper-left track wordmark with dark halo and
lower-right studio badge. The workflow currently selects the local Managed
Decline wordmark and TWS badge. Restart the backend before opening V3 so the
new node schema is registered. Complete-song subjective V3 review is next.

Complete-song review accepted the progress display and all strengthened effects
except the cloud pass: its rounded source displacement looked glitchy and moved
buildings admitted by the cloud mask. The cloud treatment now animates only a
continuous low-frequency exposure field over the unchanged source crop. This
keeps skyline and building geometry locked while retaining slow audio-reactive
atmospheric variation. All six strength controls remain linear `0.00`-`2.00`
multipliers in `0.05` steps (`0` off, `1` designed baseline, `2` twice the
configured effect amplitude); clipping and masking can make perceived response
nonlinear near the extremes. Low GPU utilization is expected because the path
is intentionally CPU/NumPy plus streamed FFmpeg encoding and loads no model.

The generalization fork is now
`user/default/workflows/music_visualizer_target_builder.json`; the accepted V3
graph remains unchanged. The new graph contains repeatable object detector,
verification preview, prompt/beat-mix configuration, and target-stack nodes.
Every target has separate linear `0..2` on-beat and off-beat controls, and the
renderer accepts an arbitrary-length stack. Prompts can combine drift/billow,
flicker, flash/lightning/pulse, scan, rain, and shimmer treatments without
translating source geometry. Unverified or empty masks stop rendering with an
actionable error. A 12-second three-target integration render completed with
192 1280×720 frames, AAC audio, and exact 12.000-second duration.

The installed environment has no text-grounded detector or SAM node. The new
detector therefore remains an explicitly model-free color/texture proposal
generator. Forced-verification QA showed why the gate matters: coarse initial
boxes can admit unrelated structures, especially clouds in a dense scene. The
detector now refines boxes to matching pixels, but users must inspect previews,
constrain `search_area`, or replace the detector output with a painted or future
semantic mask. Optional text-grounded segmentation is the next quality lever;
it is not misrepresented as solved by the current heuristic.

## Closeout Status

The guided motion-poster workflow is accepted as production-ready at its current
quality bar. The production baseline is 1024×576 exact-16:9 generation, one variant, neutral camera, conservative
anti-lip-sync guidance, optional post-process logo and wordmark, exact song
duration, and default 1920×1080 Lanczos delivery. Remaining items are deferred
enhancements or known input-suitability limits, not blockers to ordinary use.

## Product Bar

Create a full-song 16:9 video that remains true to supplied artwork, contains
restrained plausible motion, and is engaging enough for a casual YouTube
listener. Cinematic continuity, beat synchronization, and timed lyrics are not
MVP requirements. Obvious failures—especially inaccurate lip sync, invented
mouth motion, identity drift, and damaged composition—are unacceptable.

## Accepted Architecture

1. Use one guided ComfyUI graph for the ordinary workflow: choose the primary
   reference image and song, enter motion guidance, choose one to three
   variants, and queue once.
2. Generate short Wan motion assets at the validated 1024×576 exact-16:9
   production resolution. Never use the earlier square proof or crop/stretch a mismatched
   source into the delivery frame.
3. Give Wan explicit physical motion guidance. Background-only is the safe
   default. Preserve identity, face, expression, mouth position, pose, framing,
   clothing, and composition.
4. Default the negative prompt against lip sync, singing, talking, mouth
   movement, facial drift, scene changes, warping, and whole-image pulsing.
5. Build closed ping-pong cycles, crossfade variants into a closed reel, stream
   it to the exact audio duration, and upscale only afterward. The legacy
   manifest and command-line renderer remain diagnostic/reproducibility tools,
   not the normal user interface.

## What Landed

- `custom_nodes/comfyui_audio_duration_plan/motion_poster_nodes.py` provides
  editable safe prompt construction, deterministic one-to-three variant seed
  planning, song-title-based naming, dual branding overlays, and full-song
  FFmpeg assembly with preview and saved output.
- `user/default/workflows/video_wan2_2_14B_s2v_motion_poster_guided.json` is the
  primary guided workflow. It generates the selected variants and assembles the
  final MP4 in one queue operation; no manifest editing or Python command is
  required for normal use. It exposes one reference-image picker, one audio
  picker, and two optional branding-image pickers; the unrelated square example
  graph inherited from the source JSON is pruned by the builder.
- `scripts/build_guided_motion_poster_workflow.py` deterministically regenerates
  and structurally validates that guided workflow.
- `user/default/workflows/video_wan2_2_14B_s2v_motion_poster_visualizer.json`
  is a separate experimental copy. Its dedicated assembler analyzes audio on
  CPU and draws a chromatic 24-bar stereo radial spectrum around the clean
  logo. Low bands begin at the bottom, high bands end at the top, left/right
  audio stays on its respective side, and smoothed band energy controls radial
  length and brightness. It composites only during final rendering.
- `scripts/build_guided_motion_poster_visualizer_workflow.py` regenerates that
  experimental copy without changing the production workflow.
- The visualizer passed coherence testing, but user review found it too
  visually dominant in the lower-right corner. It is preserved for future
  iteration and is not the production recommendation.
- `README.md`, `refs/operations/localSetup.md`, and
  `refs/operations/troubleshooting.md` contain the user-facing installation,
  workflow-selection, settings, caveat, and recovery guidance.
- All committed workflows and example manifests use neutral `select_*`
  placeholders. Studio source image/audio files and rendered outputs remain
  outside the repository.
- The assembler exposes `source`, default `1080p`, and `1080p_fill` delivery
  modes. The production 1024×576 source is exact 16:9, so the 1080p path
  Lanczos-scales the complete picture directly to 1920×1080 without padding or
  crop, then composites both branding inputs. It requires no upscale model.
- `scripts/build_motion_loop_workflow.py` derives a short two-chunk Wan workflow
  from the source S2V graph. It remains the base graph and an advanced
  diagnostic path, producing roughly 9.5 seconds at 832×480 / 16 fps.
- `user/default/workflows/video_wan2_2_14B_s2v_motion_loop.json` is the curated
  workflow with editable motion guidance and anti-lip-sync defaults.
- The builder accepts a v2 project manifest and can write an ignored active
  workflow with the selected audio, primary image, dimensions, and prompts.
- `assets/motion-poster.example.json` v2 records audio, reference image(s),
  optional untimed lyrics, generation prompts, expected loop variants,
  crossfades, camera drift, and encoding settings.
- `scripts/render_motion_poster.py` accepts one or more loop variants, closes
  each reversal, crossfades variants into a repeating reel, and streams the
  final H.264/AAC output with bounded memory.
- The renderer rejects aspect-ratio mismatches instead of cropping or
  stretching them. The previous 640×640 proof clip is no longer an eligible
  production input.

## Validation Evidence

The earlier square proof established that closed ping-pong looping and exact
audio-duration assembly work, but its crop and unintended lip motion make it
unsuitable as a base asset.

The v2 assembler passed a synthetic three-variant test at 832×480. It produced
192 frames at 16 fps with a 12.000-second video/audio container, crossfaded all
three closed cycles, and reported zero duration delta. A direct regression test
confirmed that a 640×640 loop is rejected with a no-crop/no-stretch error.

The new guided assembler node also passed a direct synthetic three-variant
test. It accepted image tensors and stereo audio through the same interfaces
used by ComfyUI, produced a 160×96 H.264/AAC preview at 8 fps, and matched the
2.000-second test audio exactly. The generated guided graph passed structural
checks for its prompt, seed-list, image-list, audio, and assembler links. A real
Wan run subsequently validated the same path in Desktop.

On 2026-10-01 Comfy Desktop 0.38.1 was confirmed as the authoritative running
instance on port 8000. Its generated model-path configuration uses
`C:\Users\sloth\ComfyUI-Shared\models` first and the project `models/` directory
second. All five Wan assets are installed in the shared root and visible to the
live loader nodes. The earlier manually launched 0.21.1 backend used a stale
model-path configuration and must not be used as evidence that models are
missing.

A matching production audio/reference-image pair was validated locally without
adding either source file to the repository. Desktop successfully generated a
159-frame, 832×480, 16 fps, 9.9375-second motion loop. Contact-sheet review
showed preserved composition and stable mouth/expression with subtle background
variation.

On 2026-10-01 ACE-Step 1.5 was installed for the same Desktop instance using
ComfyUI 0.38.1's native nodes and built-in `Text to Audio (ACE-Step 1.5)`
blueprint. No third-party node or Python dependency was added. The blueprint's
four exact Comfy-Org assets—standard turbo diffusion model, 0.6B conditioning
encoder, 4B planning LM, and ACE 1.5 VAE—were downloaded to
`C:\Users\sloth\ComfyUI-Shared\models`, verified against the publisher's
SHA-256 digests, and confirmed visible through the running backend's loader
schemas without restarting Desktop. The optional XL, base/SFT, and alternate
LM assets were intentionally not installed; they are not required by the
shipped workflow and the standard 2B turbo model is the appropriate upstream
tier for the local 12 GB RTX 4070.

The first real one-variant guided GUI run completed quickly and produced
`output/motion_poster/guided_motion_poster_00001_.mp4`: 832×480 at 16 fps with
a 244.080-second container matching the song. User review found the underlying
animation smooth and the overall result good. Two limitations were observed:
Wan mangles text embedded in the reference art, and the assembler's whole-frame
camera drift is visibly jerky. Text/branding can remain a post-process overlay.
The pan issue is consistent with FFmpeg crop-coordinate quantization: at the
default amplitude/period, ideal movement is substantially below one pixel per
frame, so crop positions hold and then jump.

Testing with the remaining reference images exposed an additional base-generation
limit: Wan visibly blurs or distorts faces when they are not large and central
in the composition. This feedback predates testing of the new 1080p delivery
path, so it is not an upscale artifact. Lanczos will preserve—and may make more
visible—damage already present at 832×480; it cannot restore missing facial
detail. Small or off-center important faces require source-resolution review
and are candidates for a future protected/static-foreground or regional-motion
mask rather than generative face enhancement.

On 2026-10-02 the user reported a more severe generative failure: one run
invented a new central face, while broad prompting often ignored smoke, local
lights, and background tentacle-like forms. The guidance node now provides an
empty per-image `motion_targets` field that appends a strict animate-only-these-
existing-regions instruction. The preservation text fixes all existing people
and faces in place, and the negative default explicitly rejects extra,
duplicate, new, background, and disembodied faces or people. This is a cheap
risk reduction, not a guarantee; an affected seed must still be rejected and a
regional/static-foreground mask remains the robust future control.

A follow-up run with horizontal and vertical drift disabled looked materially
better and was accepted as the near-term default. Camera zoom `1.0` is neutral;
zero is not a valid scale. The guided graph now defaults to neutral zoom and
zero drift, names output files from an editable song-title field, exposes
editable positive and negative prompt fields, collapses the linked read-only
conditioning nodes, and removes stale lower-canvas groups and unused subgraph
definitions.
The workflow uses native `LoadAudio` for frontend reliability. A custom loader
was registered successfully by the backend but serialized without a
`class_type` in Desktop, producing an otherwise-unspecified missing-node error
for node 58. Output naming therefore uses a visible song-title field in the
assembler; update it when selecting different audio.

The real three-variant run was operationally successful: increased generation
time remained within tolerance, GPU utilization stayed near 95%, and no heat
problem appeared. It failed the visual quality bar. The transitions looked like
the three variants were layered together, introduced substantial blur, and
smoothed the lighting flicker until it was nearly absent. One variant remains
the default; alternative multi-variant transition strategies are pinned as
future work.

Two independent post-process branding inputs are now available. A transparent
brand logo can be enabled at lower right with a default 12% width and 72%
opacity; a transparent wordmark can be enabled at upper left with a default 35%
width and 95% opacity. Each has separate enable, size, opacity, and margin
controls. FFmpeg applies both after generation, so Wan cannot deform their text
or artwork. A synthetic dual-overlay regression test confirmed upper-left and
lower-right placement plus exact one-second video/audio duration; the user then
validated the branded result visually and accepted it.

The upper-left wordmark now has a procedural halo underlay. `dark` and `light`
styles are derived from the supplied PNG's alpha channel, padded, blurred, and
composited beneath the clean wordmark with independent opacity and blur
controls. A synthetic regression produced exact one-second source and
1920×1080 `1080p_fill` outputs with both halo styles. `1080p_fill` is an
explicit alternative that removes side bands by slightly center-cropping the
832×480 generated frame; the no-crop `1080p` mode remains the default.

The user then validated a guided run at 1024×576. Its visual quality was
accepted, runtime remained within the acceptable production envelope, and the
encoded MP4 was smaller than the preceding output. Because the generation and
delivery canvases are both exact 16:9, the production path no longer needs
side padding or a fill crop. The deterministic builder now pins 1024×576 so a
workflow regeneration cannot silently restore the older 832×480 setting.

The audio-reactive logo pass is implemented in a separate workflow. Its second
iteration replaced the whole-logo dominant-note tint with twelve logarithmic
frequency bands per stereo channel. Synthetic channel-separation tests placed
110 Hz left-channel energy on the lower-left and 1760 Hz right-channel energy
on the upper-right, while the full twelve-color chromatic palette remained
available. An end-to-end test composited the padded halo without edge clipping
and produced an exact 3.000-second 320×180 H.264/AAC output. Silence retains the
static fallback. A later representative run passed coherence review but was
too visually dominant in the lower-right corner, so the effect is deferred.

A synthetic delivery-scale regression test passed both assembler modes. The
source case retained its 160×96 test dimensions; the 1080p case produced exact
1920×1080 H.264/AAC output, and both matched the one-second test audio exactly.
The test included both branding overlays after scaling. The user subsequently
accepted the overall workflow as good enough for production use; optional AI
enhancement and further subjective upscale comparisons remain future work.

A private local manifest assembled a complete song into 3,905 frames at
832×480 and 244.080 seconds, H.264/AAC, with a 0.000021-second source-duration
delta. The closed-cycle boundary luma-difference average was 5.23/255. The
manifest and its media-specific paths are not retained in the repository.

## Current Usage

Restart Comfy Desktop once so it discovers the new project-owned nodes, then
open `video_wan2_2_14B_s2v_motion_poster_guided.json` from the workflow menu:

1. Select the cover art in `Load Image` and the song in `Load Song`.
2. Edit the positive and negative text in `Motion Poster Guidance`; leave lip
   motion disabled. In `motion_targets`, name exact existing regions and their
   physical motion, separated by semicolons. Optional lyrics or theme text can
   guide the atmosphere.
3. Set `variant_count` in `Motion Poster Variant Seeds`. The base seed defaults
   to `randomize` after each queued run; switch it to `fixed` to reproduce a
   known run. Keep one variant for normal quality; two or three remain
   experimental until their transition blur is fixed.
4. Set optional crossfade/camera controls in `Assemble Full Motion Poster`.
   Zoom `1.0` means no zoom and drift defaults to zero. Update the song-title
   field when changing audio; it is prepended to the output filename.
5. Optionally select transparent PNGs in the lower-right brand-logo loader and
   upper-left wordmark loader, then enable and tune either overlay in the
   assembler. The wordmark halo defaults to a dark 55%-opacity, 18-pixel blur;
   choose `light` or `off` as needed.
6. Leave `delivery_resolution` at `1080p` for the exact 1920×1080 YouTube-ready
   no-pad/no-crop output, or choose `source` for a 1024×576 diagnostic render.
   `1080p_fill` remains available for non-16:9 diagnostic assets but is
   equivalent to normal scaling for the production canvas.
7. Queue once. The final node previews and saves the full-song MP4.

The experimental
`video_wan2_2_14B_s2v_motion_poster_visualizer.json` remains installable for
future design work, but the primary guided workflow and static logo are the
current recommendation. Its present radial treatment passed coherence testing
but draws too much attention to the lower-right corner.

Variant frames are held in memory only until assembly begins. Full-song
encoding is streamed through FFmpeg and does not retain the completed song's
frames in memory. The older manifest workflow remains documented in `README.md`
for reproducible diagnostics.

The first reference image currently drives Wan. Additional images are retained
as project context but are not yet independently conditioned. Untimed lyrics
may inform atmosphere or a prompt summary; time-specific animation waits for
timing marks.

## Deferred Future Work

- Protect small or off-center faces with static-foreground or regional-motion
  masking; do not treat generative face enhancement as the default repair.
- Revisit multi-variant transitions using short transitions, low-motion cuts,
  or section-level alternation rather than the blur-producing crossfade.
- Compare optional AI upscaling only if added detail can preserve temporal
  stability and artwork fidelity better than the accepted Lanczos path.
- Redesign or substantially soften the experimental brand-logo visualizer
  before reconsidering it for the production workflow.
- Add timed-lyric and richer multi-reference guidance in a later iteration.
- Revisit subpixel/supersampled camera movement only if nonzero drift becomes
  valuable.
- Keep native full-song Wan continuation, GPU-retention diagnosis, and durable
  chunk checkpoints as a separate experimental track.

## Required Reads

- `refs/architecture/localBeatVisualizer.md`
- `custom_nodes/comfyui_audio_duration_plan/local_visualizer_nodes.py`
- `scripts/build_local_music_visualizer_workflow.py`
- `user/default/workflows/music_visualizer_local_composite.json`
- `refs/planning/decisions.yaml`
- `refs/implementation/dependencyPolicy.md`
- `refs/operations/localSetup.md`
- `refs/operations/troubleshooting.md`
- `custom_nodes/comfyui_audio_duration_plan/motion_poster_nodes.py`
- `scripts/build_guided_motion_poster_workflow.py`
- `user/default/workflows/video_wan2_2_14B_s2v_motion_poster_guided.json`
- `scripts/build_guided_motion_poster_visualizer_workflow.py`
- `user/default/workflows/video_wan2_2_14B_s2v_motion_poster_visualizer.json`
- `scripts/build_motion_loop_workflow.py`
- `scripts/motion_poster_manifest.py`
- `scripts/render_motion_poster.py`
- `assets/motion-poster.example.json`

## Do Not Reopen

- Do not use the square proof clip as the production base.
- Do not crop or stretch mismatched loop assets into the delivery frame.
- Do not make native full-song Wan continuation a production prerequisite.
- Do not infer mouth, body, or whole-image motion from audio amplitude alone.
- Do not make manifest editing or command-line scripts part of ordinary usage.
- Do not track models, input media, outputs, logs, caches, or general user state.
