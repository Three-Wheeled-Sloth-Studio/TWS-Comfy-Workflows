# TWS Comfy Workflows

Three-Wheeled Sloth Studio's curated ComfyUI workflows, project-owned custom nodes, reproducible setup utilities, and durable agent context.

This Git worktree intentionally lives at the root of a working ComfyUI data directory. Its `.gitignore` is deny-by-default: models, inputs, outputs, temporary files, virtual environments, user-specific configuration, logs, caches, and third-party custom nodes are excluded. A repository validation script rejects forbidden tracked paths as a second safety layer.

## Current workflow

**Status:** usable production baseline. The supported path is one generated
variant, neutral camera, optional post-process branding, and deterministic
1920×1080 delivery. Known limitations and optional improvements are preserved
below as future work rather than prerequisites for ordinary use.

The primary interface is a guided ComfyUI graph that generates short Wan 2.2
S2V variants and assembles a full-song motion poster in one queue operation:

- `user/default/workflows/video_wan2_2_14B_s2v_motion_poster_guided.json` — primary guided workflow.
- `user/default/workflows/video_wan2_2_14B_s2v_motion_poster_visualizer.json` — deferred experimental copy with an audio-reactive brand logo; coherent, but currently too visually dominant for production use.
- `custom_nodes/comfyui_audio_duration_plan/motion_poster_nodes.py` — guidance, variant planning, and full-song assembly nodes.
- `user/default/workflows/video_wan2_2_14B_s2v.json` — source workflow.
- `user/default/workflows/video_wan2_2_14B_s2v_auto_duration.json` — first loop-based duration adaptation.
- `user/default/workflows/video_wan2_2_14B_s2v_auto_duration_windowed.json` — current CPU-state/windowed continuation experiment.
- `user/default/workflows/video_wan2_2_14B_s2v_motion_loop.json` — advanced short-asset workflow.
- `scripts/render_motion_poster.py` and `assets/motion-poster.example.json` — reproducible CLI diagnostic path.

The long-Wan experiment generates 77-frame chunks at 16 fps, defaults to its
832×480 diagnostic resolution, keeps completed latents in system RAM, and
reuses a 19-latent-frame motion window.
The production guided path generates at 1024×576 exact 16:9 and turns one to
three variants into closed, crossfaded
ping-pong cycles, applies restrained camera drift, streams them for the source
audio duration, scales to an exact 1920×1080 delivery frame by default, and
writes an H.264/AAC result without retaining the completed song's frames in
memory.

## Lightweight local music visualizer prototype

`user/default/workflows/music_visualizer_local_composite.json` is a separate
compositing-first workflow for restrained full-song animation without Wan or
another generative video model. The Managed Decline prototype loads the still
and finalized audio, builds six inspectable masks, maps independent audio
features to clouds, candles, warning lights, monitor glow, rain, and
reflections, and streams the complete H.264/AAC render through FFmpeg. It has
no camera motion and copies the static source into every frame before applying
only the masked effects.

The V3 graph includes visible per-frame ComfyUI progress, a model-free
candidate-region suggestion node for adapting other images, stronger cloud,
candle, monitor, rain, and reflection treatments, and optional post-process
track-wordmark plus studio-badge overlays. The supplied Managed Decline
wordmark and TWS badge are selected in the local prototype; replace both image
loaders when adapting another track.

Restart ComfyUI after updating the custom nodes, open the workflow, inspect or
edit each normalized box/ellipse/polygon region, and queue the green renderer.
The checked-in graph uses neutral media placeholders while its region shapes
are tuned and tested for Managed Decline; select the local Managed Decline
image/audio for that prototype or replace both with ordinary inputs for other
artwork. The default is 1920×1080 at 16 fps. No model download is needed.
Architecture, mappings, resource observations, limitations, and next
experiments are documented in
`refs/architecture/localBeatVisualizer.md`.

`user/default/workflows/music_visualizer_target_builder.json` is the generic
fork. Instead of six fixed effect sockets, it chains any number of animation
targets. Each target lane asks what to find, produces a green mask preview for
review, requires `mask_verified`, accepts a plain-language animation
description, and exposes separate `on_beat_flicker`, `off_beat_flicker`,
`on_beat_motion`, and `off_beat_motion` mixes. Connected targets without
`mask_verified` are skipped automatically.
Motion is explicit rather than semantic prompting: choose `billow` for
non-rigid cloud/smoke flow, `sway` for anchored flame movement, `drift` for
coherent travel, or `still` for lighting-only targets.
Each starter lane includes a `Verify / Edit Detection Mask` review node. It
uses detection immediately with no upload step; opening that same node in Mask
Editor and pressing Save automatically makes the painted mask the lane's
persistent correction. Duplicate the complete lane to add a target.
The included detector is a lightweight color/texture proposal system,
not semantic AI segmentation; constrain its normalized `search_area`, adjust
sensitivity, or replace its mask with a painted/segmentation mask when needed.
The advanced `approved_mask` socket remains optional for externally supplied
add, subtract, or replace masks.

## Render a motion poster

The normal path is the guided ComfyUI workflow:

`user/default/workflows/video_wan2_2_14B_s2v_motion_poster_guided.json`

After installing or updating this repository, restart Comfy Desktop once so it
loads the project-owned custom nodes. Then open the guided workflow and:

1. Choose the reference image and song in **Load Image** and **Load Song**.
2. Edit the positive and negative prompts in **Motion Poster Guidance**. The
   supplied preservation and anti-lip-sync defaults are ordinary editable text;
   leave lip motion disabled unless it is deliberately wanted. In
   `motion_targets`, name the exact existing regions that may move and how.
3. Choose one to three variants in **Motion Poster Variant Seeds**. The base
   seed randomizes after each queued run by default; select `fixed` when a run
   must be reproduced exactly.
4. Set optional camera/crossfade controls in **Assemble Full Motion Poster**.
   Camera zoom `1.0` is neutral, camera drift defaults to zero, and delivery
   defaults to `1080p`. The 1024×576 generation canvas is already exact 16:9,
   so normal delivery requires no padding or crop. When changing songs, update
   the adjacent song-title field used for output naming.
5. Select valid transparent PNGs in the connected **Brand Logo** and **Title /
   Wordmark** loaders, then enable either overlay independently in the
   assembler. Disabled overlays are not composited; users without branding can
   select any valid placeholder PNG and leave both toggles off. The logo is
   placed subtly at lower right, while the larger wordmark at upper left can
   automatically generate a dark or light blurred halo beneath itself.
6. Queue the graph once. It generates the variants, closes their seams,
   crossfades them, repeats them to the full audio duration, and saves one MP4.

The final node shows the saved video in ComfyUI. Its filename begins with the
song-title field. No manifest editing or command-line rendering is required for
ordinary use.

ComfyUI reloads widget values from the saved workflow. After selecting media or
editing prompts/lyrics, use **Save As** to create a per-song workflow if those
values should persist without changing the reusable template.

### Guided workflow settings

The green control nodes and titled media loaders are the normal per-song
interface.

| Setting | Default | What it controls |
| --- | --- | --- |
| **Load Image** | `select_reference_image.png` placeholder | Primary artwork conditioned by Wan. Select your own file before queueing. Prefer textless art; add text and branding afterward. |
| **Load Song** | `select_audio.mp3` placeholder | Audio used for Wan conditioning and the exact final video duration. Select your own file before queueing. |
| `positive_prompt` | Background/hair/smoke/light motion plus preservation instructions | Motion that should occur. Keep it physically plausible and explicitly preserve identity, expression, framing, and composition. |
| `negative_prompt` | Anti-lip-sync, anti-warp, anti-camera-motion, and anti-duplicate-face terms | Motion and artifacts to suppress. The defaults now explicitly reject extra, duplicate, new, background, and disembodied faces. |
| `allow_lip_motion` | Off | Removes the leading lip-sync/singing exclusions from the negative prompt. Leave off unless mouth motion is intentional. |
| `motion_targets` | Empty | Semicolon-separated descriptions of exact existing regions and their allowed motion, such as `left smoke plume — billow slowly; red light bars — pulse locally; background tentacles — sway in place`. This is more reliable than asking Wan to discover salient background objects. |
| `lyrics_or_theme_context` | Empty | Adds untimed atmosphere/context to the positive prompt. It does not synchronize animation to individual lyrics. |
| `variant_count` | `1` | Generates one to three seeded variants. Keep `1` for production quality; the tested three-variant crossfade is currently too blurry and suppresses flicker. |
| `base_seed` | `20261001`, randomize after generation | Starting seed. Additional variants and their continuation seeds are derived deterministically from it. Select `fixed` to reproduce a run. |

Branding is optional and happens after generation, so Wan cannot deform it.
Use transparent PNGs for both inputs.

| Setting | Default | What it controls |
| --- | --- | --- |
| **Brand Logo** image | Placeholder, disabled | Small graphic placed at the lower-right corner. |
| `apply_brand_logo` | Off | Enables the lower-right logo. |
| `brand_logo_width_percent` | `12` | Logo width as a percentage of the video width; range 2–40%. |
| `brand_logo_opacity` | `0.72` | Logo opacity; range 0.05–1.0. |
| `brand_logo_margin_px` | `16` | Distance from the right and bottom edges at working resolution; it scales proportionally for 1080p delivery. |
| **Title / Wordmark** image | Placeholder, disabled | More prominent transparent title graphic placed at the upper-left corner. |
| `apply_wordmark` | Off | Enables the upper-left wordmark. |
| `wordmark_width_percent` | `35` | Wordmark width as a percentage of video width; range 5–80%. |
| `wordmark_opacity` | `0.95` | Wordmark opacity; range 0.05–1.0. |
| `wordmark_margin_px` | `20` | Distance from the left and top edges at working resolution; it scales proportionally for 1080p delivery. |
| `wordmark_halo_style` | `dark` | Procedurally derives an `off`, `dark`, or `light` halo from the wordmark PNG's alpha channel and places it beneath the wordmark. |
| `wordmark_halo_opacity` | `0.55` | Halo strength; set to zero or choose `off` to disable it. |
| `wordmark_halo_blur_px` | `18` | Halo softness in final-output pixels. The assembler adds enough transparent padding that the blur is not clipped at the wordmark edge. |

The assembler controls loop closure, final framing, naming, and encoding.

| Setting | Default | What it controls |
| --- | --- | --- |
| `song_name` | `song_title` placeholder | Prepended to the saved filename. Update it when changing songs. |
| `fps` | `16` | Final frame rate. Keep it aligned with the generated Wan clips. |
| `reversal_crossfade_seconds` | `0.5` | Softens each forward/reverse turnaround. Larger values hide the seam more but blur motion for longer. |
| `variant_crossfade_seconds` | `1.0` | Blend time between distinct variants. It has no effect with one variant; multi-variant output is currently experimental. |
| `camera_zoom` | `1.0` | Static scale before cropping. `1.0` is neutral; zero is not a valid scale. |
| `horizontal_drift_px` | `0` | Sinusoidal horizontal camera travel. Nonzero drift requires enough zoom margin and may show quantized stepping. |
| `vertical_drift_px` | `0` | Sinusoidal vertical camera travel. Leave at zero for the validated restrained result. |
| `delivery_resolution` | `1080p` | `source` keeps 1024×576. `1080p` scales the exact-16:9 picture to 1920×1080 without padding or crop. `1080p_fill` remains available for non-16:9 diagnostic inputs. |
| `output_prefix` | `motion_poster/guided_motion_poster` | Output subfolder and suffix. The default produces `output/motion_poster/<song_name>_guided_motion_poster_<counter>.mp4`. |

#### Delivery upscaling

The default `1080p` mode is deterministic FFmpeg post-processing, not an AI
upscaler. The accepted 1024×576 guided generation canvas is exact 16:9, so the
assembler scales the complete picture directly to 1920×1080 without padding,
stretching, or cropping. Branding is composited afterward at delivery
resolution. A real production run completed within the acceptable local time
and memory envelope and produced a visually accepted result; 1024×576 is now
the guided default. The older 832×480 motion-loop workflow remains an advanced
diagnostic rather than the production canvas.

This path uses FFmpeg's Lanczos scaler and requires no additional model file or
custom-node package. No AI upscale model is currently installed or declared as
a workflow dependency. A later optional Real-ESRGAN comparison may add apparent
detail, but it remains outside the production default until frame-to-frame
stability and artwork fidelity pass review.

#### Advanced generation controls

These settings are exposed by the underlying Wan graph but should normally stay
at their validated values:

- Resolution `1024×576`, length `77`, and Wan batch size `1` define each native
  landscape generation chunk.
- **Chunk Length** `77` feeds both the initial and continuation stages.
- **Steps** `4`, **CFG** `1`, sampler `uni_pc`, scheduler `simple`, denoise `1`,
  SD3 shift `8`, and LightX2V LoRA strength `1` are the tested fast-generation
  settings. Linked controls override the numbers displayed inside samplers.
- **Batch sizes** `2`, `LatentCut`, `LatentConcat`, and `ImageFromBatch` implement
  the first-frame/continuation workaround. They are plumbing, not creative
  controls.
- Model-loader fields select the required Wan diffusion model, UMT5 encoder,
  Wan VAE, Wav2Vec2 audio encoder, and LightX2V LoRA. Change them only when
  intentionally substituting compatible assets.
- The collapsed positive/negative conditioning nodes are read-only because they
  receive text from **Motion Poster Guidance**. Edit prompts in the green node.

One variant is the quality default. A completed three-variant test stayed within
the GPU/time budget but produced excessive blended blur and largely erased the
lighting flicker; multi-variant transitions remain future work.

Reference composition also affects fidelity. Testing across additional artwork
found that faces can blur or distort when they occupy a small part of the frame
or sit away from the image center. This occurs in the Wan generation itself,
before delivery upscaling. Review a `source` render when facial fidelity is in
doubt; the Lanczos step preserves the generated result but cannot reconstruct a
face that Wan already damaged. Prefer artwork with important faces larger in
frame until a protected/static-foreground or regional-animation path is added.
Dense compositions with many face-like shapes can also cause Wan to invent a
new face. The stronger defaults and exact `motion_targets` reduce that risk but
cannot guarantee suppression; reject the seed when it occurs. A protected
foreground or regional mask remains the robust future fix.

### Deferred brand-logo visualizer experiment

`video_wan2_2_14B_s2v_motion_poster_visualizer.json` is a separate copy of the
production graph. It keeps the same 1024×576 generation and 1080p assembly but
uses `MotionPosterVisualizerAssemble` for the lower-right logo. The effect is
post-processing only: twelve logarithmic frequency bands per channel form a
24-bar radial spectrum. Left and right audio occupy their respective sides,
low bands begin at the bottom, and high bands end at the top. Every band has a
distinct chromatic note color; smoothed band energy controls both radial length
and brightness. It cannot alter Wan generation, faces, or scene motion.

The implementation passes coherence testing, but its current ring pulls too
much attention toward the lower-right brand position. It is preserved for a
future visual-design pass and is not the production recommendation. Use the
primary guided workflow and static logo today. Future tuning should reduce the
effect's footprint, contrast, or opacity before promotion.

The saved experimental defaults are color strength `0.70`, brightness range
`0.65–1.20`, response time `0.20` seconds, and maximum halo extent `35%` of
logo width. Turning `animate_brand_logo` off uses the ordinary static-logo
path. Silence also falls back to the static logo automatically. Audio analysis
runs on CPU and the animated logo is rendered at final overlay dimensions
before lossless temporary encoding, avoiding meaningful VRAM pressure.

### Deferred future work

The following are intentionally outside the accepted baseline:

- Protect small or off-center faces with static-foreground or regional-motion
  masking.
- Replace the blurry multi-variant crossfade with short transitions, low-motion
  cuts, or section-level alternation.
- Compare optional AI upscaling against the stable Lanczos default.
- Redesign or substantially soften the audio-reactive brand logo so it does not
  visually overweight the lower-right corner.
- Use timed lyrics for section-aware guidance or compositing; untimed text
  remains atmosphere context only.
- Revisit smooth camera motion only if it adds enough value to justify a
  supersampled or subpixel implementation.
- Condition from multiple reference images independently.
- Continue checkpoint and GPU-retention research only for the separate native
  full-song Wan experiment; it is not required by the motion-poster workflow.

### Reproducible CLI path

The manifest and Python scripts remain available for automated testing,
reproduction, and debugging. Edit a copy of
`assets/motion-poster.example.json`, then run:

```powershell
python scripts/render_motion_poster.py assets/motion-poster.example.json --check-manifest
python scripts/build_motion_loop_workflow.py `
  --manifest assets/motion-poster.example.json `
  --output user/default/workflows/motion_poster_active.json
```

The generated `motion_poster_active.json` is the older two-stage diagnostic
workflow. It remains useful when individual loop assets need to be reviewed or
reused before assembly:

```powershell
python scripts/render_motion_poster.py assets/motion-poster.example.json
```

FFmpeg and FFprobe must be available on `PATH`. The renderer uses only the
Python standard library and invokes FFmpeg as a streaming subprocess. Reference
image paths record which artwork the loops derive from. The first image drives the current Wan
workflow; additional references and untimed lyrics are retained as project
context for future conditioning. The renderer refuses non-native aspect ratios
rather than cropping or stretching them, and crossfades any accepted loop
variants into a closed repeating reel.

## Install into another ComfyUI data folder

Prerequisites are a current ComfyUI/ComfyUI Desktop installation with native
Wan S2V nodes, Python 3, Windows PowerShell, FFmpeg and FFprobe on `PATH`, and
enough disk space for the declared model set. The accepted 1024×576 path was
validated on an RTX 4070 with 12 GB VRAM; other hardware is not yet
characterized.

From a clone of this repository, preview the installation first:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-to-comfy.ps1 `
  -ComfyRoot "C:\path\to\ComfyUI" -WhatIf

powershell -ExecutionPolicy Bypass -File scripts/install-wan-s2v-assets.ps1 `
  -ComfyRoot "C:\path\to\ComfyUI" -ListOnly
```

Install the project-owned custom node and all curated workflows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-to-comfy.ps1 -ComfyRoot "C:\path\to\ComfyUI"
```

To also download the Wan S2V model set declared in `assets/wan-s2v-models.json`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-to-comfy.ps1 -ComfyRoot "C:\path\to\ComfyUI" -InstallModels
```

Large model downloads are never committed. Run the model installer with `-ListOnly` to inspect destinations and URLs without downloading.

Restart the ComfyUI backend or Desktop after installation; refreshing only the
browser does not load new Python nodes. Open the guided workflow, then replace
the intentionally nonexistent `select_*` media placeholders with your own
files. The logo and wordmark are optional and disabled by default. Update the
manual `song_name` field whenever the song changes. Because the branding image
loaders are connected, select valid transparent PNGs even when their compositor
toggles remain off.

Detailed setup and workflow-selection notes are in
`refs/operations/localSetup.md`; common failures and fixes are in
`refs/operations/troubleshooting.md`.

## Agent re-entry

This repository uses the [Agent Academy](https://github.com/Three-Wheeled-Sloth-Studio/Agent-Academy) `refs/` harness. Begin routine work with:

```powershell
python refs/tools/generate_agent_context.py --focus "short task description"
```

The generated packet is orientation, not authoritative project state. Durable status, decisions, risks, validation, and handoff context live under `refs/`.

## Validation

```powershell
python scripts/validate_repository.py
python refs/tools/generate_source_catalog.py --check
python refs/tools/generate_okf_indexes.py --check
python refs/tools/validate_refs.py --mode initialized
python refs/tools/generate_agent_context.py --check
```
