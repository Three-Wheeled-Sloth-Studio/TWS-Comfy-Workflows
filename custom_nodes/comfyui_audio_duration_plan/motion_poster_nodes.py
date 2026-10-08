from __future__ import annotations

import colorsys
import copy
import math
import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path


PRESERVATION_PROMPT = (
    "Preserve the subject's identity, face, expression, lips, mouth position, "
    "pose, framing, clothing, and the original composition. Keep every existing "
    "person and face fixed in place and unchanged. Do not add or remove people, "
    "faces, figures, or objects. Restrained, physically plausible motion with "
    "seamless-loop-friendly pacing."
)

ANTI_LIP_SYNC_PROMPT = (
    "lip sync, lips moving, mouth movement, singing, talking, speech, changing "
    "expression, blinking to the beat, face deformation, identity drift, body "
    "movement, dancing, camera shake, rapid zoom, scene change, new objects, "
    "extra face, duplicate face, new face, face appearing in the background, "
    "extra person, duplicate person, disembodied face, warping, morphing, "
    "whole-image pulsing, exaggerated motion"
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


def _overlay_rgba_pixels(image, mask):
    import torch
    import torch.nn.functional as functional

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
    return rgba.mul(255).round().to(torch.uint8).numpy()


def _write_overlay_png(image, mask, destination: Path) -> None:
    from PIL import Image

    pixels = _overlay_rgba_pixels(image, mask)
    Image.fromarray(pixels, mode="RGBA").save(destination)


def _logo_spectrum_features(
    audio: dict,
    fps: int,
    duration: float,
    response_seconds: float,
    band_count: int = 12,
) -> tuple[list[tuple[tuple[float, ...], tuple[float, ...]]] | None, tuple[int, ...]]:
    """Return smoothed left/right log-band energy and each band's pitch class."""
    import torch
    import torch.nn.functional as functional

    waveform = audio.get("waveform")
    sample_rate = int(audio.get("sample_rate", 0))
    if waveform is None or sample_rate <= 0:
        raise ValueError("Audio must contain waveform and a positive sample rate.")
    samples = waveform.detach().to("cpu", dtype=torch.float32)
    if samples.ndim == 3:
        samples = samples[0]
    if samples.ndim == 1:
        samples = samples.unsqueeze(0)
    if samples.shape[0] == 1:
        samples = samples.repeat(2, 1)
    else:
        samples = samples[:2]
    samples = samples.clamp(-1.0, 1.0)
    frame_count = max(1, math.ceil(duration * fps))
    hop = max(1, round(sample_rate / fps))
    n_fft = 4096 if sample_rate >= 16000 else 2048
    required = ((frame_count - 1) * hop) + n_fft
    left_pad = n_fft // 2
    right_pad = max(n_fft // 2, required - int(samples.shape[-1]) - left_pad)
    padded = functional.pad(samples, (left_pad, right_pad))
    spectrum = torch.stft(
        padded,
        n_fft=n_fft,
        hop_length=hop,
        win_length=n_fft,
        window=torch.hann_window(n_fft),
        center=False,
        return_complex=True,
    ).abs()[..., :frame_count]
    if spectrum.shape[-1] < frame_count:
        spectrum = functional.pad(spectrum, (0, frame_count - spectrum.shape[-1]))

    frequencies = torch.fft.rfftfreq(n_fft, d=1.0 / sample_rate)
    highest_frequency = min(3520.0, sample_rate * 0.45)
    edges = torch.logspace(
        math.log10(55.0), math.log10(highest_frequency), band_count + 1
    )
    band_energy = []
    pitch_classes = tuple(
        round(index * 12 / band_count) % 12 for index in range(band_count)
    )
    for index in range(band_count):
        selected = (frequencies >= edges[index]) & (frequencies < edges[index + 1])
        energy = spectrum[:, selected].square().mean(dim=1).sqrt()
        band_energy.append(energy)
    energy = torch.stack(band_energy, dim=1)
    if not energy.numel() or float(energy.max()) <= 1e-7:
        return None, pitch_classes
    compressed = torch.log1p(energy)
    floor = torch.quantile(compressed, 0.10, dim=2, keepdim=True)
    ceiling = torch.quantile(compressed, 0.95, dim=2, keepdim=True)
    normalized = ((compressed - floor) / (ceiling - floor).clamp_min(1e-7)).clamp(0, 1)
    prominence = (ceiling / ceiling.max().clamp_min(1e-7)).pow(0.25)
    normalized *= 0.45 + (0.55 * prominence)

    response_frames = max(1.0, response_seconds * fps)
    release_alpha = 1.0 - math.exp(-1.0 / response_frames)
    attack_alpha = min(1.0, release_alpha * 2.5)
    smoothed = normalized[:, :, 0].clone()
    features: list[tuple[tuple[float, ...], tuple[float, ...]]] = []
    for index in range(frame_count):
        target = normalized[:, :, index]
        alpha = torch.where(target > smoothed, attack_alpha, release_alpha)
        smoothed += alpha * (target - smoothed)
        features.append(
            (
                tuple(float(value) for value in smoothed[0]),
                tuple(float(value) for value in smoothed[1]),
            )
        )
    return features, pitch_classes


def _write_visualizer_logo_video(
    image,
    mask,
    audio: dict,
    fps: int,
    duration: float,
    color_strength: float,
    minimum_brightness: float,
    maximum_brightness: float,
    response_seconds: float,
    target_width: int,
    halo_extent_percent: float,
    destination: Path,
) -> int | None:
    """Encode a stereo radial-spectrum logo animation and return its padding."""
    import numpy
    from PIL import Image, ImageDraw

    features, pitch_classes = _logo_spectrum_features(
        audio, fps, duration, response_seconds
    )
    if features is None:
        return None
    source_image = Image.fromarray(_overlay_rgba_pixels(image, mask), mode="RGBA")
    target_height = max(1, round(source_image.height * target_width / source_image.width))
    logo = source_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
    maximum_bar_length = max(4, round(target_width * halo_extent_percent / 100.0))
    gap = max(2, round(target_width * 0.025))
    stroke = max(2, round(target_width * 0.018))
    minimum_bar_length = max(stroke, round(target_width * 0.025))
    padding = maximum_bar_length + minimum_bar_length + gap + stroke + 2
    width = target_width + (padding * 2)
    height = target_height + (padding * 2)
    center_x = padding + (target_width / 2)
    center_y = padding + (target_height / 2)
    radius_x = (target_width / 2) + gap
    radius_y = (target_height / 2) + gap
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pixel_format", "rgba",
        "-video_size", f"{width}x{height}", "-framerate", str(fps),
        "-i", "-", "-an", "-c:v", "qtrle", "-pix_fmt", "argb",
        str(destination),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdin is not None
    try:
        for channel_energy in features:
            frame_image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(frame_image)
            for channel, energies in enumerate(channel_energy):
                for band, energy in enumerate(energies):
                    progress = band / max(1, len(energies) - 1)
                    angle = (
                        (math.pi / 2) + (progress * math.pi)
                        if channel == 0
                        else (math.pi / 2) - (progress * math.pi)
                    )
                    cosine, sine = math.cos(angle), math.sin(angle)
                    start_x = center_x + (radius_x * cosine)
                    start_y = center_y + (radius_y * sine)
                    length = minimum_bar_length + (maximum_bar_length * energy)
                    end_x = start_x + (length * cosine)
                    end_y = start_y + (length * sine)
                    pitch = pitch_classes[band]
                    saturation = 0.35 + (0.65 * color_strength)
                    red, green, blue = colorsys.hsv_to_rgb(
                        pitch / 12.0, saturation, 1.0
                    )
                    brightness = minimum_brightness + (
                        (maximum_brightness - minimum_brightness) * energy
                    )
                    alpha = round(55 + (200 * energy))
                    color = (
                        round(max(0, min(255, red * 255 * brightness))),
                        round(max(0, min(255, green * 255 * brightness))),
                        round(max(0, min(255, blue * 255 * brightness))),
                        alpha,
                    )
                    draw.line(
                        (start_x, start_y, end_x, end_y),
                        fill=color,
                        width=stroke,
                    )
            frame_image.alpha_composite(logo, (padding, padding))
            process.stdin.write(numpy.asarray(frame_image).tobytes())
        process.stdin.close()
        stderr = process.stderr.read().decode("utf-8", errors="replace")
        return_code = process.wait()
    except BaseException:
        process.kill()
        raise
    if return_code:
        raise RuntimeError(f"FFmpeg logo animation encoding failed: {stderr.strip()}")
    return padding


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
                "motion_targets": (
                    "STRING", {"default": "", "multiline": True}
                ),
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
        motion_targets,
        lyrics_or_theme_context,
    ):
        context = lyrics_or_theme_context.strip()
        positive = positive_prompt.strip()
        targets = motion_targets.strip()
        if targets:
            positive += (
                " Animate only these elements that are already visible in the "
                f"reference image: {targets}. Keep each animated element anchored "
                "to its original position and shape. Do not invent replacements, "
                "new subjects, or new faces."
            )
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
                "wordmark_halo_style": (
                    ["off", "dark", "light"], {"default": "dark"}
                ),
                "wordmark_halo_opacity": (
                    "FLOAT", {"default": 0.55, "min": 0.0, "max": 1.0, "step": 0.01}
                ),
                "wordmark_halo_blur_px": (
                    "FLOAT", {"default": 18.0, "min": 0.5, "max": 100.0, "step": 0.5}
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
                "delivery_resolution": (
                    ["source", "1080p", "1080p_fill"], {"default": "1080p"}
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
        wordmark_halo_style,
        wordmark_halo_opacity,
        wordmark_halo_blur_px,
        song_name,
        fps,
        reversal_crossfade_seconds,
        variant_crossfade_seconds,
        camera_zoom,
        horizontal_drift_px,
        vertical_drift_px,
        delivery_resolution,
        output_prefix,
        animate_brand_logo=False,
        visualizer_color_strength=0.70,
        visualizer_min_brightness=0.65,
        visualizer_max_brightness=1.20,
        visualizer_response_seconds=0.20,
        visualizer_halo_extent_percent=35.0,
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
        logo_animated = bool(_scalar(animate_brand_logo))
        visualizer_color = float(_scalar(visualizer_color_strength))
        visualizer_min = float(_scalar(visualizer_min_brightness))
        visualizer_max = float(_scalar(visualizer_max_brightness))
        visualizer_response = float(_scalar(visualizer_response_seconds))
        visualizer_extent = float(_scalar(visualizer_halo_extent_percent))
        wordmark_enabled = bool(_scalar(apply_wordmark))
        wordmark_width = float(_scalar(wordmark_width_percent))
        wordmark_opacity_value = float(_scalar(wordmark_opacity))
        wordmark_margin = int(_scalar(wordmark_margin_px))
        halo_style = str(_scalar(wordmark_halo_style)).casefold()
        halo_opacity = float(_scalar(wordmark_halo_opacity))
        halo_blur = float(_scalar(wordmark_halo_blur_px))
        fps_value = int(_scalar(fps))
        reversal = float(_scalar(reversal_crossfade_seconds))
        variant_crossfade = float(_scalar(variant_crossfade_seconds))
        zoom = float(_scalar(camera_zoom))
        x_drift = float(_scalar(horizontal_drift_px))
        y_drift = float(_scalar(vertical_drift_px))
        delivery = str(_scalar(delivery_resolution)).casefold()
        song = _safe_filename_component(str(_scalar(song_name)))
        prefix = str(_scalar(output_prefix))
        if not 0.0 <= visualizer_color <= 1.0:
            raise ValueError("Visualizer color strength must be between 0 and 1.")
        if visualizer_min < 0.0 or visualizer_max < visualizer_min:
            raise ValueError("Visualizer brightness range is invalid.")
        if visualizer_response <= 0.0:
            raise ValueError("Visualizer response must be positive.")
        if not 5.0 <= visualizer_extent <= 100.0:
            raise ValueError("Visualizer halo extent must be between 5 and 100 percent.")

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
        if delivery == "source":
            output_width, output_height = width, height
        elif delivery in {"1080p", "1080p_fill"}:
            output_width, output_height = 1920, 1080
        else:
            raise ValueError(f"Unsupported delivery resolution: {delivery_resolution}")
        output_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
            prefix, folder_paths.get_output_directory(), output_width, output_height
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
                f"trim=duration={audio_duration:.9f},setpts=PTS-STARTPTS,format=rgba"
            )]
            if delivery == "source":
                parts[0] += "[base]"
            elif delivery == "1080p_fill":
                parts[0] += (
                    f",scale={output_width}:{output_height}:"
                    "force_original_aspect_ratio=increase:flags=lanczos,"
                    f"crop={output_width}:{output_height},format=rgba[base]"
                )
            else:
                parts[0] += ",split=2[delivery_background_source][delivery_foreground]"
                parts.extend([
                    (
                        "[delivery_background_source]"
                        f"scale={output_width}:{output_height}:"
                        "force_original_aspect_ratio=increase:flags=lanczos,"
                        f"crop={output_width}:{output_height},"
                        "boxblur=luma_radius=20:luma_power=1:"
                        "chroma_radius=10:chroma_power=1,format=rgba"
                        "[delivery_background]"
                    ),
                    (
                        "[delivery_foreground]"
                        f"scale={output_width}:{output_height}:"
                        "force_original_aspect_ratio=decrease:flags=lanczos,"
                        "format=rgba[delivery_picture]"
                    ),
                    (
                        "[delivery_background][delivery_picture]"
                        "overlay=x=(W-w)/2:y=(H-h)/2:shortest=1:format=auto[base]"
                    ),
                ])
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-stream_loop", "-1", "-i", str(reel_path), "-i", str(audio_path),
            ]
            current = "base"
            overlay_index = 2
            if logo_enabled:
                logo_path = work / "brand-logo.png"
                animated_logo_path = work / "brand-logo-visualizer.mov"
                target_width = max(2, round(output_width * logo_width / 100))
                target_margin = round(logo_margin * output_width / width)
                visualizer_padding = None
                if logo_animated:
                    visualizer_padding = _write_visualizer_logo_video(
                        _scalar(brand_logo),
                        _scalar(brand_logo_mask),
                        audio_value,
                        fps_value,
                        audio_duration,
                        visualizer_color,
                        visualizer_min,
                        visualizer_max,
                        visualizer_response,
                        target_width,
                        visualizer_extent,
                        animated_logo_path,
                    )
                if visualizer_padding is not None:
                    command.extend(["-i", str(animated_logo_path)])
                else:
                    _write_overlay_png(
                        _scalar(brand_logo), _scalar(brand_logo_mask), logo_path
                    )
                    command.extend(["-loop", "1", "-i", str(logo_path)])
                if visualizer_padding is not None:
                    parts.append(
                        f"[{overlay_index}:v]format=rgba,"
                        f"colorchannelmixer=aa={logo_opacity:.6f}[logo]"
                    )
                else:
                    parts.append(
                        f"[{overlay_index}:v]format=rgba,scale={target_width}:-1,"
                        f"colorchannelmixer=aa={logo_opacity:.6f}[logo]"
                    )
                parts.append(
                    f"[{current}][logo]overlay=x=W-w-{target_margin}:"
                    f"y=H-h-{target_margin}:shortest=1:format=auto[with_logo]"
                )
                current = "with_logo"
                overlay_index += 1
            if wordmark_enabled:
                wordmark_path = work / "wordmark.png"
                _write_overlay_png(
                    _scalar(wordmark), _scalar(wordmark_mask), wordmark_path
                )
                command.extend(["-loop", "1", "-i", str(wordmark_path)])
                target_width = max(2, round(output_width * wordmark_width / 100))
                target_margin = round(wordmark_margin * output_width / width)
                if halo_style not in {"off", "dark", "light"}:
                    raise ValueError(f"Unsupported wordmark halo style: {halo_style}")
                if halo_style == "off" or halo_opacity <= 0:
                    parts.append(
                        f"[{overlay_index}:v]format=rgba,scale={target_width}:-1,"
                        f"colorchannelmixer=aa={wordmark_opacity_value:.6f}[wordmark]"
                    )
                else:
                    halo_pad = max(2, math.ceil(halo_blur * 3))
                    halo_rgb = 0 if halo_style == "dark" else 255
                    parts.extend([
                        (
                            f"[{overlay_index}:v]format=rgba,scale={target_width}:-1,"
                            "split=2[wordmark_source][wordmark_halo_source]"
                        ),
                        (
                            "[wordmark_source]"
                            f"colorchannelmixer=aa={wordmark_opacity_value:.6f}"
                            "[wordmark]"
                        ),
                        (
                            "[wordmark_halo_source]"
                            f"pad=iw+{halo_pad * 2}:ih+{halo_pad * 2}:"
                            f"x={halo_pad}:y={halo_pad}:color=0x00000000,"
                            f"lutrgb=r={halo_rgb}:g={halo_rgb}:b={halo_rgb},"
                            f"colorchannelmixer=aa={halo_opacity:.6f},"
                            f"gblur=sigma={halo_blur:.6f}:steps=2[wordmark_halo]"
                        ),
                        (
                            f"[{current}][wordmark_halo]"
                            f"overlay=x={target_margin - halo_pad}:"
                            f"y={target_margin - halo_pad}:shortest=1:"
                            "format=auto[with_wordmark_halo]"
                        ),
                    ])
                    current = "with_wordmark_halo"
                parts.append(
                    f"[{current}][wordmark]overlay=x={target_margin}:"
                    f"y={target_margin}:shortest=1:format=auto[with_wordmark]"
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


class MotionPosterVisualizerAssemble(MotionPosterAssemble):
    """Experimental assembler with an audio-reactive lower-right brand logo."""

    @classmethod
    def INPUT_TYPES(cls):
        input_types = copy.deepcopy(super().INPUT_TYPES())
        input_types["required"].update(
            {
                "animate_brand_logo": ("BOOLEAN", {"default": True}),
                "visualizer_color_strength": (
                    "FLOAT", {"default": 0.70, "min": 0.0, "max": 1.0, "step": 0.05}
                ),
                "visualizer_min_brightness": (
                    "FLOAT", {"default": 0.65, "min": 0.0, "max": 2.0, "step": 0.05}
                ),
                "visualizer_max_brightness": (
                    "FLOAT", {"default": 1.20, "min": 0.0, "max": 2.0, "step": 0.05}
                ),
                "visualizer_response_seconds": (
                    "FLOAT", {"default": 0.20, "min": 0.05, "max": 2.0, "step": 0.05}
                ),
                "visualizer_halo_extent_percent": (
                    "FLOAT", {"default": 35.0, "min": 5.0, "max": 100.0, "step": 1.0}
                ),
            }
        )
        return input_types


NODE_CLASS_MAPPINGS = {
    "MotionPosterGuidance": MotionPosterGuidance,
    "MotionPosterSeedPlan": MotionPosterSeedPlan,
    "MotionPosterAssemble": MotionPosterAssemble,
    "MotionPosterVisualizerAssemble": MotionPosterVisualizerAssemble,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MotionPosterGuidance": "Motion Poster Guidance",
    "MotionPosterSeedPlan": "Motion Poster Variant Seeds",
    "MotionPosterAssemble": "Assemble Full Motion Poster",
    "MotionPosterVisualizerAssemble": "Assemble Motion Poster + Logo Visualizer",
}
