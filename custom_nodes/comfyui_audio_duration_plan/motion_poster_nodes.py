from __future__ import annotations

import math
import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path


PRESERVATION_PROMPT = (
    "Preserve the subject's identity, face, expression, lips, mouth position, "
    "pose, framing, clothing, and the original composition. Restrained, "
    "physically plausible motion with seamless-loop-friendly pacing."
)

ANTI_LIP_SYNC_PROMPT = (
    "lip sync, lips moving, mouth movement, singing, talking, speech, changing "
    "expression, blinking to the beat, face deformation, identity drift, body "
    "movement, dancing, camera shake, rapid zoom, scene change, new objects, "
    "warping, morphing, whole-image pulsing, exaggerated motion"
)

DEFAULT_POSITIVE_PROMPT = (
    "Background motion only. Hair moves gently as if blown by a light wind. "
    "Smoke billows slowly in the background. Street and neon lights flicker "
    f"intermittently. {PRESERVATION_PROMPT}"
)


def _run(command: list[str]) -> None:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"FFmpeg failed: {detail}")


def _scalar(value):
    if isinstance(value, list):
        if not value:
            raise ValueError("Expected a non-empty input list.")
        return value[0]
    return value


def _safe_filename_component(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    return cleaned or "untitled_song"


def _write_overlay_png(image, mask, destination: Path) -> None:
    import torch
    import torch.nn.functional as functional
    from PIL import Image

    rgb = image.detach().to("cpu")
    alpha_mask = mask.detach().to("cpu")
    if rgb.ndim == 4:
        rgb = rgb[0]
    if alpha_mask.ndim == 3:
        alpha_mask = alpha_mask[0]
    if rgb.ndim != 3 or rgb.shape[-1] < 3:
        raise ValueError("Branding overlays must be IMAGE inputs.")
    height, width = int(rgb.shape[0]), int(rgb.shape[1])
    if alpha_mask.ndim != 2:
        raise ValueError("Branding overlay masks must be MASK inputs.")
    if tuple(alpha_mask.shape) != (height, width):
        alpha_mask = functional.interpolate(
            alpha_mask[None, None], size=(height, width), mode="bilinear",
            align_corners=False,
        )[0, 0]
    # ComfyUI's LoadImage mask is inverse alpha: 0 is opaque, 1 is transparent.
    alpha = 1.0 - alpha_mask.clamp(0, 1)
    rgba = torch.cat((rgb[..., :3].clamp(0, 1), alpha[..., None]), dim=-1)
    pixels = rgba.mul(255).round().to(torch.uint8).numpy()
    Image.fromarray(pixels, mode="RGBA").save(destination)


def _write_audio_wav(audio: dict, destination: Path) -> float:
    waveform = audio.get("waveform")
    sample_rate = int(audio.get("sample_rate", 0))
    if waveform is None or sample_rate <= 0:
        raise ValueError("Audio must contain waveform and a positive sample rate.")
    samples = waveform.detach().to("cpu")
    if samples.ndim == 3:
        samples = samples[0]
    if samples.ndim == 1:
        samples = samples.unsqueeze(0)
    samples = samples.clamp(-1.0, 1.0).mul(32767).to(dtype=__import__("torch").int16)
    interleaved = samples.transpose(0, 1).contiguous().numpy().astype("<i2")
    with wave.open(str(destination), "wb") as handle:
        handle.setnchannels(int(samples.shape[0]))
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(interleaved.tobytes())
    return int(samples.shape[-1]) / sample_rate


def _write_frames_video(images, fps: int, destination: Path) -> tuple[int, int, float]:
    import torch

    frames = images.detach().to("cpu")
    if frames.ndim != 4 or frames.shape[-1] < 3:
        raise ValueError("Each loop variant must be an IMAGE frame batch.")
    height, width = int(frames.shape[1]), int(frames.shape[2])
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pixel_format", "rgb24",
        "-video_size", f"{width}x{height}", "-framerate", str(fps),
        "-i", "-", "-an", "-c:v", "libx264", "-preset", "fast",
        "-crf", "18", "-pix_fmt", "yuv420p", str(destination),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdin is not None
    try:
        for frame in frames:
            rgb = frame[..., :3].clamp(0, 1).mul(255).to(torch.uint8).numpy()
            process.stdin.write(rgb.tobytes())
        process.stdin.close()
        stderr = process.stderr.read().decode("utf-8", errors="replace")
        return_code = process.wait()
    except BaseException:
        process.kill()
        raise
    if return_code:
        raise RuntimeError(f"FFmpeg frame encoding failed: {stderr.strip()}")
    return width, height, int(frames.shape[0]) / fps


def _build_closed_cycle(
    source: Path,
    duration: float,
    fps: int,
    crossfade: float,
    destination: Path,
) -> float:
    if crossfade <= 0 or crossfade >= duration / 2:
        raise ValueError("Reversal crossfade must be shorter than half the loop.")
    midpoint = duration / 2
    cycle_duration = (2 * duration) - (2 * crossfade) - (1 / fps)
    graph = (
        f"[0:v]fps={fps},split=3[forward][backward][closing];"
        f"[forward]trim=start={midpoint:.9f},setpts=PTS-STARTPTS[a];"
        f"[backward]reverse,setpts=PTS-STARTPTS[b];"
        f"[closing]trim=end={midpoint:.9f},setpts=PTS-STARTPTS[c];"
        f"[a][b]xfade=transition=fade:duration={crossfade:.9f}:"
        f"offset={midpoint - crossfade:.9f}[ab];"
        f"[ab][c]xfade=transition=fade:duration={crossfade:.9f}:"
        f"offset={midpoint + duration - (2 * crossfade):.9f},"
        f"trim=end={cycle_duration:.9f},setpts=PTS-STARTPTS,format=yuv420p[v]"
    )
    _run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
        "-filter_complex", graph, "-map", "[v]", "-an", "-c:v", "libx264",
        "-preset", "fast", "-crf", "18", str(destination),
    ])
    return cycle_duration


def _build_reel(
    cycles: list[tuple[Path, float]],
    fps: int,
    crossfade: float,
    destination: Path,
) -> tuple[Path, float]:
    if len(cycles) == 1:
        return cycles[0]
    anchor_half = cycles[0][1] / 2
    if crossfade <= 0 or crossfade >= min(
        anchor_half, *(duration for _, duration in cycles[1:])
    ):
        raise ValueError("Variant crossfade is too long for the generated loops.")
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for path, _ in cycles:
        command.extend(["-i", str(path)])
    parts = [
        "[0:v]split=2[anchor_after][anchor_before]",
        f"[anchor_after]trim=start={anchor_half:.9f},setpts=PTS-STARTPTS[s0]",
    ]
    durations = [anchor_half]
    for index, (_, duration) in enumerate(cycles[1:], start=1):
        parts.append(f"[{index}:v]setpts=PTS-STARTPTS[s{index}]")
        durations.append(duration)
    last_index = len(cycles)
    parts.append(
        f"[anchor_before]trim=end={anchor_half:.9f},"
        f"setpts=PTS-STARTPTS[s{last_index}]"
    )
    durations.append(anchor_half)
    cumulative = durations[0]
    previous = "s0"
    for index in range(1, len(durations)):
        label = f"mix{index}"
        parts.append(
            f"[{previous}][s{index}]xfade=transition=fade:duration={crossfade:.9f}:"
            f"offset={cumulative - crossfade:.9f}[{label}]"
        )
        cumulative += durations[index] - crossfade
        previous = label
    reel_duration = cumulative - (1 / fps)
    parts.append(
        f"[{previous}]trim=end={reel_duration:.9f},"
        "setpts=PTS-STARTPTS,format=yuv420p[v]"
    )
    command.extend([
        "-filter_complex", ";".join(parts), "-map", "[v]", "-an",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", str(destination),
    ])
    _run(command)
    return destination, reel_duration


class MotionPosterGuidance:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "positive_prompt": (
                    "STRING",
                    {
                        "default": DEFAULT_POSITIVE_PROMPT,
                        "multiline": True,
                    },
                ),
                "negative_prompt": (
                    "STRING",
                    {
                        "default": ANTI_LIP_SYNC_PROMPT,
                        "multiline": True,
                    },
                ),
                "allow_lip_motion": ("BOOLEAN", {"default": False}),
                "lyrics_or_theme_context": (
                    "STRING", {"default": "", "multiline": True}
                ),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("positive_prompt", "negative_prompt")
    FUNCTION = "build"
    CATEGORY = "audio/video planning"

    def build(
        self,
        positive_prompt,
        negative_prompt,
        allow_lip_motion,
        lyrics_or_theme_context,
    ):
        context = lyrics_or_theme_context.strip()
        positive = positive_prompt.strip()
        if context:
            positive += (
                " Song atmosphere/context only; do not invent literal new scene "
                f"content: {context}"
            )
        negative = negative_prompt.strip()
        if allow_lip_motion:
            negative = negative.replace(
                "lip sync, lips moving, mouth movement, singing, talking, speech, ",
                "",
            )
        return positive, negative


class MotionPosterSeedPlan:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "variant_count": ("INT", {"default": 3, "min": 1, "max": 3}),
                "base_seed": (
                    "INT",
                    {
                        "default": 20261001,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": True,
                    },
                ),
            }
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("initial_seeds", "extension_seeds")
    OUTPUT_IS_LIST = (True, True)
    FUNCTION = "plan"
    CATEGORY = "audio/video planning"

    def plan(self, variant_count, base_seed):
        initial = [int(base_seed) + (index * 9973) for index in range(variant_count)]
        extension = [seed + 1000003 for seed in initial]
        return initial, extension


class MotionPosterAssemble:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "loop_images": ("IMAGE",),
                "audio": ("AUDIO",),
                "brand_logo": ("IMAGE",),
                "brand_logo_mask": ("MASK",),
                "wordmark": ("IMAGE",),
                "wordmark_mask": ("MASK",),
                "apply_brand_logo": ("BOOLEAN", {"default": False}),
                "brand_logo_width_percent": (
                    "FLOAT", {"default": 12.0, "min": 2.0, "max": 40.0, "step": 1.0}
                ),
                "brand_logo_opacity": (
                    "FLOAT", {"default": 0.72, "min": 0.05, "max": 1.0, "step": 0.01}
                ),
                "brand_logo_margin_px": (
                    "INT", {"default": 16, "min": 0, "max": 200}
                ),
                "apply_wordmark": ("BOOLEAN", {"default": False}),
                "wordmark_width_percent": (
                    "FLOAT", {"default": 35.0, "min": 5.0, "max": 80.0, "step": 1.0}
                ),
                "wordmark_opacity": (
                    "FLOAT", {"default": 0.95, "min": 0.05, "max": 1.0, "step": 0.01}
                ),
                "wordmark_margin_px": (
                    "INT", {"default": 20, "min": 0, "max": 200}
                ),
                "song_name": ("STRING", {"default": "song"}),
                "fps": ("INT", {"default": 16, "min": 1, "max": 60}),
                "reversal_crossfade_seconds": (
                    "FLOAT", {"default": 0.5, "min": 0.05, "max": 3.0, "step": 0.05}
                ),
                "variant_crossfade_seconds": (
                    "FLOAT", {"default": 1.0, "min": 0.05, "max": 5.0, "step": 0.05}
                ),
                "camera_zoom": (
                    "FLOAT", {"default": 1.0, "min": 1.0, "max": 1.2, "step": 0.01}
                ),
                "horizontal_drift_px": (
                    "FLOAT", {"default": 0.0, "min": 0.0, "max": 100.0}
                ),
                "vertical_drift_px": (
                    "FLOAT", {"default": 0.0, "min": 0.0, "max": 100.0}
                ),
                "output_prefix": (
                    "STRING", {"default": "motion_poster/guided_motion_poster"}
                ),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("output_path",)
    INPUT_IS_LIST = True
    OUTPUT_NODE = True
    FUNCTION = "assemble"
    CATEGORY = "audio/video planning"

    def assemble(
        self,
        loop_images,
        audio,
        brand_logo,
        brand_logo_mask,
        wordmark,
        wordmark_mask,
        apply_brand_logo,
        brand_logo_width_percent,
        brand_logo_opacity,
        brand_logo_margin_px,
        apply_wordmark,
        wordmark_width_percent,
        wordmark_opacity,
        wordmark_margin_px,
        song_name,
        fps,
        reversal_crossfade_seconds,
        variant_crossfade_seconds,
        camera_zoom,
        horizontal_drift_px,
        vertical_drift_px,
        output_prefix,
    ):
        import folder_paths

        if shutil.which("ffmpeg") is None:
            raise RuntimeError("FFmpeg must be available on PATH.")
        variants = loop_images if isinstance(loop_images, list) else [loop_images]
        audio_value = _scalar(audio)
        logo_enabled = bool(_scalar(apply_brand_logo))
        logo_width = float(_scalar(brand_logo_width_percent))
        logo_opacity = float(_scalar(brand_logo_opacity))
        logo_margin = int(_scalar(brand_logo_margin_px))
        wordmark_enabled = bool(_scalar(apply_wordmark))
        wordmark_width = float(_scalar(wordmark_width_percent))
        wordmark_opacity_value = float(_scalar(wordmark_opacity))
        wordmark_margin = int(_scalar(wordmark_margin_px))
        fps_value = int(_scalar(fps))
        reversal = float(_scalar(reversal_crossfade_seconds))
        variant_crossfade = float(_scalar(variant_crossfade_seconds))
        zoom = float(_scalar(camera_zoom))
        x_drift = float(_scalar(horizontal_drift_px))
        y_drift = float(_scalar(vertical_drift_px))
        song = _safe_filename_component(str(_scalar(song_name)))
        prefix = str(_scalar(output_prefix))

        prefix_path = Path(prefix.replace("\\", "/"))
        if prefix_path.name.casefold().startswith(song.casefold()):
            named_prefix = prefix_path.name
        else:
            named_prefix = f"{song}_{prefix_path.name}" if prefix_path.name else song
        if str(prefix_path.parent) not in {"", "."}:
            prefix = (prefix_path.parent / named_prefix).as_posix()
        else:
            prefix = named_prefix

        first = variants[0]
        height, width = int(first.shape[1]), int(first.shape[2])
        output_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
            prefix, folder_paths.get_output_directory(), width, height
        )
        output_file = f"{filename}_{counter:05}_.mp4"
        output_path = Path(output_folder) / output_file

        with tempfile.TemporaryDirectory(prefix="guided-motion-poster-") as temp:
            work = Path(temp)
            audio_path = work / "song.wav"
            audio_duration = _write_audio_wav(audio_value, audio_path)
            cycles: list[tuple[Path, float]] = []
            for index, images in enumerate(variants):
                clip_path = work / f"variant-{index:02d}.mp4"
                clip_width, clip_height, duration = _write_frames_video(
                    images, fps_value, clip_path
                )
                if (clip_width, clip_height) != (width, height):
                    raise ValueError("All loop variants must have identical dimensions.")
                cycle_path = work / f"cycle-{index:02d}.mp4"
                cycle_duration = _build_closed_cycle(
                    clip_path, duration, fps_value, reversal, cycle_path
                )
                cycles.append((cycle_path, cycle_duration))
            reel_path, _ = _build_reel(
                cycles, fps_value, variant_crossfade, work / "reel.mp4"
            )

            scaled_width = math.ceil(width * zoom / 2) * 2
            scaled_height = math.ceil(height * zoom / 2) * 2
            if x_drift > (scaled_width - width) / 2:
                raise ValueError("Horizontal drift exceeds the selected camera zoom margin.")
            if y_drift > (scaled_height - height) / 2:
                raise ValueError("Vertical drift exceeds the selected camera zoom margin.")
            x = f"(iw-ow)/2+{x_drift:.6f}*sin(2*PI*t/19.0)"
            y = f"(ih-oh)/2+{y_drift:.6f}*sin(2*PI*t/29.0+PI/3)"
            parts = [(
                f"[0:v]scale={scaled_width}:{scaled_height}:flags=lanczos,"
                f"crop={width}:{height}:x='{x}':y='{y}',fps={fps_value},"
                f"trim=duration={audio_duration:.9f},setpts=PTS-STARTPTS,"
                "format=rgba[base]"
            )]
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-stream_loop", "-1", "-i", str(reel_path), "-i", str(audio_path),
            ]
            current = "base"
            overlay_index = 2
            if logo_enabled:
                logo_path = work / "brand-logo.png"
                _write_overlay_png(
                    _scalar(brand_logo), _scalar(brand_logo_mask), logo_path
                )
                command.extend(["-loop", "1", "-i", str(logo_path)])
                target_width = max(2, round(width * logo_width / 100))
                parts.append(
                    f"[{overlay_index}:v]format=rgba,scale={target_width}:-1,"
                    f"colorchannelmixer=aa={logo_opacity:.6f}[logo]"
                )
                parts.append(
                    f"[{current}][logo]overlay=x=W-w-{logo_margin}:"
                    f"y=H-h-{logo_margin}:shortest=1:format=auto[with_logo]"
                )
                current = "with_logo"
                overlay_index += 1
            if wordmark_enabled:
                wordmark_path = work / "wordmark.png"
                _write_overlay_png(
                    _scalar(wordmark), _scalar(wordmark_mask), wordmark_path
                )
                command.extend(["-loop", "1", "-i", str(wordmark_path)])
                target_width = max(2, round(width * wordmark_width / 100))
                parts.append(
                    f"[{overlay_index}:v]format=rgba,scale={target_width}:-1,"
                    f"colorchannelmixer=aa={wordmark_opacity_value:.6f}[wordmark]"
                )
                parts.append(
                    f"[{current}][wordmark]overlay=x={wordmark_margin}:"
                    f"y={wordmark_margin}:shortest=1:format=auto[with_wordmark]"
                )
                current = "with_wordmark"
            parts.append(f"[{current}]format=yuv420p[v]")
            command.extend([
                "-filter_complex", ";".join(parts), "-map", "[v]", "-map", "1:a:0",
                "-t", f"{audio_duration:.9f}", "-c:v", "libx264", "-preset",
                "medium", "-crf", "20", "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", str(output_path),
            ])
            _run(command)

        preview = {
            "filename": output_file,
            "subfolder": subfolder,
            "type": "output",
        }
        return {
            "ui": {"images": [preview], "animated": (True,)},
            "result": (str(output_path),),
        }


NODE_CLASS_MAPPINGS = {
    "MotionPosterGuidance": MotionPosterGuidance,
    "MotionPosterSeedPlan": MotionPosterSeedPlan,
    "MotionPosterAssemble": MotionPosterAssemble,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MotionPosterGuidance": "Motion Poster Guidance",
    "MotionPosterSeedPlan": "Motion Poster Variant Seeds",
    "MotionPosterAssemble": "Assemble Full Motion Poster",
}
