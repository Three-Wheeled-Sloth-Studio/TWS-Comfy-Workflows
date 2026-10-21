---
type: Handoff
title: Current Handoff
description: Standalone beat-aware local compositor prototype plus the retained guided Wan baseline.
status: draft
tags: [handoff, comfyui, music-video, compositing, visualizer, wan]
---
# Current Handoff

## 2026-10-20 Next Video Quality Priorities

Raise the Neon Black v2 `_00002_` is the current accepted render. The old
overlap reset caused 9.44 median boundary change versus 1.49 normally. Correct
`N-overlap` indexing reduced all 21 regenerated full-song boundaries to 1.414
median and 1.667 maximum, below the 3.235 ordinary-frame 95th percentile.
Crossfade-reset ghosting is fixed; other model/encode fuzz still requires the
planned lossless stage comparison.

Next, test Wan 2.1 VACE 1.3B separately at 832x480/~81 frames on the next
user-selected art. No checkpoint is installed. Gate runtime/VRAM, source and
static-region fidelity, intended motion, and seam quality before an 8-second
compositor probe. Details are in
`refs/evaluations/2026-10-20-next-video-motion-quality-plan.md`.

## Fast-Moving Production State

Production inputs change frequently. Never infer the current base image, song,
target boxes, prompts, effect settings, branding, or output prefix from this
handoff, an older workflow, file timestamps, or a previously prepared
candidate. At the start of every production task, inspect the user-designated
live workflow and treat its saved values as authoritative. Historical image and
song names below describe the state observed during a specific audit only; they
are not defaults and must not be written back into a workflow unless the user
explicitly selects them for the current production.

## 2026-10-20 Raise the Neon Black Motion Test

The user explicitly selected the Raise the Neon Black `Banner.png` and FLAC for
one fixed-seed environmental-motion test. A separate 1024x576 candidate was
built and queued without modifying the dual-track scaffold. Both Wan segments
generated successfully, but the first final save failed because the 192 kHz
source master is unsupported by AAC. A save-only retry reused every generated
node from cache and produced a 9.9375-second review clip; an audible copy was
then muxed at 48 kHz without regeneration. The candidate workflow now uses a
lossless 48 kHz working FLAC while the production master remains untouched.

Hair, the large flag, waves, and underwater tentacles move visibly; the face,
pose, buildings, and cranes remain comparatively stable. Storm clouds and
waterline fog move, but the fog is moderate rather than ample. The extension
join is clean, while the end-to-start boundary still needs deterministic loop
assembly. The stable composition remains suitable for later music-synchronized
procedural lighting/glow and title-card layers. See
`refs/evaluations/2026-10-20-raise-neon-black-motion-test.md` for runtime and
measurement evidence.

## 2026-10-19 Hybrid Atmosphere Candidate Gate

The shortest path to the requested organic-quality improvement is candidate C:
one contextual full-scene Wan clip, confined to the reviewed smoke masks, with
the established procedural renderer retaining lights, reflections, audio
envelopes, title, wordmark, EQ, and exact-duration assembly. No new diffusion
model or full compositor rewrite is required for this first quality gate.

Cached-clip handling now fails closed when `cached_clip` is explicitly selected:
a blank path, missing/undecodable file, or first frame that does not structurally
match the selected artwork raises an actionable error. Automatic and
`cached_clip_then_procedural` modes retain intentional fallback behavior. The
QA report includes the clip/source similarity score.

A separate, snapshot-specific workflow,
`user/default/workflows/video_wan2_2_14B_s2v_infra_choir_atmosphere_candidate_v1.json`,
is reproducibly built from the retained motion-loop workflow. It selects the
image/audio observed during the recovery audit, fixed seeds, the installed four-step Wan path, and
prompts for independently billowing cigarette/piano smoke while strongly
protecting people, faces, geometry, exposure, and camera position. It saves to
`output/infra_choir/motion_assets/`. The expensive generation has not been
queued and this candidate must not be treated as production-ready or queued
until its image, audio, prompts, and output prefix are rebound to the
user-designated live production state. The handoff stop rule requires human
approval before this materially different visual path consumes GPU time. The dual-track scaffold remains
byte-identical to its recovered hash. The focused renderer test exercises the
strict missing-clip path directly, a known older wrong-artwork clip is rejected
at 0.048 similarity, and every command in `validationCommands.yaml` passes in
the isolated validation worktree.

## 2026-10-19 Priority-0 Live-State Recovery

The live workflow directory and Git working tree were audited before any new
implementation work. The authoritative scaffold remains
`user/default/workflows/music_visualizer_infra_choir_dual_track_scaffold.json`
with SHA-256
`A7EE372E260DA42B609E068D38443F092C62B92351C8809CF77A0CF61FB93E7E`.
It is an untracked live workflow and therefore has no direct committed version;
the comparison baseline is the October 12 production commit
`e774788fe6e73e099ad1da7590163eeaee02c343`. A byte-for-byte recovery snapshot
of all 107 workflow-directory files plus the project-owned custom node was
created at
`C:\Users\sloth\Documents\ComfyUI-recovery-snapshots\2026-10-19_priority0_pre_recovery`;
all source/snapshot workflow hashes matched.

The scaffold state observed during the recovery audit was `Photo.png` with
`Static in the Champagne Room.mp3`, title and wordmark enabled, custom EQ colour
`#f58e87`, 512 regular bands plus 2048 ultra bands, and output prefix
`infra_choir/TWS_`. Five manual detector lanes are enabled and two are disabled.
The four-mask approved discovery manifest is image-fingerprint current, but the
merge policy is intentionally `manual_only`, so those auto masks are preserved
without affecting the render. Both smoke lanes currently select procedural
motion and have blank cached/generated clip paths.

Focused discovery/merge, generated-clip decode and looping, title/EQ, schema,
and enhanced-analysis tests passed. An 8-second real-image/audio render also
passed and left the scaffold hash unchanged. The complete repository validation
list, including every workflow builder, was run only inside an isolated Git
worktree beneath the recovery snapshot; all commands passed and no live
workflow was regenerated. No scaffold value, target mask, media selection,
box, prompt, link, or graph position changed during recovery.

## 2026-10-15 Manual Effect Cards and Advanced Settings Popout

The authoritative live workflow is
`user/default/workflows/music_visualizer_infra_choir_dual_track_scaffold.json`.
There is intentionally no TWS/Video duplicate. The saved workflow uses
`Photo.png` and `Static in the Champagne Room.mp3` at the time of that work; its manual boxes,
prompts, include choices, node positions, and links are user state and must not
be regenerated from the earlier Bella Ciao baseline.

All seven manual effect cards now keep only likely day-to-day controls on the
graph and provide one **Advanced Settings…** button. The button opens a modal
editor rather than creating graph nodes or wires. Per-target audio drivers,
ADSHR response, grouping, detailed glow/shimmer, generated-motion, and cached
atmosphere-clip controls serialize into a hidden per-card JSON field. Existing
visible controls and the detector-side inclusion toggle retain their current
behavior. The migration modified only the seven effect nodes by adding that
field and shortening their heights; a structural guard verified every other
saved value was unchanged. Focused backend and workflow regression tests pass;
a Desktop reload is still required to load the new frontend extension and node
schema before visual popout QA.

The first post-reload save exposed a frontend serialization defect: changing a
hidden widget's type caused ComfyUI to omit `target_id`, shift every following
value one field left, clamp some values to the wrong numeric ranges, and drop
the advanced input declaration. The popout now hides rows only through zero
layout height while retaining each widget's original serialization type. The
seven affected cards were repaired from their last known-good values in the
root workflow; jazz media, boxes, links, positions, and all unrelated nodes
were preserved. The light and lamp lane names were retained explicitly rather
than restoring the older sun-specific labels.

A subsequent visual review found that technically active effects were still
perceptually muted: the latest full-song output showed roughly 7–9 luma levels
of smoke-region variation but only 1.5–1.6 levels in the light regions. The
non-geometric smoke safety path had removed source-pixel translation without
replacing it with sufficiently legible density transport, and the enhanced
lighting transfer remained too conservative after soft-mask compositing.

Procedural smoke now advects a stronger multi-scale synthetic density field
while source pixels remain fixed. Enhanced luminance and glow transfers are
stronger but remain bounded by each card's explicit caps. The active smoke
lanes now use intensity 2.2/2.0 and billow 1.15/0.95; the active light,
illumination, and reflection lanes use stronger flicker/luminance settings,
with reflection shimmer at 0.35. The modal no longer exposes generated-motion,
shimmer, lighting, or motion controls on roles where they do not drive the
renderer. Its role-specific help explicitly names the primary on-card controls.
No media, masks, box coordinates, links, node positions, or prompts changed.

A later load/save was performed by a still-running frontend instance that had
the older hidden-widget serialization behavior. It omitted `target_id` from all
seven compact manual cards and shifted every subsequent value left: advanced
JSON appeared in `hue_variation_degrees`, atmosphere boundary values appeared
as smoke intensity, and light radius/hue values appeared as glow/saturation.
The authoritative scaffold was repaired by restoring the seven cards' widget
prefixes and named values only. Current user media, boxes, prompts, inclusion
choices, role/motion selections, renderer settings, positions, and links were
left unchanged. The focused dual-track regression passes. The running ComfyUI
frontend must be fully refreshed before this workflow is loaded and saved
again so it uses the corrected `computeSize`-only hiding extension.

The server history payload subsequently proved the inverse compatibility
problem: the live frontend still declared the legacy leading `target_id`
widget while the backend and saved scaffold did not. It therefore dropped the
first saved value and submitted every remaining value under the field name to
its left, producing the exact 21 role/type/range errors. The durable contract
now restores `target_id` as the first hidden-but-serialized widget in both
compact node schemas; the Advanced Settings modal edits that real widget, and
the root scaffold contains matching IDs in its inputs, positional values, and
named values. The migration touched only the seven manual effect nodes and
preserved the user's media, boxes, prompts, role/motion selections, renderer
settings, layout, and links. The focused dual-track regression passes.

The remaining 21 validation errors were traced to a connected `forceInput`
Boolean consuming a hidden positional widget slot during frontend load. The
authoritative root scaffold now carries that slot on all seven effect cards,
and the frontend extension restores and saves those cards through
`widgets_values_named` so future frontend serialization cannot shift role,
motion, numeric, or advanced-JSON values again. A live Desktop refresh loaded
all seven IDs, roles, motion types, and numeric controls in their intended
fields with no validation issues listed. The repair did not change the user's
media, detector boxes, prompts, effect values, layout, links, or any other
workflow.

Two detector cards (`lights` and `lamp`) still carried an extra leading
Boolean in their positional arrays, shifting `find` through
`detection_provider` and producing six additional validation errors. Those
two surplus values were removed without changing either detector's named
settings. Named-field load/save recovery now also covers all manual detector
cards, and the regression test verifies exact positional-to-named alignment
for all seven detector/effect pairs. A live Desktop refresh showed sensitivity
0.58/0.40, max regions 6, provider `semantic_or_heuristic`, and no validation
errors.

The next valid full-song render (`TWS_00002_.mp4`) proved that correct values
were reaching the renderer but the enhanced transfer functions still muted
them below practical visibility. Decoded upper-frame motion averaged only
0.01-0.08 luma between adjacent frames; lighting was especially weak because
the linear envelope occupied a narrow middle range and Gaussian glow diluted
small source masks. Enhanced lighting now uses a smooth high-contrast gate
bounded by each card's existing luminance cap, and emissive glow preserves the
source mask while adding a normalized halo. Procedural smoke now uses stronger
non-geometric density transport with no source-pixel displacement. An 8-second
actual-image/audio diagnostic with EQ, titles, and branding disabled measured
60-68 luma of smoke excursion, 27 for the light source, 13 for illumination,
and 9 for reflection inside their verified masks. The user's workflow values,
boxes, prompts, layout, and media were not changed. ComfyUI must be restarted
before the live backend uses this renderer update.

Visual inspection then rejected that stronger procedural-smoke treatment: it
made the masks read as glowing translucent haze rather than flowing smoke. The
fallback no longer introduces a pale synthetic layer. It now advects fine and
broad texture extracted from the source image and applies only the transported
texture difference, keeping the region's mean colour stable. On the same
8-second jazz-image probe, per-pixel temporal ranges inside the two smoke masks
were 51.3 and 19.3 luma while whole-frame mean drift was only 0.53. Contact
frames showed no white veil, and the authoritative workflow SHA-256 was
identical before and after the probe. Wan/cached clips remain the production
route for genuinely generated smoke detail; the procedural path is explicitly
the model-free fallback. The live backend must reload the project node before
using this correction.

## 2026-10-14 Infra Choir Dual-Track Scaffold Implementation

The requested dual-track candidate is now wired to project-owned backend node
classes at
`user/default/workflows/TWS/Video/music_visualizer_infra_choir_dual_track_scaffold.json`.
The enhanced workflow remains the rollback baseline. Setup actions are explicit
and idle by default; manifests are image-bound, merge modes deterministic, and
stale data loads empty. Titles stay bounded, ultra EQ uses distinct FFT bins,
and atmosphere supports protected expansion or offline clips without diffusion.

Automated regression and dual-track tests pass. The candidate still requires a
Desktop restart/import, manual-only/auto-only/both full-song visual QA, and a
separate RTX 4070 12 GB Wan-clip benchmark before promotion. Details are in
`refs/architecture/infraChoirDualTrack.md`.

Setup feedback is now visible: discover/apply show a preview, actions show node
status/toasts, and the primary label explicitly lists lights, reflections,
smoke/fog, and flame. Idle is the render-safe no-op.

Live dual-track rendering exposed a backend-starvation failure: the 28%-radius
smoke expansion reached a 605x605 Pillow `MaxFilter` at 1080p, held the Python
backend on one CPU core before FFmpeg started, and made `/queue` and frontend
requests report `Fetch Timeout` even though the process remained alive. Large
mask expansion now uses equivalent separable SciPy maximum filters with a
bounded downsampled Pillow fallback. The active queue was not interrupted and
the visually arranged scaffold JSON was not rewritten; the fix takes effect
after ComfyUI next reloads the project node.

Review of `discovery_00002_.mp4` and its saved masks then identified why lights
still appeared to slide despite correct `motion_type: still` JSON: the smoke
detector had also selected chandelier and foreground-detail regions, so the
later smoke layer spatially warped pixels owned by static classes. Rendering
now gives auto-discovered light, illumination, reflection, flame, and human
classes priority over smoke/atmosphere masks, including a small safety margin,
and reports the protected overlap percentage in QA. Auto lighting classes also
receive minimum visible flicker/luminance contracts, while flame is spatially
still. Future discovery combines person and face protection with a larger
margin. This is node-code-only; the user's arranged scaffold layout remains
untouched.

The next reviewed render showed this was still insufficient: CLIPSeg continued
to label the small piano player's head as smoke, class-overlap protection made
real smoke too subtle, and measured light-mask variation was only 0.6-1.4 luma
levels. Auto smoke/atmosphere therefore no longer resamples neighboring source
pixels at all. It now uses a stronger moving haze-opacity field, which can show
billow without translating a falsely included head or fixture. Lighting classes
now have materially higher but bounded flicker and luminance floors. The
semantic exclusions remain useful, but visual safety no longer depends on the
human detector finding every small background face.

A six-second 1280x720 direct QA against the audit-time `Photo.png` manifest then
verified the revised transfer: illumination varied across an 11.9-luma 1st-to-
99th-percentile range, reflections 8.7, and smoke 5.1. Phase correlation over
the piano-player crop measured 0.001 px median and 0.009 px maximum apparent
shift, effectively codec noise rather than source-pixel motion.

Subsequent mask review rejected CLIPSeg discovery as the production path for
this dense scene: it grouped separate plumes into giant boxes, missed the large
couch-to-piano smoke cloud, selected a piano-player head, and favored weak or
unlit chandelier regions over obvious lamps, sconces, and building lights.
Threshold tuning cannot make a coarse semantic heatmap behave like referring
instance segmentation. The arranged scaffold now defaults to `manual_only` and
keeps every node position and size unchanged. Its two atmospheric lanes replace
the ambiguous cached-loop/expansion widget labels with `smoke_intensity` (0-3)
and `smoke_boundary_expansion_percent` (0-50). Manually boxed smoke/clouds use
non-geometric haze billow across the expanded support, so high intensity does
not drag source objects inside the box. Boundary percentage is relative to the
manual mask's own larger dimension rather than the full frame.

The manual-only retest found lighting correct but smoke visually static. Initial
saved-file inspection incorrectly blamed verification; ComfyUI run history then
proved both submitted `mask_verified` values were true. The actual defect was
double application of each soft smoke mask inside billow and again at final
composite, reducing piano-smoke variation to the level of a static control
region. Billow now uses binary support internally and the soft mask exactly once
at composite, with a stronger intensity range. The two atmosphere lanes now use
compact effect cards; `include this mask` lives on and is linked from each
box/detection card, and no second verification widget appears on the effect
card. A follow-up corrected the incomplete first UI pass: all seven lanes now
use the same detector-side inclusion control and compact effect cards, arranged
as aligned detector → review → effect rows. The two legacy hair/fabric lanes
default excluded; smoke and lighting lanes default included. Existing manual
box coordinates are retained.

Follow-up usability work removes manifest editing from the normal path. After
Discover, **Push this discovery into flow** directly approves and atomically
saves the visible image-bound candidates without queuing a full-song render;
the next normal run loads them automatically, and setup returns itself to
`idle`. The large JSON editor is hidden
unless advanced editing is requested. Smoke is now its own first-class target
with an independently normalized thin-plume/broad-fog semantic ensemble, a
finer spatial grid, up to eight disconnected regions, and a dedicated slow
billow preset. A real `input/Photo.png` check now produces a smoke target where
the previous combined atmosphere phrase produced none; final mask precision
still requires visual review of the annotated discovery preview.

Runtime feedback exposed that the scaffold's inherited Bella Ciao manual lanes
were still active under `manual_wins`; on unrelated artwork, `red_hair` and
`red_fabric` could reinterpret heads or clothes and apply sway. The scaffold and
merge-node default are now `auto_only`, with manual modes retained as explicit
fallbacks. Auto-discovered light/illumination/reflection targets are hard-locked
to spatially still luminance/glow/shimmer behavior. Auto people, faces, hair,
and fabric are spatially still because the procedural compositor cannot create
credible articulated human motion. Discovery also subtracts a dilated semantic
person mask from environmental effects. Smoke billow response is stronger, but
deformation amplitude is now capped independently from mask expansion so large
atmospheric support cannot drag neighboring heads or fixtures.

## 2026-10-13 Infra Choir Enhanced Production Visualizer

The new non-destructive production entry point is
`user/default/workflows/music_visualizer_infra_choir_enhanced.json`. It keeps
the original seven reviewed semantic-mask lanes, target stack, title treatment,
streamed full-song renderer, and output contract. The existing
`music_visualizer_infra_choir_production.json` remains the baseline and was not
replaced.

The project-owned nodes now provide one cached, frame-aligned STFT analysis
with RMS, low/mid/high energy, kick/snare/hi-hat transient accents, onset,
beat confidence/phase, slow and phrase envelopes, and lightweight
vocal/instrument spectral proxies. The enhanced target node adds independent
driver mixing and ADSR-style shaping. The enhanced renderer adds genuine
32-512-band log/linear spectra (256 bands by default), four fine-spectrum
styles, peak hold, masked edge glow, reflection shimmer, atmospheric treatment,
and optional section gain overrides. Every enhancement is switchable, and the
master-off output is byte-identical after decoding to the baseline smoke test.

Fill-Nodes was audited at source level. Its Apache-2.0 drum-envelope and edge
effect concepts were adapted inside the project node because its native
`FL_AUDIO_ENVELOPE` and full-image-batch nodes do not fit this renderer's
target JSON or bounded streaming contract. No third-party node code was edited,
and no cloud service, diffusion model, or source-separation model was added.

A complete Bella Ciao A/B rendered at 1920x1080, 16 fps, 4,598 frames, and
287.375 seconds. Baseline/enhanced times were 843.93/860.76 seconds; enhanced
peak process-plus-FFmpeg RSS was about 2.41 GiB and total observed GPU memory
was 3,310 MiB. Fresh enhanced analysis took 9.52 seconds; a disk-cache hit took
0.14 seconds. Both outputs carry identical decoded audio, and representative
early/middle/late frames plus the EQ region were visually inspected. Details,
paths, limitations, and Fill-Nodes integration decisions are in
`refs/evaluations/2026-10-13-infra-choir-enhanced-visualizer.md` and
`refs/architecture/infraChoirVisualizerEnhanced.md`.

## 2026-10-13 Audio-Reactive Loop LTX 2.3 Q2 Evaluation

A new, non-destructive workflow is saved at
`user/default/workflows/audio_reactive_loop_LTX23_Q2_8GB.json`. It restores
the upstream LTX 2.3 architecture while preserving AudioLoopHelper's
TensorLoopOpen/TensorLoopClose, AudioLoopController, full-song audio latent,
and automatic stop wiring. Its test plan is 704x416, 97 frames, and 24 fps.
The existing `audio_reactive_loop_LTX25.json` remains unchanged.

The workflow uses the Video Studio fast-tier Q2_K GGUF transformer, its Gemma
3 12B FP4 mixed text encoder, separate BF16 text projection, and LTX 2.3 video
and audio VAEs. `ComfyUI-GGUF` was added at commit
`6ea2651f3266613034c67221f84f979c58de87db`, with `gguf==0.19.0` installed in
Desktop's `.venv`. All five model files live under
`D:\comfyDesktop\models\local`; the larger Q3 model was not downloaded.

A real four-second audio-conditioned run completed eight sampler steps and
produced a 704x416, 24 fps, 97-frame video plus a four-second AAC stereo mux.
The best tested configuration completed in 127.53 seconds and peaked at
10,834 MiB (10.58 GiB) total GPU memory. Dynamic VRAM was slower and peaked
higher. The user accepted this 10.58 GiB result as the current RTX 4070 12 GB
baseline. For future experiments, the target remains below 10 GiB, while the
acceptance gate is that active generation remains GPU-resident without model
or layer offloading to CPU. A lower reported VRAM peak achieved through CPU
offloading is not an improvement. Do not describe the Studio "8GB" tier as
validated on an 8 GB card; the upstream documentation itself warns that the
tier was tested on a 16 GB GPU and offloads aggressively on lower VRAM.

The retained configuration uses PyTorch attention, four FFN chunks, bypassed
NAG, explicit pre-decode model cleanup, and 2x2 tiled decode. Audio
conditioning was verified through the LTX 2.3 audio-VAE-to-AV-latent path and
an output audio stream; subjective beat responsiveness was not independently
A/B scored. Detailed evidence is in
`refs/evaluations/2026-10-13-ltx23-q2-audio-loop-benchmark.md`.

## 2026-10-12 Audio-Reactive Loop LTX 2.5 Repair

The user workflow at
`user/default/workflows/ComfyUI-AudioLoopHelper/audio_reactive_loop.json` was
adapted from its unavailable LTX 2.3 selectors to the installed LTX 2.5 model
set under `D:\comfyDesktop\models\local`. The active transformer, combined
Gemma 4 text encoder/projection, video VAE, and audio VAE selectors now match
the installed INT8 ConvRot/BF16 files. The loader changed from the obsolete
two-file `DualCLIPLoader` arrangement to the official LTX 2.5 single-file
`CLIPLoader` arrangement. All nine workflow timing sites now agree at the
official LTX 2.5 rate of 24 fps.

Four unavailable LTX 2.3-only optional selectors (vocal separation, spatial
upscaler, IC-LoRA, and base-model distill LoRA) remain bypassed and were cleared
so they are not presented as required models. No model was downloaded.
`colour-science` 0.4.7 was added to the live `.venv`, satisfying the declared
`ComfyUI-LTXVideo` dependency and restoring that node pack's registration.

Validation parsed the 100-node/138-link workflow, confirmed all four active
model names through the same D-drive model-path configuration used by Desktop,
and completed ComfyUI 0.39.2's import-only startup check with both
`ComfyUI-AudioLoopHelper` and `ComfyUI-LTXVideo` registered. The upstream
AudioLoopHelper audit reports 44 passing topology checks; its two remaining
errors are the expected hard-coded LTX 2.3 assertion that frame rate must be 25,
while its independent coherence check confirms all nine adapted sites are 24.
No render was queued and no ComfyUI service was started, stopped, or restarted.

On 2026-10-13, Desktop's session LevelDB showed that the visible tab was an
unsaved temporary workflow at `workflows/audio_reactive_loop.json`. Reloading
that tab therefore restored its old LTX 2.3 graph from browser session state
instead of rereading the corrected workflow file. An identical corrected copy
is now saved at the collision-free root path
`user/default/workflows/audio_reactive_loop_LTX25.json`. Close the stale
temporary tab and open `audio_reactive_loop_LTX25.json` from the Workflows
panel; do not reopen the AudioLoopHelper bundled template, which remains an
upstream LTX 2.3 artifact.

The 2026-10-13 user reload then exposed a second setup-scanner mismatch:
`VAELoaderKJ` found the D-drive files at runtime but advertised both selectors
as unknown models. Nodes 1537 and 1538 now use the official core `VAELoader`
shape and basename selectors from the LTX 2.5 reference workflows, with their
existing VAE output links preserved. The only remaining setup requirements are
the intentional user-selected image and audio inputs.

## 2026-10-12 Comfy Desktop D-Drive Storage Migration

Comfy Desktop's persistent settings, installation record, shared model-path
file, and instance model-path file now point to `D:\comfyDesktop`. The 44.4
GiB shared and 80.1 GiB local model stores were moved to
`D:\comfyDesktop\models\shared` and `D:\comfyDesktop\models\local`; input,
output, and temp storage were moved alongside them. The former C-drive paths
are compatibility junctions, while Desktop launches with D-drive input,
output, and temp arguments directly. All 669 migrated files matched by path
and byte length, and all 102 model files matched SHA-256 before the C-drive
copies were removed.

A live ComfyUI 0.39.2 smoke test loaded both D-drive model roots, registered
the YuE2 nodes, and discovered the YuE2 checkpoint, SheetSage2 encoder,
instrumental LoRA, Wan S2V, LTX, and ACE-Step assets. Existing unrelated
KJNodes Triton and VRGDG LTX-submodule warnings remain. The smoke-test backend
was stopped and port 8000 was released.

## 2026-10-12 Music Generation Candidate Spike

`pytraveler/YuE2-ComfyUI` is linked from
`custom_nodes/YuE2-ComfyUI` to the maintenance checkout at
`D:\Apps\Tools\YuE2-ComfyUI`. Its 13 nodes and 12 templates load in ComfyUI
0.39.2. Live API runs validated ABC planning, edited-ABC override, a short new
song, SheetSage2 transcription plus cover render, and the instrumental LoRA.
The existing shared INT8 YuE2 checkpoint and SheetSage2 encoder were reused;
only the 266 MiB instrumental adapter was added. Peak sampled GPU use was
7,927 MiB on the RTX 4070. The recommendation is BUILD AROUND for
non-commercial work; YuE2, SheetSage2, and the adapter are CC BY-NC 4.0.

Remiqora is a standalone Electron/Vue/FastAPI orchestrator, not a Comfy custom
node. Its source checkout, dedicated backend venv, frontend build, and desktop
dependencies are installed at `D:\Apps\Tools\remiqora`; nothing was put in
Comfy's node or workflow directories. It reused the existing standalone
ACE-Step venv/checkpoints, launched ACE through its orchestrator, and generated
a ten-second FLAC through the Remiqora proxy. Its YuE2 path remains deliberately
uninstalled because it requires a separate `audio.cpp` CUDA binary and roughly
10 GiB of GGUF weights that cannot reuse Comfy's safetensors. Recommendation:
MINE FOR IDEAS. Full evidence is in
`refs/evaluations/infraChoirMusicGenerationCandidates.md`.

## 2026-10-12 User Acceptance

The user reviewed the corrected production treatment and explicitly reported
that it passes QA. The accepted behavior includes the faded-source opening
card, generated persistent upper-left band/song wordmark, restrained EQ,
outline-confined glints, bounded organic motion beyond the source matte, and
the optional direct logo selector. This closes the subjective Infra Choir
motion-review todo; further Wan clip work remains an optional deferred fidelity
experiment rather than a production blocker.

## 2026-10-12 Generated Wordmark and Organic Motion Support

The production workflow now treats `band_name` and `song_title` as the source
for both the opening title card and the persistent upper-left wordmark.
`apply_wordmark` no longer silently skips when no PNG is connected: it renders
transparent dark-red/pale-outline serif text, while an explicitly connected
image/mask remains the override. The generated opening card now uses a dimmed,
mostly desaturated copy of the source instead of black, controlled by
`title_card_source_visibility` (default 0.20).

Organic lanes gained bounded `organic_motion_expansion_percent` support
(default 2.5%, maximum 8%). Procedural alpha is warped with the pixels so hair,
fabric, smoke, and clouds can move beyond the detected footprint without any
camera or far-field motion. The freshly saved user workflow was migrated in
place without replacing its verified masks, revised smoke search area, or
per-lane motion settings. Direct six-second QA measured 5.691 mean temporal
delta in the expanded ring and 0.016 in the far field; the expanded render took
2.19 seconds versus 1.90 seconds with strict clipping. Complete treatment and
repeat previews both produced H.264/AAC output. A corrected full-song run
rendered 2,299 frames in 53.71 seconds and preserved the 287.36-second source as
a 287.375-second H.264/AAC container. ComfyUI must be restarted once to load the
updated renderer schema. The lower-priority logo gap is also closed with a
`brand_logo_image` input-folder selector; the existing connected image/mask
path remains the higher-priority override.

## 2026-10-09 Infra Choir Production Polish

`user/default/workflows/music_visualizer_infra_choir_production.json` is a new
production copy; the prior hybrid and all reference workflows remain intact.
The existing `InfraChoirVisualizer` now exposes generated or input-selected
title cards, a shared-analysis bottom EQ, and title-outline glints. All three
features are independently optional. The generated title uses editable
`band_name` and `song_title`, automatic wrapping/sizing, configurable timing and
placement, and the reference black/crimson/pale-outline treatment. External
cards override generation without a new connection; unreliable outline
detection skips only sparkle and reports the reason.

Audio analysis remains one deterministic pass and now retains 24 log-frequency
bands for the EQ. Environmental animation, linked lighting, optional generated
motion, streaming FFmpeg assembly, and atomic promotion are unchanged. Georgia
is a documented local Windows font dependency with DejaVu Serif and Pillow
fallbacks; no font or model was added to the repository.

Executed validation covered long Unicode text, external override, bottom-only
EQ restraint, strict sparkle-mask confinement, each feature disabled, generated
title with no asset, repeat rendering, environmental mask confinement, and
full-song audio. The complete six-second preview rendered twice without manual
intervention. A 287.36-second Bella Ciao run produced 2,299 1280x720/8 fps
frames with AAC in 39.75 seconds and a 287.375-second container. Equal-length
six-second baseline/polish renders were 2.82/2.37 seconds, so the new layers
were inside normal codec/startup timing variance rather than adding measurable
overhead in this harness. QA artifacts remain ignored under
`output/infra_choir_validation/`.

## 2026-10-09 Yvann Audio-Reactive Environment Install

`ComfyUI_Yvann-Nodes` 2.1.1 and every external node pack referenced by its
three bundled workflows are installed in the live Comfy Desktop data directory.
Their requirements were installed with this instance's `.venv` Python. The
sample workflows are available under `Yvann Audio Reactive` in the user's
workflow directory, and all 35 referenced non-core node types passed an
isolated registration check.

The workflows' SD 1.5 checkpoint, AnimateDiff models and LoRAs, ControlNets,
VAE, IP-Adapter, CLIP vision encoder, upscaler, and path-compatible aliases are
installed under the repository-local `models/` tree used by Desktop. Hybrid
Demucs is prewarmed in the Torch Hub cache. Open-Unmix UMX-L is installed as
`models/openunmix/umxl.pth`; its four cached source models were reconstructed
from a bit-identical safetensors conversion after the upstream Zenodo endpoint
proved unreliable. No ComfyUI process or queue was restarted or altered.

## 2026-10-09 Infra Choir Hybrid Visualizer

`user/default/workflows/music_visualizer_infra_choir_hybrid.json` is a new,
separate seven-lane workflow built by
`scripts/build_infra_choir_visualizer_workflow.py`. The three local/generic/
semantic reference workflows were not modified; the user's pre-existing edit
to `music_visualizer_target_builder_semantic.json` remains untouched.

`InfraChoirAnimationTarget` adds enable/skip behavior, reusable configuration
JSON, organic/light-source/illumination/reflection roles, shared audio envelope
groups, bounded light controls, and optional short generated IMAGE batches.
`InfraChoirVisualizer` translation-stabilizes generated batches, clips all
changes to verified masks, starts every frame from the source, streams exact
audio duration, treats branding as optional, and atomically promotes a
`.part.mp4` only after FFmpeg succeeds. Clips above 161 frames are rejected with
an actionable short-clip instruction.

Bella Ciao received seven starter lanes: hair, fabric, crop-first smoke,
clouds, sun source, atmospheric illumination, and river reflection. A compact
warm-luminance refinement now isolates explicit sun-disk/source queries instead
of CLIPSeg's earlier broad sunset-cloud response. Every starter mask remains
unverified by default. Direct QA produced a 2-second 1280x720 H.264/AAC file
with exact duration; decoded outside-area temporal delta was 0.020 versus 0.434
inside. Managed Decline generalized without code changes and rendered three
enabled targets from a seven-lane stack while four disabled/missing lanes were
skipped. Optional-detector fallback, strict failure, absent overlays, short
generated-clip stabilization, and interrupted-partial replacement were tested.

Review artifacts are ignored under `output/infra_choir_validation/`. Full
architecture, usage, evidence, resource observations, and limitations are in
`refs/architecture/infraChoirVisualizer.md`. The remaining work is subjective
motion/matte review and, only if useful, embedding a lazy Wan short-clip branch;
the present workflow is complete without Wan and never loads it by default.

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
Every target has four linear `0..2` controls separating beat/off-beat flicker
from beat/off-beat masked motion, and the renderer accepts an arbitrary-length
stack. Prompts can combine drift/billow, flicker, flash/lightning/pulse, scan,
rain, and shimmer treatments. Unverified or empty masks are skipped while at
least one usable verified target remains. A 12-second three-target integration render completed with
192 1280×720 frames, AAC audio, and exact 12.000-second duration.

The installed environment has no text-grounded detector or SAM node. The new
detector therefore remains an explicitly model-free color/texture proposal
generator. Forced-verification QA showed why the gate matters: coarse initial
boxes can admit unrelated structures, especially clouds in a dense scene. The
detector now refines boxes to matching pixels, but users must inspect previews,
constrain `search_area`, or replace the detector output with a painted or future
semantic mask. Optional text-grounded segmentation is the next quality lever;
it is not misrepresented as solved by the current heuristic.

First-target testing exposed an onboarding problem: the starter graph chains
all three example lanes, so the renderer previously rejected the stack while
clouds and monitor remained unverified. `mask_verified` is now an inclusion
toggle. The renderer logs and skips unverified targets, renders any verified
targets without reconnection, and errors only when no usable verified mask
remains.

Follow-up testing found that narrow search areas could yield empty masks because
candidate regions were ranked globally and intersected with `search_area` only
afterward. Detection now ranks candidates inside the search area, draws the
area as a gold preview outline, and memoizes six unchanged results in process.
The renderer skips an empty verified target if another usable verified target
exists, so one weak proposal cannot abort the complete stack. Manual painting
on `Load Image` remains a separate mask unless explicitly connected or combined;
it does not mutate the detector's generated mask.

The attached failing graph confirmed that Mask Editor changes were not in the
render path: each target consumed only `detected_mask`, and the editable source
`MASK` output had no links. `Configure Animation Target` now has an optional
`approved_mask` input. A connected painted mask takes precedence over detector
output on every queue, while unchanged detector inputs remain memoized.

Subsequent QA showed that adding a prewired `EDIT/SAVE APPROVED MASK` `Load
Image` node made correction persist but introduced a mandatory-looking second
upload step. That regression has been removed. Each lane now routes its proposal
through `Verify / Edit Detection Mask`: with no edit it immediately uses the
detector mask; opening that same review node in Mask Editor and pressing Save
persists and selects the painted mask on the next queue. The hidden saved-image
widget is workflow state rather than user-facing input. The optional
`Configure Animation Target.approved_mask` socket remains available for advanced
external add/subtract/replace composition.

Source-switch QA found that the hidden saved-image reference outlived its source:
selecting new artwork caused the review node to redisplay and reuse the previous
picture and mask. Each review node now also consumes the unmodified source image
and persists its fingerprint in hidden workflow state. A changed fingerprint
immediately falls back to the new detector proposal, displays its fresh preview,
and asks the frontend to clear the stale clipspace reference. Legacy workflows
retain a saved correction only when its saved preview RGB matches the current
preview; otherwise they migrate to clean detector state.

Focused validation confirmed that a blank review state returns the detector
proposal, while a saved RGBA clipspace image is decoded with native `LoadImage`
alpha semantics into the expected mask tensor. The regenerated starter graph
contains three review nodes, zero approved-mask loaders, and complete
detector → review → configuration links.
Additional focused tests confirmed that a bound correction remains active for
the same source, a legacy matching correction is retained, a different source
returns the detector mask and emits the clear-state signal, and the existing
Managed Decline correction is rejected against the Bella Ciao source.

Same-source discovery testing exposed a review-state usability gap: after
saving a flag correction, changing `find` to `flower` and broadening the search
area recomputed detection but the review node continued to display and output
its persisted flag correction. `Verify / Edit Detection Mask` now has a visible
**Reset saved mask** button. It clears only that lane's hidden Mask Editor image
and source binding, immediately removes the stale saved preview, and uses the
latest detector proposal on the next queue without changing the source or
rebuilding the node. A full-frame search area is `box 0 0 1 1`;
`box 0 0 0 0` is empty.

Bella Ciao review then confirmed the model-free detector's semantic ceiling:
hair, sun, red fabric, and flags were not understood, while smoke shared the
same neutral-atmosphere heuristic as clouds. The current mainline work now adds
an optional local CLIPSeg provider ahead of the unchanged search-area,
sensitivity, region-ranking, preview, and edit flow. `semantic_or_heuristic` is
the default, `semantic_only` exposes missing/runtime failures, and `heuristic`
retains the model-free path. Loading is local-only from
`models/detection/clipseg-rd64-refined`; workflow execution never downloads
weights. A pinned installer lists or downloads the approximately 577 MiB
snapshot. Missing-model fallback, strict-mode diagnostics, and a mocked
semantic heatmap pass focused tests. The authorized pinned snapshot was then
installed locally and evaluated on the 3840×2160 Bella Ciao artwork at default
semantic sensitivity. Hair now isolates the central woman's hair (0.5% of the
frame), red fabric finds the main scarf and large left flag (4.1%), and flag
finds the large flag but also admits scarf fabric (2.5%). Sun selects the broad
sunset glow rather than the disk (3.6%), while smoke remains empty with only
0.142 peak confidence. A lower-threshold phrase comparison found `smoke haze`
but did not establish a trustworthy smoke-only mask. CLIPSeg is therefore a
useful partial improvement, not accepted semantic detection. Its absolute
floor was retuned so valid part-level responses survive the default sensitivity,
and its original slow image processor is explicit for reproducible inference.

Because billowing smoke is an established visual language requirement, a
second exploration compared twelve smoke phrases on a cropped background
region. Full-frame and cropped bare `smoke` remained blind, but `white smoke`
cleanly selected the pale plumes behind the central figures. The provider now
runs semantic inference on the bounding `search_area` crop and, only when that
crop covers at most 85% of the frame, expands an unqualified smoke query across
white, gray, and black variants. On Bella Ciao, `box .40 .18 .72 .62` with the
ordinary query `smoke` and default `0.65` sensitivity selects 0.6% of the frame,
covering the intended plumes without selecting the large sky clouds. The node
reports both crop use and query expansion. This is a useful smoke path pending
cross-artwork validation; review remains required before marking the target
verified, while editing stays optional.

Workflow-fork semantics were clarified after this pass: “fork off for the next
pass” means preserve the accepted workflow file in place and perform new work
in a separately named workflow copy, not merely on a Git branch. The fixed UI
version remains `music_visualizer_target_builder.json` and retains the original
model-free `VisualizerObjectDetector`. All CLIPSeg work now lives in
`music_visualizer_target_builder_semantic.json` and uses the distinct
`VisualizerSemanticObjectDetector`, preventing a backend restart from silently
changing the fixed workflow's detection behavior.

Repository history is intentionally maintained on the single `main` branch;
workflow experimentation is represented by separately named workflow files,
not long-lived Git branches.

The semantic workflow now contains five complete detector/review/configuration/
stack lanes, the intended practical UI maximum. The user's live first-three
lane settings and saved corrections were retained during expansion; the new
Flowers and Fabric lanes begin unverified. The renderer also adds a cheap
post-process wordmark sparkle: a deterministic alpha-clipped glint passes about
every six seconds, responds lightly to high-band energy, and is controlled by
`wordmark_sparkle_strength` (`0` disables it). It loads no model and consumes
no target lane.

Motion QA then confirmed that the generic renderer's so-called motion modes
only changed exposure or color; target pixels never moved. Target configuration
now exposes four linear `0..2` controls: `on_beat_flicker`,
`off_beat_flicker`, `on_beat_motion`, and `off_beat_motion`. The first pair
drives the existing appearance treatments, while the second pair drives
bounded, edge-replicated subpixel displacement inside the verified mask.
Prompt modes select conservative motion scale and cadence; clouds default to
low motion because a loose cloud mask can otherwise move admitted buildings.
A one-second motion-only integration render (`on/off` flicker both zero,
`off_beat_motion=1`) produced eight distinct 1280×720 H.264 frames, AAC audio,
and exact 1.000-second duration, confirming spatial animation survives encode.

The next QA clarification established that prompt keywords cannot provide the
semantic motion needed for flowing clouds or wind-swept flames. The generic
target now exposes explicit `auto`, `billow`, `sway`, `drift`, and `still`
motion types. `billow` uses evolving multi-scale mesh deformation with a
contracted motion interior; `sway` anchors the mask base and moves its upper
pixels more strongly. Starter clouds and candles use zero beat-motion and
autonomous billow/sway, while their lighting remains beat responsive. A
two-second cloud integration completed with 16 1280×720 frames, AAC audio, and
exact 2.000-second duration. A matching flame-sway integration also completed
with 16 1280×720 frames, AAC audio, and exact 2.000-second duration. Both retain
native per-frame progress reporting. Pitch-to-color remains a separate
next-stage audio feature after motion quality review.

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

## Raise the Neon Black Full-Song Result (2026-10-20)

The production input for this run was explicitly supplied by the user:
`Banner.png` and `Raise the Neon Black.flac`. Do not infer that future runs use
this artwork, the earlier jazz image, or any other prior song configuration;
production inputs change quickly and must be read from the current request or
workflow.

The accepted 1024x576 Wan motion clip was preserved. A proposed 640x360
49-frame cloud/smoke gate failed after 95:45 at KSampler because that height
produced incompatible latent tensor widths (23 versus 22). It also demonstrated
that small Wan passes are not cheap on the current 12 GB/offload path because
fixed conditioning and model movement dominate runtime.

The useful cheap path is deterministic temporal amplification of motion already
present in the accepted clip. `scripts/build_atmospheric_motion_boost_preview.py`
produced `raise_the_neon_black_atmosphere_boost_preview_v3.mp4`, increasing
measured cloud motion about 18% and waterline-fog motion about 72% without
spatial warping; the protected face-region measurement remained unchanged.

`scripts/build_infra_choir_raise_neon_black_full_video.py` builds
`video_raise_the_neon_black_full_visualizer_v2.json`, a separate
full-song workflow, API prompt, and conservative source-derived light mask. It
does not overwrite `music_visualizer_infra_choir_dual_track_scaffold.json`.
The first full output was rejected because the compact target adapter dropped
the cached-motion fields and rendered the overlays over a still image. The
adapter now forwards the cached clip mode, path, duration, overlap, expansion,
strength, and foreground-protection fields. A regression test covers that
contract, and the separate production workflow was rebuilt with the corrected
settings. The accepted output is:

`D:\comfyDesktop\output\infra_choir\final\raise_the_neon_black_full_v2_00001_.mp4`

It is 1920x1080 H.264, 16 fps, 3,332 frames, 208.25 seconds, with 48 kHz stereo
AAC. It includes the opening title card, persistent wordmark, cyan 2048-band
EQ, localized music-synchronized practical-light glow, and the approved
cloud/fog-boosted motion loop. Loop-boundary median change is below the normal
adjacent-frame median. Motion measurements at five points from 8 through 200
seconds confirm the moving layer persists throughout the final file. The
scaffold remained byte-identical to its recovered hash. Detailed evidence is in
`refs/evaluations/2026-10-20-raise-neon-black-full-render.md`.

Later review found a second jump defect: per-frame phase-correlation against
the static cover applied translations up to 7.5 pixels. The separate v2 workflow
now sets `maximum_stabilization_percent=0.0`, which explicitly bypasses that
translation; the reusable scaffold remains byte-identical.

The corrected non-VACE path passed a 20-second/320-frame probe at
`D:\comfyDesktop\output\infra_choir\tests\raise_the_neon_black_no_vertical_shift_probe_00001_.mp4`.
Both the renderer report and an independent adjacent-frame scan found zero
vertical translation. Motion, lighting, title, and 2048-band EQ remain enabled.
The standalone GUI workflow
`user/default/workflows/video_raise_the_neon_black_full_visualizer_v2.json`
now saves under `infra_choir/final/raise_the_neon_black_full_no_vertical_shift`.
The corresponding full render completed successfully at
`D:\comfyDesktop\output\infra_choir\final\raise_the_neon_black_full_no_vertical_shift_00001_.mp4`:
3332 frames at 1920x1080/16 fps, maximum applied shift 0.0 pixels, with cached
motion, lighting, generated title, 2048-band EQ, and AAC audio preserved.
An independent whole-file phase-correlation scan at 160x90 found zero vertical
translation in all 3331 adjacent-frame pairs.

A separate reusable workflow now lives at
`user/default/workflows/music_visualizer_cached_motion_full_song.json`. It has
no selected source image, audio, cached-motion path, reviewed-mask fingerprint,
track title, or track-specific output prefix. Its light detector and mask-review
lane are driven directly by the currently selected source image. Cached motion
starts disabled and must be enabled only after its Advanced Settings points to
a reviewed clip for that same artwork. The song-specific workflow remains an
immutable production record and is not the reusable template.

The user resaved and spaced the live reusable copy as
`user/default/workflows/music_visualizer_cached_motion_full.json`; preserve its
saved image/audio choices and all node positions. That copy now uses the
dedicated `InfraChoirCachedMotionTarget`, whose short card exposes a populated
input/output/temp video dropdown, strength, maximum seconds, and loop overlap.
It also has a standard `PreviewImage` output below the light detector so the
detection branch can be queued independently with a visible result. Loading
the new node class requires a ComfyUI restart; do not collapse or regenerate
the user's layout.

The official Comfy Wan 2.1 VACE 1.3B checkpoint is installed and SHA-256
verified (`640ccc0577e6a5d4bb15cd91b11b699ef914fc55f126c5a1c544e152130784f2`).
Its 832x480 gate uses this image only by explicit authorization. Dynamic offload
makes UMT5 and VACE control encoding costly; start future gates at 17 or 33
frames before an 81-frame pass, and never assume prior production artwork.

The 17-frame VACE gate eventually completed at
`D:\comfyDesktop\output\infra_choir\tests\raise_the_neon_black_vace_13b_atmosphere_short_gate_00001_.mp4`.
It is only 1.061 seconds at 832x480/16 fps and required 45 minutes 31 seconds.
Visual review confirms real cloud, water, flag, and subtle hair motion, but the
clip cannot validate the multi-second screen jump, a loop, tentacles, or final
lighting/title/EQ composition. Treat VACE 1.3B as visually viable but currently
impractical at this offload cost; the interrupted 81-frame run produced no file.

## Current Usage

After installing node changes, restart Comfy Desktop and open
`video_wan2_2_14B_s2v_motion_poster_guided.json`:

1. Select the cover art in `Load Image` and the song in `Load Song`.
2. Edit `Motion Poster Guidance`; keep lip motion off. In `motion_targets`, name
   exact existing regions and physical motion, separated by semicolons.
3. Set `variant_count`; use one normally, and `fixed` seed mode to reproduce a
   run. Two or three variants remain experimental due to transition blur.
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
