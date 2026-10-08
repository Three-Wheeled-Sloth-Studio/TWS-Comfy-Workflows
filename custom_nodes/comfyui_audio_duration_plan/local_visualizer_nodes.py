from __future__ import annotations

import math
import re
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path


def _safe_name(value: str) -> str:
    cleaned = re.sub(r'[^A-Za-z0-9._-]+', "_", value).strip("._")
    return cleaned or "local_visualizer"


def _image_pixels(image):
    import numpy as np

    value = image.detach().to("cpu")
    if value.ndim == 4:
        value = value[0]
    if value.ndim != 3 or value.shape[-1] < 3:
        raise ValueError("Expected a ComfyUI IMAGE tensor.")
    return np.clip(value[..., :3].numpy() * 255.0, 0, 255).round().astype(np.uint8)


def _parse_shapes(text: str, width: int, height: int):
    shapes = []
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.replace(",", " ").split()
        kind, values = fields[0].casefold(), fields[1:]
        try:
            numbers = [float(value) for value in values]
        except ValueError as exc:
            raise ValueError(f"Invalid region coordinate on line {line_number}.") from exc
        if kind in {"box", "ellipse"} and len(numbers) == 4:
            x0, y0, x1, y1 = numbers
            shapes.append((kind, (x0 * width, y0 * height, x1 * width, y1 * height)))
        elif kind == "polygon" and len(numbers) >= 6 and len(numbers) % 2 == 0:
            points = [
                (numbers[index] * width, numbers[index + 1] * height)
                for index in range(0, len(numbers), 2)
            ]
            shapes.append((kind, points))
        else:
            raise ValueError(
                f"Line {line_number} must be 'box x0 y0 x1 y1', "
                "'ellipse x0 y0 x1 y1', or 'polygon x1 y1 x2 y2 x3 y3 ...'."
            )
        if any(number < 0.0 or number > 1.0 for number in numbers):
            raise ValueError(f"Region coordinates on line {line_number} must be 0..1.")
    if not shapes:
        raise ValueError("At least one box, ellipse, or polygon is required.")
    return shapes


def _mask_pixels(image_pixels, regions: str, color_filter: str, threshold: float, feather: float):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    height, width = image_pixels.shape[:2]
    canvas = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(canvas)
    for kind, coordinates in _parse_shapes(regions, width, height):
        if kind == "box":
            draw.rectangle(coordinates, fill=255)
        elif kind == "ellipse":
            draw.ellipse(coordinates, fill=255)
        else:
            draw.polygon(coordinates, fill=255)
    selection = np.asarray(canvas, dtype=np.float32) / 255.0
    rgb = image_pixels.astype(np.float32) / 255.0
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    cutoff = float(threshold)
    mode = color_filter.casefold()
    if mode == "red":
        selection *= (red >= cutoff) & (red > green * 1.18) & (red > blue * 1.12)
    elif mode == "warm":
        selection *= (red >= cutoff) & (red > green * 1.04) & (green > blue * 1.08)
    elif mode == "bright":
        selection *= np.max(rgb, axis=2) >= cutoff
    elif mode == "neutral_bright":
        channel_spread = np.max(rgb, axis=2) - np.min(rgb, axis=2)
        luminance = (red * 0.2126) + (green * 0.7152) + (blue * 0.0722)
        selection *= (luminance >= cutoff) & (channel_spread <= 0.16)
    elif mode != "none":
        raise ValueError(f"Unsupported color filter: {color_filter}")
    mask = Image.fromarray(np.clip(selection * 255.0, 0, 255).astype(np.uint8), "L")
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=float(feather)))
    return np.asarray(mask, dtype=np.float32) / 255.0


def _write_audio_wav(audio: dict, destination: Path) -> float:
    import numpy as np

    waveform = audio.get("waveform")
    sample_rate = int(audio.get("sample_rate", 0))
    if waveform is None or sample_rate <= 0:
        raise ValueError("Audio must contain waveform and a positive sample rate.")
    samples = waveform.detach().to("cpu", dtype=__import__("torch").float32).numpy()
    if samples.ndim == 3:
        samples = samples[0]
    if samples.ndim == 1:
        samples = samples[None, :]
    samples = np.clip(samples, -1.0, 1.0)
    pcm = (samples.T * 32767.0).round().astype("<i2")
    with wave.open(str(destination), "wb") as handle:
        handle.setnchannels(int(pcm.shape[1]))
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return samples.shape[1] / sample_rate


def _normalize_feature(values):
    import numpy as np

    values = np.asarray(values, dtype=np.float32)
    if not values.size or float(np.max(values)) <= 1e-9:
        return np.zeros_like(values)
    floor, ceiling = np.percentile(values, (10, 95))
    if ceiling <= floor + 1e-9:
        ceiling = float(np.max(values))
        floor = float(np.min(values))
    return np.clip((values - floor) / max(ceiling - floor, 1e-9), 0.0, 1.0)


def _audio_features(audio: dict, fps: int, duration: float):
    """Extract deterministic low beat, onset, high-band, and slow energy envelopes."""
    import numpy as np

    waveform = audio["waveform"].detach().to("cpu", dtype=__import__("torch").float32).numpy()
    sample_rate = int(audio["sample_rate"])
    if waveform.ndim == 3:
        waveform = waveform[0]
    if waveform.ndim == 2:
        waveform = waveform.mean(axis=0)
    frame_count = max(1, math.ceil(duration * fps))
    window_size = min(4096, max(1024, 2 ** int(math.ceil(math.log2(sample_rate * 0.06)))))
    taper = np.hanning(window_size).astype(np.float32)
    frequencies = np.fft.rfftfreq(window_size, 1.0 / sample_rate)
    low_bins = (frequencies >= 35.0) & (frequencies <= 180.0)
    high_bins = (frequencies >= 1800.0) & (frequencies <= min(9000.0, sample_rate / 2))
    rms, low, high, onset = [], [], [], []
    previous = None
    half = window_size // 2
    for index in range(frame_count):
        center = round(index * sample_rate / fps)
        start, end = center - half, center + half
        segment = np.zeros(window_size, dtype=np.float32)
        source_start, source_end = max(0, start), min(len(waveform), end)
        if source_end > source_start:
            destination_start = source_start - start
            segment[destination_start : destination_start + source_end - source_start] = waveform[source_start:source_end]
        spectrum = np.abs(np.fft.rfft(segment * taper)).astype(np.float32)
        rms.append(float(np.sqrt(np.mean(segment * segment))))
        low.append(float(np.mean(spectrum[low_bins])) if np.any(low_bins) else 0.0)
        high.append(float(np.mean(spectrum[high_bins])) if np.any(high_bins) else 0.0)
        onset.append(0.0 if previous is None else float(np.mean(np.maximum(spectrum - previous, 0.0))))
        previous = spectrum
    energy = _normalize_feature(rms)
    low = _normalize_feature(low)
    high = _normalize_feature(high)
    onset = _normalize_feature(onset)

    slow = np.empty_like(energy)
    state = 0.0
    coefficient = 1.0 - math.exp(-1.0 / max(1.0, fps * 1.5))
    for index, value in enumerate(energy):
        state += coefficient * (float(value) - state)
        slow[index] = state

    score = 0.70 * low + 0.30 * onset
    beat = np.zeros(frame_count, dtype=np.float32)
    minimum_gap = max(1, round(fps * 0.24))
    last_peak = -minimum_gap
    for index in range(1, frame_count - 1):
        if index - last_peak < minimum_gap:
            continue
        if score[index] >= 0.38 and score[index] >= score[index - 1] and score[index] > score[index + 1]:
            amplitude = min(1.0, 0.35 + float(score[index]))
            tail = min(frame_count, index + max(2, round(fps * 0.34)))
            for position in range(index, tail):
                beat[position] = max(beat[position], amplitude * math.exp(-(position - index) / max(1.0, fps * 0.10)))
            last_peak = index
    return {"beat": beat, "onset": onset, "high": high, "slow": slow, "energy": energy}


@dataclass
class _Layer:
    mask: object
    bounds: tuple[int, int, int, int] | None


def _prepare_layer(mask, width: int, height: int) -> _Layer:
    import numpy as np
    from PIL import Image

    value = mask.detach().to("cpu")
    if value.ndim == 3:
        value = value[0]
    pixels = np.clip(value.numpy(), 0.0, 1.0)
    resized = np.asarray(
        Image.fromarray((pixels * 255).astype(np.uint8), "L").resize((width, height), Image.Resampling.LANCZOS),
        dtype=np.float32,
    ) / 255.0
    selected = np.argwhere(resized > 0.005)
    if not selected.size:
        return _Layer(resized, None)
    y0, x0 = selected.min(axis=0)
    y1, x1 = selected.max(axis=0) + 1
    return _Layer(resized, (int(x0), int(y0), int(x1), int(y1)))


def _blend(frame, changed, layer: _Layer, opacity: float = 1.0):
    import numpy as np

    if layer.bounds is None:
        return
    x0, y0, x1, y1 = layer.bounds
    alpha = np.clip(layer.mask[y0:y1, x0:x1, None] * opacity, 0.0, 1.0)
    original = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = np.clip(original * (1.0 - alpha) + changed * alpha, 0, 255).astype(np.uint8)


def _expanded_layer(layer: _Layer, radius: float) -> _Layer:
    import numpy as np
    from PIL import Image, ImageFilter

    if layer.bounds is None or radius <= 0:
        return layer
    mask = Image.fromarray(np.clip(layer.mask * 255.0, 0, 255).astype(np.uint8), "L")
    expanded = np.asarray(mask.filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.float32) / 255.0
    selected = np.argwhere(expanded > 0.005)
    if not selected.size:
        return _Layer(expanded, None)
    y0, x0 = selected.min(axis=0)
    y1, x1 = selected.max(axis=0) + 1
    return _Layer(expanded, (int(x0), int(y0), int(x1), int(y1)))


def _overlay_pixels(image, mask):
    import numpy as np
    from PIL import Image

    rgb = _image_pixels(image)
    value = mask.detach().to("cpu")
    if value.ndim == 3:
        value = value[0]
    alpha = 1.0 - np.clip(value.numpy(), 0.0, 1.0)
    if alpha.shape != rgb.shape[:2]:
        alpha = np.asarray(
            Image.fromarray((alpha * 255).astype(np.uint8), "L").resize(
                (rgb.shape[1], rgb.shape[0]), Image.Resampling.LANCZOS
            ),
            dtype=np.float32,
        ) / 255.0
    return rgb, alpha


def _prepare_overlay(image, mask, target_width, opacity, x, y):
    import numpy as np
    from PIL import Image

    rgb, alpha = _overlay_pixels(image, mask)
    height = max(1, round(rgb.shape[0] * target_width / rgb.shape[1]))
    rgb = np.asarray(
        Image.fromarray(rgb, "RGB").resize((target_width, height), Image.Resampling.LANCZOS),
        dtype=np.float32,
    )
    alpha = np.asarray(
        Image.fromarray((alpha * 255).astype(np.uint8), "L").resize(
            (target_width, height), Image.Resampling.LANCZOS
        ),
        dtype=np.float32,
    ) / 255.0
    return rgb, np.clip(alpha * opacity, 0.0, 1.0), int(x), int(y)


def _apply_overlay(frame, overlay):
    import numpy as np

    rgb, alpha, x, y = overlay
    height, width = rgb.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(frame.shape[1], x + width), min(frame.shape[0], y + height)
    if x1 <= x0 or y1 <= y0:
        return
    sx0, sy0 = x0 - x, y0 - y
    sx1, sy1 = sx0 + x1 - x0, sy0 + y1 - y0
    local_alpha = alpha[sy0:sy1, sx0:sx1, None]
    original = frame[y0:y1, x0:x1].astype(np.float32)
    changed = rgb[sy0:sy1, sx0:sx1]
    frame[y0:y1, x0:x1] = np.clip(
        original * (1.0 - local_alpha) + changed * local_alpha, 0, 255
    ).astype(np.uint8)


def _halo_overlay(overlay, opacity: float, blur: float):
    import numpy as np
    from PIL import Image, ImageFilter

    _, alpha, x, y = overlay
    padding = max(2, math.ceil(blur * 3))
    canvas = Image.new("L", (alpha.shape[1] + padding * 2, alpha.shape[0] + padding * 2), 0)
    canvas.paste(Image.fromarray(np.clip(alpha * 255, 0, 255).astype(np.uint8), "L"), (padding, padding))
    halo_alpha = np.asarray(canvas.filter(ImageFilter.GaussianBlur(radius=blur)), dtype=np.float32) / 255.0
    halo_rgb = np.zeros((*halo_alpha.shape, 3), dtype=np.float32)
    return halo_rgb, np.clip(halo_alpha * opacity, 0.0, 1.0), x - padding, y - padding


class VisualizerCandidateRegions:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "candidate_type": (
                    ["bright highlights", "warm lights", "red accents", "neutral atmosphere", "textured motion"],
                    {"default": "bright highlights"},
                ),
                "sensitivity": ("FLOAT", {"default": 0.65, "min": 0.1, "max": 0.95, "step": 0.05}),
                "max_regions": ("INT", {"default": 6, "min": 1, "max": 16}),
                "padding_percent": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 15.0, "step": 0.5}),
            }
        }

    RETURN_TYPES = ("STRING", "MASK", "IMAGE")
    RETURN_NAMES = ("suggested_regions", "candidate_mask", "candidate_preview")
    FUNCTION = "discover"
    CATEGORY = "audio/local visualizer"
    DESCRIPTION = "Suggest inspectable normalized boxes for likely local animation targets."

    def discover(self, image, candidate_type, sensitivity, max_regions, padding_percent):
        import numpy as np
        import torch
        from PIL import Image, ImageFilter

        pixels = _image_pixels(image).astype(np.float32) / 255.0
        height, width = pixels.shape[:2]
        red, green, blue = pixels[..., 0], pixels[..., 1], pixels[..., 2]
        luma = red * 0.2126 + green * 0.7152 + blue * 0.0722
        spread = np.max(pixels, axis=2) - np.min(pixels, axis=2)
        mode = candidate_type.casefold()
        if mode == "bright highlights":
            score = luma * luma
        elif mode == "warm lights":
            score = np.clip(red - blue * 0.65, 0, 1) * np.clip(luma * 1.4, 0, 1)
        elif mode == "red accents":
            score = np.clip(red - np.maximum(green, blue) * 0.85, 0, 1) * red
        elif mode == "neutral atmosphere":
            score = np.clip(luma * 1.5, 0, 1) * np.clip(1.0 - spread * 3.0, 0, 1)
        else:
            dx = np.abs(np.diff(luma, axis=1, prepend=luma[:, :1]))
            dy = np.abs(np.diff(luma, axis=0, prepend=luma[:1, :]))
            score = np.clip((dx + dy) * 3.0, 0, 1)

        columns, rows = 16, 9
        grid = np.zeros((rows, columns), dtype=np.float32)
        for row in range(rows):
            y0, y1 = row * height // rows, (row + 1) * height // rows
            for column in range(columns):
                x0, x1 = column * width // columns, (column + 1) * width // columns
                tile = score[y0:y1, x0:x1]
                grid[row, column] = float(np.percentile(tile, 85))
        cutoff = float(np.quantile(grid, min(0.98, 0.50 + sensitivity * 0.48)))
        active = grid >= max(cutoff, 0.02)
        groups = []
        visited = np.zeros_like(active, dtype=bool)
        for row in range(rows):
            for column in range(columns):
                if not active[row, column] or visited[row, column]:
                    continue
                stack, cells = [(row, column)], []
                visited[row, column] = True
                while stack:
                    current_row, current_column = stack.pop()
                    cells.append((current_row, current_column))
                    for next_row, next_column in (
                        (current_row - 1, current_column), (current_row + 1, current_column),
                        (current_row, current_column - 1), (current_row, current_column + 1),
                    ):
                        if 0 <= next_row < rows and 0 <= next_column < columns and active[next_row, next_column] and not visited[next_row, next_column]:
                            visited[next_row, next_column] = True
                            stack.append((next_row, next_column))
                value = float(np.mean([grid[r, c] for r, c in cells]))
                if mode in {"bright highlights", "warm lights", "red accents"}:
                    value /= math.sqrt(len(cells))
                groups.append((value, cells))
        groups.sort(key=lambda item: item[0], reverse=True)
        if not groups:
            best_row, best_column = np.unravel_index(int(np.argmax(grid)), grid.shape)
            groups = [(float(grid[best_row, best_column]), [(int(best_row), int(best_column))])]
        padding = float(padding_percent) / 100.0
        lines = [f"# Suggested {candidate_type}; inspect and correct before rendering."]
        for _, cells in groups[: int(max_regions)]:
            row_values, column_values = zip(*cells)
            x0 = max(0.0, min(column_values) / columns - padding)
            y0 = max(0.0, min(row_values) / rows - padding)
            x1 = min(1.0, (max(column_values) + 1) / columns + padding)
            y1 = min(1.0, (max(row_values) + 1) / rows + padding)
            lines.append(f"box {x0:.4f} {y0:.4f} {x1:.4f} {y1:.4f}")
        regions = "\n".join(lines)
        mask = _mask_pixels((pixels * 255).astype(np.uint8), regions, "none", 0.0, 4.0)
        preview = pixels * (1.0 - mask[..., None] * 0.35)
        preview[..., 1] += mask * 0.35
        preview_image = Image.fromarray(
            np.clip(preview * 255.0, 0, 255).astype(np.uint8), "RGB"
        )
        if preview_image.width > 640:
            preview_image = preview_image.resize(
                (640, max(1, round(preview_image.height * 640 / preview_image.width))),
                Image.Resampling.LANCZOS,
            )
        return (
            regions,
            torch.from_numpy(mask),
            torch.from_numpy(np.asarray(preview_image, dtype=np.float32) / 255.0)[None, ...],
        )


class VisualizerRegionMask:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "regions": ("STRING", {"multiline": True, "default": "box 0.1 0.1 0.4 0.4"}),
                "color_filter": (["none", "red", "warm", "bright", "neutral_bright"], {"default": "none"}),
                "threshold": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 1.0, "step": 0.01}),
                "feather_px": ("FLOAT", {"default": 8.0, "min": 0.0, "max": 100.0, "step": 0.5}),
            }
        }

    RETURN_TYPES = ("MASK", "IMAGE")
    RETURN_NAMES = ("mask", "mask_preview")
    FUNCTION = "build"
    CATEGORY = "audio/local visualizer"
    DESCRIPTION = "Build a transparent, inspectable mask from normalized boxes, ellipses, or polygons."

    def build(self, image, regions, color_filter, threshold, feather_px):
        import numpy as np
        import torch
        from PIL import Image

        pixels = _image_pixels(image)
        mask = _mask_pixels(pixels, regions, color_filter, threshold, feather_px)
        preview = pixels.astype(np.float32) / 255.0
        preview = preview * (1.0 - mask[..., None] * 0.35)
        preview[..., 0] += mask * 0.35
        preview_image = Image.fromarray(
            np.clip(preview * 255.0, 0, 255).astype(np.uint8), "RGB"
        )
        if preview_image.width > 640:
            preview_height = max(1, round(preview_image.height * 640 / preview_image.width))
            preview_image = preview_image.resize((640, preview_height), Image.Resampling.LANCZOS)
        preview_tensor = torch.from_numpy(
            np.asarray(preview_image, dtype=np.float32) / 255.0
        )[None, ...]
        return (torch.from_numpy(mask), preview_tensor)


class BeatAwareLocalVisualizer:
    @classmethod
    def INPUT_TYPES(cls):
        strength = {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05}
        return {
            "required": {
                "image": ("IMAGE",),
                "audio": ("AUDIO",),
                "brand_logo": ("IMAGE",),
                "brand_logo_mask": ("MASK",),
                "wordmark": ("IMAGE",),
                "wordmark_mask": ("MASK",),
                "cloud_mask": ("MASK",),
                "candle_mask": ("MASK",),
                "red_light_mask": ("MASK",),
                "monitor_mask": ("MASK",),
                "rain_mask": ("MASK",),
                "reflection_mask": ("MASK",),
                "fps": ("INT", {"default": 16, "min": 8, "max": 30}),
                "delivery_resolution": (["720p", "1080p", "source"], {"default": "1080p"}),
                "pattern_key": ("INT", {"default": 20261007, "min": 0, "max": 0x7FFFFFFF}),
                "cloud_strength": ("FLOAT", strength),
                "candle_strength": ("FLOAT", strength),
                "red_light_strength": ("FLOAT", strength),
                "monitor_strength": ("FLOAT", strength),
                "rain_strength": ("FLOAT", {**strength, "default": 0.55}),
                "reflection_strength": ("FLOAT", {**strength, "default": 0.65}),
                "apply_brand_logo": ("BOOLEAN", {"default": True}),
                "brand_logo_width_percent": ("FLOAT", {"default": 10.0, "min": 2.0, "max": 40.0, "step": 1.0}),
                "brand_logo_opacity": ("FLOAT", {"default": 0.68, "min": 0.05, "max": 1.0, "step": 0.01}),
                "apply_wordmark": ("BOOLEAN", {"default": True}),
                "wordmark_width_percent": ("FLOAT", {"default": 32.0, "min": 5.0, "max": 80.0, "step": 1.0}),
                "wordmark_opacity": ("FLOAT", {"default": 0.95, "min": 0.05, "max": 1.0, "step": 0.01}),
                "overlay_margin_px": ("INT", {"default": 24, "min": 0, "max": 200}),
                "wordmark_halo_opacity": ("FLOAT", {"default": 0.55, "min": 0.0, "max": 1.0, "step": 0.01}),
                "wordmark_halo_blur_px": ("FLOAT", {"default": 18.0, "min": 0.5, "max": 100.0, "step": 0.5}),
                "output_prefix": ("STRING", {"default": "local_visualizer/managed_decline"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("output_path",)
    OUTPUT_NODE = True
    FUNCTION = "render"
    CATEGORY = "audio/local visualizer"
    DESCRIPTION = "Stream a full-song, beat-aware procedural composite while keeping unmasked pixels static."

    def render(
        self, image, audio, brand_logo, brand_logo_mask, wordmark, wordmark_mask,
        cloud_mask, candle_mask, red_light_mask, monitor_mask,
        rain_mask, reflection_mask, fps, delivery_resolution, pattern_key, cloud_strength,
        candle_strength, red_light_strength, monitor_strength, rain_strength,
        reflection_strength, apply_brand_logo, brand_logo_width_percent,
        brand_logo_opacity, apply_wordmark, wordmark_width_percent,
        wordmark_opacity, overlay_margin_px, wordmark_halo_opacity,
        wordmark_halo_blur_px, output_prefix,
    ):
        import folder_paths
        import numpy as np
        from PIL import Image, ImageDraw

        try:
            from comfy.utils import ProgressBar
        except ImportError:
            ProgressBar = None

        if shutil.which("ffmpeg") is None:
            raise RuntimeError("FFmpeg must be available on PATH.")
        source = Image.fromarray(_image_pixels(image), "RGB")
        source_width, source_height = source.size
        if delivery_resolution == "720p":
            width, height = 1280, 720
        elif delivery_resolution == "1080p":
            width, height = 1920, 1080
        elif delivery_resolution == "source":
            width, height = source_width, source_height
        else:
            raise ValueError(f"Unsupported delivery resolution: {delivery_resolution}")
        if (width, height) != (source_width, source_height):
            source = source.resize((width, height), Image.Resampling.LANCZOS)
        base = np.asarray(source, dtype=np.uint8)
        layers = {
            "cloud": _prepare_layer(cloud_mask, width, height),
            "candle": _prepare_layer(candle_mask, width, height),
            "red": _prepare_layer(red_light_mask, width, height),
            "monitor": _prepare_layer(monitor_mask, width, height),
            "rain": _prepare_layer(rain_mask, width, height),
            "reflection": _prepare_layer(reflection_mask, width, height),
        }
        candle_halo = _expanded_layer(layers["candle"], max(6.0, width / 160.0))
        overlays = []
        margin = round(float(overlay_margin_px) * width / 1920)
        if bool(apply_wordmark):
            wordmark_overlay = _prepare_overlay(
                wordmark, wordmark_mask, max(2, round(width * float(wordmark_width_percent) / 100.0)),
                float(wordmark_opacity), margin, margin,
            )
            if float(wordmark_halo_opacity) > 0:
                overlays.append(_halo_overlay(wordmark_overlay, float(wordmark_halo_opacity), float(wordmark_halo_blur_px)))
            overlays.append(wordmark_overlay)
        if bool(apply_brand_logo):
            target_width = max(2, round(width * float(brand_logo_width_percent) / 100.0))
            rgb, alpha = _overlay_pixels(brand_logo, brand_logo_mask)
            target_height = max(1, round(rgb.shape[0] * target_width / rgb.shape[1]))
            overlays.append(_prepare_overlay(
                brand_logo, brand_logo_mask, target_width, float(brand_logo_opacity),
                width - target_width - margin, height - target_height - margin,
            ))
        prefix = _safe_name(str(output_prefix).replace("\\", "/").split("/")[-1])
        parent = Path(str(output_prefix).replace("\\", "/")).parent.as_posix()
        save_prefix = f"{parent}/{prefix}" if parent not in {"", "."} else prefix
        output_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
            save_prefix, folder_paths.get_output_directory(), width, height
        )
        output_file = f"{filename}_{counter:05}_.mp4"
        output_path = Path(output_folder) / output_file

        with tempfile.TemporaryDirectory(prefix="local-visualizer-") as temporary:
            audio_path = Path(temporary) / "audio.wav"
            duration = _write_audio_wav(audio, audio_path)
            progress = ProgressBar(max(1, math.ceil(duration * int(fps))) + 3) if ProgressBar else None
            if progress:
                progress.update_absolute(1)
            features = _audio_features(audio, int(fps), duration)
            frame_count = len(features["energy"])
            if progress:
                progress.update_absolute(2, frame_count + 3)
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{width}x{height}",
                "-framerate", str(int(fps)), "-i", "-", "-i", str(audio_path),
                "-map", "0:v:0", "-map", "1:a:0", "-t", f"{duration:.9f}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output_path),
            ]
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            pattern_key = int(pattern_key)
            rng = np.random.default_rng(pattern_key)
            rain = layers["rain"]
            drops = []
            if rain.bounds is not None:
                x0, y0, x1, y1 = rain.bounds
                for _ in range(max(100, (x1 - x0) * (y1 - y0) // 9000)):
                    drops.append((rng.uniform(x0, x1), rng.uniform(y0, y1), rng.uniform(45, 150), rng.uniform(12, 34)))
            cloud_rows = cloud_columns = None
            if layers["cloud"].bounds:
                x0, y0, x1, y1 = layers["cloud"].bounds
                cloud_rows = np.arange(y1 - y0, dtype=np.float32)[:, None, None]
                cloud_columns = np.arange(x1 - x0, dtype=np.float32)[None, :, None]
            reflection_rows = None
            if layers["reflection"].bounds:
                x0, y0, x1, y1 = layers["reflection"].bounds
                reflection_rows = np.arange(y1 - y0, dtype=np.float32)[:, None, None]
            try:
                for index in range(frame_count):
                    frame = base.copy()
                    seconds = index / float(fps)

                    layer = layers["cloud"]
                    if layer.bounds and cloud_strength > 0:
                        x0, y0, x1, y1 = layer.bounds
                        crop = base[y0:y1, x0:x1].astype(np.float32)
                        flow_a = np.sin(cloud_columns * 0.008 + cloud_rows * 0.005 - seconds * 0.55)
                        flow_b = np.cos(cloud_columns * 0.004 - cloud_rows * 0.009 + seconds * 0.37)
                        flow = 0.5 * (flow_a + flow_b)
                        changed = crop * (
                            1.0 + cloud_strength * (0.025 + 0.065 * features["slow"][index] + 0.09 * flow)
                        )
                        _blend(frame, changed, layer, min(1.0, cloud_strength))

                    layer = layers["candle"]
                    if layer.bounds and candle_strength > 0:
                        x0, y0, x1, y1 = layer.bounds
                        crop = base[y0:y1, x0:x1].astype(np.float32)
                        jitter = 0.5 + 0.5 * math.sin(seconds * 17.3 + pattern_key * 0.01) * math.sin(seconds * 7.1)
                        drive = 0.45 * features["high"][index] + 0.35 * features["onset"][index] + 0.20 * jitter
                        changed = crop * (1.0 + candle_strength * 0.48 * drive)
                        changed[..., 0] += candle_strength * 46.0 * drive
                        changed[..., 1] += candle_strength * 18.0 * drive
                        _blend(frame, changed, layer)
                        if candle_halo.bounds:
                            hx0, hy0, hx1, hy1 = candle_halo.bounds
                            halo = base[hy0:hy1, hx0:hx1].astype(np.float32)
                            halo[..., 0] += candle_strength * 34.0 * drive
                            halo[..., 1] += candle_strength * 13.0 * drive
                            _blend(frame, halo, candle_halo, min(0.75, 0.35 + 0.35 * drive))

                    layer = layers["red"]
                    if layer.bounds and red_light_strength > 0:
                        x0, y0, x1, y1 = layer.bounds
                        crop = base[y0:y1, x0:x1].astype(np.float32)
                        drive = features["beat"][index]
                        changed = crop * (1.0 + red_light_strength * 0.38 * drive)
                        changed[..., 0] += red_light_strength * 55.0 * drive
                        _blend(frame, changed, layer)

                    layer = layers["monitor"]
                    if layer.bounds and monitor_strength > 0:
                        x0, y0, x1, y1 = layer.bounds
                        crop = base[y0:y1, x0:x1].astype(np.float32)
                        drive = 0.65 * features["onset"][index] + 0.35 * features["energy"][index]
                        scan = (np.sin(np.arange(y1 - y0)[:, None] * 0.22 + seconds * 8.0) + 1.0) * 0.5
                        changed = crop * (1.0 + monitor_strength * (0.26 * drive + 0.07 * scan[..., None]))
                        changed[..., 0] += monitor_strength * 34.0 * drive
                        changed[..., 1] += monitor_strength * 5.0 * drive
                        _blend(frame, changed, layer)

                    if rain.bounds and rain_strength > 0 and drops:
                        x0, y0, x1, y1 = rain.bounds
                        overlay = Image.new("RGB", (x1 - x0, y1 - y0), (0, 0, 0))
                        alpha = Image.new("L", overlay.size, 0)
                        overlay_draw, alpha_draw = ImageDraw.Draw(overlay), ImageDraw.Draw(alpha)
                        drive = 0.25 + 0.75 * features["slow"][index]
                        for drop_x, drop_y, speed, length in drops:
                            y = y0 + ((drop_y - y0 + speed * seconds) % max(1, y1 - y0))
                            start = (round(drop_x - x0), round(y - y0))
                            end = (round(drop_x - x0 - length * 0.18), round(y - y0 + length))
                            overlay_draw.line((start, end), fill=(180, 195, 205), width=2)
                            alpha_draw.line((start, end), fill=round(min(210, 145 * rain_strength * drive)), width=2)
                        rain_pixels = np.asarray(overlay, dtype=np.float32)
                        rain_alpha = np.asarray(alpha, dtype=np.float32)[..., None] / 255.0
                        original = frame[y0:y1, x0:x1].astype(np.float32)
                        changed = original * (1.0 - rain_alpha) + rain_pixels * rain_alpha
                        _blend(frame, changed, rain)

                    layer = layers["reflection"]
                    if layer.bounds and reflection_strength > 0:
                        x0, y0, x1, y1 = layer.bounds
                        crop = base[y0:y1, x0:x1].astype(np.float32)
                        shimmer = 0.5 + 0.5 * np.sin(reflection_rows * 0.09 + seconds * 2.7)
                        drive = 0.55 * features["beat"][index] + 0.45 * features["slow"][index]
                        changed = crop * (1.0 + reflection_strength * 0.30 * drive * shimmer)
                        changed[..., 0] += reflection_strength * 38.0 * drive * shimmer[..., 0]
                        _blend(frame, changed, layer)

                    for overlay in overlays:
                        _apply_overlay(frame, overlay)

                    process.stdin.write(np.ascontiguousarray(frame).tobytes())
                    if progress:
                        progress.update_absolute(index + 3, frame_count + 3)
                process.stdin.close()
                error = process.stderr.read().decode("utf-8", errors="replace").strip()
                return_code = process.wait()
                if return_code:
                    raise RuntimeError(f"FFmpeg failed: {error or return_code}")
                if progress:
                    progress.update_absolute(frame_count + 3, frame_count + 3)
            except BaseException:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                process.kill()
                process.wait()
                raise

        preview = {"filename": output_file, "subfolder": subfolder, "type": "output"}
        return {"ui": {"images": [preview], "animated": (True,)}, "result": (str(output_path),)}


def _target_candidate_type(target_description: str) -> str:
    value = target_description.casefold()
    if any(word in value for word in ("candle", "flame", "fire", "lamp", "warm")):
        return "warm lights"
    if any(word in value for word in ("red", "warning", "taillight", "neon")):
        return "red accents"
    if any(word in value for word in ("cloud", "smoke", "fog", "mist", "steam")):
        return "neutral atmosphere"
    if any(word in value for word in ("monitor", "screen", "display", "window", "light")):
        return "bright highlights"
    return "textured motion"


def _target_effect_modes(object_name: str, animation_prompt: str) -> tuple[str, ...]:
    text = f"{object_name} {animation_prompt}".casefold()
    modes = []
    keywords = (
        ("drift", ("drift", "billow", "roll", "flow", "cloud", "smoke", "fog", "mist", "steam")),
        ("flicker", ("flicker", "flutter", "candle", "flame", "fire")),
        ("flash", ("flash", "lightning", "strobe", "pulse", "throb")),
        ("scan", ("scan", "monitor", "screen", "display", "crt")),
        ("rain", ("rain", "droplet", "streak")),
        ("shimmer", ("shimmer", "reflection", "glint", "sparkle", "water")),
    )
    for mode, words in keywords:
        if any(word in text for word in words):
            modes.append(mode)
    return tuple(modes or ("drift",))


class VisualizerObjectDetector:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "find": ("STRING", {"default": "clouds"}),
                "search_area": ("STRING", {"multiline": True, "default": "box 0 0 1 1"}),
                "sensitivity": ("FLOAT", {"default": 0.65, "min": 0.1, "max": 0.95, "step": 0.05}),
                "max_regions": ("INT", {"default": 6, "min": 1, "max": 16}),
                "padding_percent": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 15.0, "step": 0.5}),
            }
        }

    RETURN_TYPES = ("MASK", "IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("detected_mask", "verification_preview", "suggested_regions", "detector_report")
    FUNCTION = "detect"
    CATEGORY = "audio/local visualizer/targets"
    DESCRIPTION = "Find likely instances of an object class and produce an inspectable mask; user verification is required."

    def detect(self, image, find, search_area, sensitivity, max_regions, padding_percent):
        import numpy as np
        import torch
        from PIL import Image, ImageFilter

        target = str(find).strip()
        if not target:
            raise ValueError("Describe the object class to find.")
        candidate_type = _target_candidate_type(target)
        regions, candidate_mask, _ = VisualizerCandidateRegions().discover(
            image, candidate_type, sensitivity, max_regions, padding_percent
        )
        pixels = _image_pixels(image)
        rgb = pixels.astype(np.float32) / 255.0
        red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        luma = red * 0.2126 + green * 0.7152 + blue * 0.0722
        spread = np.max(rgb, axis=2) - np.min(rgb, axis=2)
        if candidate_type == "bright highlights":
            score = luma * luma
        elif candidate_type == "warm lights":
            score = np.clip(red - blue * 0.65, 0, 1) * np.clip(luma * 1.4, 0, 1)
        elif candidate_type == "red accents":
            score = np.clip(red - np.maximum(green, blue) * 0.85, 0, 1) * red
        elif candidate_type == "neutral atmosphere":
            score = np.clip(luma * 1.5, 0, 1) * np.clip(1.0 - spread * 3.0, 0, 1)
        else:
            dx = np.abs(np.diff(luma, axis=1, prepend=luma[:, :1]))
            dy = np.abs(np.diff(luma, axis=0, prepend=luma[:1, :]))
            score = np.clip((dx + dy) * 3.0, 0, 1)
        area = _mask_pixels(pixels, search_area, "none", 0.0, 2.0)
        proposal = np.clip(candidate_mask.detach().to("cpu").numpy() * area, 0.0, 1.0)
        eligible = proposal > 0.05
        cutoff = float(np.quantile(score[eligible], min(0.97, 0.58 + float(sensitivity) * 0.37))) if np.any(eligible) else 1.0
        mask = ((score >= max(0.02, cutoff)) & eligible).astype(np.float32)
        mask = np.asarray(
            Image.fromarray((mask * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(radius=4.0)),
            dtype=np.float32,
        ) / 255.0
        preview = pixels.astype(np.float32) / 255.0
        preview = preview * (1.0 - mask[..., None] * 0.42)
        preview[..., 1] += mask * 0.42
        preview_image = Image.fromarray(np.clip(preview * 255.0, 0, 255).astype(np.uint8), "RGB")
        if preview_image.width > 640:
            preview_image = preview_image.resize(
                (640, max(1, round(preview_image.height * 640 / preview_image.width))),
                Image.Resampling.LANCZOS,
            )
        selected_fraction = float(np.mean(mask > 0.05))
        report = (
            f"'{target}' used the {candidate_type} detector; selected {selected_fraction:.1%} of the frame. "
            "Inspect verification_preview, constrain search_area or sensitivity if needed, then explicitly verify the target."
        )
        return (
            torch.from_numpy(mask.astype(np.float32)),
            torch.from_numpy(np.asarray(preview_image, dtype=np.float32) / 255.0)[None, ...],
            regions,
            report,
        )


class VisualizerAnimationTarget:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mask": ("MASK",),
                "object_name": ("STRING", {"default": "clouds"}),
                "animation_prompt": ("STRING", {"multiline": True, "default": "clouds drifting slowly"}),
                "mask_verified": ("BOOLEAN", {"default": False}),
                "on_beat_strength": ("FLOAT", {"default": 0.75, "min": 0.0, "max": 2.0, "step": 0.05}),
                "off_beat_strength": ("FLOAT", {"default": 0.65, "min": 0.0, "max": 2.0, "step": 0.05}),
            }
        }

    RETURN_TYPES = ("LOCAL_VISUALIZER_TARGET", "STRING")
    RETURN_NAMES = ("animation_target", "resolved_effects")
    FUNCTION = "configure"
    CATEGORY = "audio/local visualizer/targets"
    DESCRIPTION = "Describe one verified animation target and independently mix beat-driven and autonomous motion."

    def configure(self, mask, object_name, animation_prompt, mask_verified, on_beat_strength, off_beat_strength):
        name = str(object_name).strip()
        prompt = str(animation_prompt).strip()
        if not name or not prompt:
            raise ValueError("Each animation target needs an object name and animation description.")
        modes = _target_effect_modes(name, prompt)
        target = {
            "mask": mask,
            "object_name": name,
            "animation_prompt": prompt,
            "mask_verified": bool(mask_verified),
            "on_beat_strength": float(on_beat_strength),
            "off_beat_strength": float(off_beat_strength),
            "effect_modes": modes,
        }
        summary = f"{name}: {', '.join(modes)}; beat {float(on_beat_strength):.2f}, off-beat {float(off_beat_strength):.2f}"
        return target, summary


class VisualizerTargetStack:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"target": ("LOCAL_VISUALIZER_TARGET",)},
            "optional": {"previous_targets": ("LOCAL_VISUALIZER_TARGETS",)},
        }

    RETURN_TYPES = ("LOCAL_VISUALIZER_TARGETS",)
    RETURN_NAMES = ("targets",)
    FUNCTION = "append"
    CATEGORY = "audio/local visualizer/targets"
    DESCRIPTION = "Append an animation target; duplicate a detector, target, and stack node to add another target."

    def append(self, target, previous_targets=None):
        return (tuple(previous_targets or ()) + (target,),)


class GenericBeatAwareLocalVisualizer:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",), "audio": ("AUDIO",),
                "targets": ("LOCAL_VISUALIZER_TARGETS",),
                "brand_logo": ("IMAGE",), "brand_logo_mask": ("MASK",),
                "wordmark": ("IMAGE",), "wordmark_mask": ("MASK",),
                "fps": ("INT", {"default": 16, "min": 8, "max": 30}),
                "delivery_resolution": (["720p", "1080p", "source"], {"default": "1080p"}),
                "pattern_key": ("INT", {"default": 20261007, "min": 0, "max": 0x7FFFFFFF}),
                "apply_brand_logo": ("BOOLEAN", {"default": True}),
                "brand_logo_width_percent": ("FLOAT", {"default": 10.0, "min": 2.0, "max": 40.0, "step": 1.0}),
                "brand_logo_opacity": ("FLOAT", {"default": 0.68, "min": 0.05, "max": 1.0, "step": 0.01}),
                "apply_wordmark": ("BOOLEAN", {"default": True}),
                "wordmark_width_percent": ("FLOAT", {"default": 32.0, "min": 5.0, "max": 80.0, "step": 1.0}),
                "wordmark_opacity": ("FLOAT", {"default": 0.95, "min": 0.05, "max": 1.0, "step": 0.01}),
                "overlay_margin_px": ("INT", {"default": 24, "min": 0, "max": 200}),
                "wordmark_halo_opacity": ("FLOAT", {"default": 0.55, "min": 0.0, "max": 1.0, "step": 0.01}),
                "wordmark_halo_blur_px": ("FLOAT", {"default": 18.0, "min": 0.5, "max": 100.0, "step": 0.5}),
                "output_prefix": ("STRING", {"default": "generic_visualizer/render"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("output_path",)
    OUTPUT_NODE = True
    FUNCTION = "render"
    CATEGORY = "audio/local visualizer/targets"
    DESCRIPTION = "Render any number of verified prompt-configured targets over a fixed source image."

    def render(
        self, image, audio, targets, brand_logo, brand_logo_mask, wordmark, wordmark_mask,
        fps, delivery_resolution, pattern_key, apply_brand_logo, brand_logo_width_percent,
        brand_logo_opacity, apply_wordmark, wordmark_width_percent, wordmark_opacity,
        overlay_margin_px, wordmark_halo_opacity, wordmark_halo_blur_px, output_prefix,
    ):
        import folder_paths
        import numpy as np
        from PIL import Image

        try:
            from comfy.utils import ProgressBar
        except ImportError:
            ProgressBar = None
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("FFmpeg must be available on PATH.")
        targets = tuple(targets or ())
        if not targets:
            raise ValueError("Add at least one animation target to the target stack.")
        unverified = [target["object_name"] for target in targets if not target.get("mask_verified")]
        if unverified:
            raise ValueError("Inspect each detection preview, then enable mask_verified for: " + ", ".join(unverified))

        source = Image.fromarray(_image_pixels(image), "RGB")
        source_width, source_height = source.size
        sizes = {"720p": (1280, 720), "1080p": (1920, 1080), "source": (source_width, source_height)}
        if delivery_resolution not in sizes:
            raise ValueError(f"Unsupported delivery resolution: {delivery_resolution}")
        width, height = sizes[delivery_resolution]
        if source.size != (width, height):
            source = source.resize((width, height), Image.Resampling.LANCZOS)
        base = np.asarray(source, dtype=np.uint8)

        plans = []
        for index, target in enumerate(targets):
            layer = _prepare_layer(target["mask"], width, height)
            if layer.bounds is None:
                raise ValueError(f"Verified target '{target['object_name']}' has an empty mask.")
            x0, y0, x1, y1 = layer.bounds
            plans.append({
                **target, "layer": layer,
                "rows": np.arange(y1 - y0, dtype=np.float32)[:, None, None],
                "columns": np.arange(x1 - x0, dtype=np.float32)[None, :, None],
                "phase": (int(pattern_key) * 0.0001 + index * 1.913) % (math.pi * 2.0),
            })

        overlays = []
        margin = round(float(overlay_margin_px) * width / 1920)
        if bool(apply_wordmark):
            overlay = _prepare_overlay(wordmark, wordmark_mask, max(2, round(width * float(wordmark_width_percent) / 100.0)), float(wordmark_opacity), margin, margin)
            if float(wordmark_halo_opacity) > 0:
                overlays.append(_halo_overlay(overlay, float(wordmark_halo_opacity), float(wordmark_halo_blur_px)))
            overlays.append(overlay)
        if bool(apply_brand_logo):
            target_width = max(2, round(width * float(brand_logo_width_percent) / 100.0))
            rgb, _ = _overlay_pixels(brand_logo, brand_logo_mask)
            target_height = max(1, round(rgb.shape[0] * target_width / rgb.shape[1]))
            overlays.append(_prepare_overlay(brand_logo, brand_logo_mask, target_width, float(brand_logo_opacity), width - target_width - margin, height - target_height - margin))

        prefix = _safe_name(str(output_prefix).replace("\\", "/").split("/")[-1])
        parent = Path(str(output_prefix).replace("\\", "/")).parent.as_posix()
        save_prefix = f"{parent}/{prefix}" if parent not in {"", "."} else prefix
        output_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(save_prefix, folder_paths.get_output_directory(), width, height)
        output_file = f"{filename}_{counter:05}_.mp4"
        output_path = Path(output_folder) / output_file

        with tempfile.TemporaryDirectory(prefix="generic-local-visualizer-") as temporary:
            audio_path = Path(temporary) / "audio.wav"
            duration = _write_audio_wav(audio, audio_path)
            features = _audio_features(audio, int(fps), duration)
            frame_count = len(features["energy"])
            progress = ProgressBar(frame_count + 3) if ProgressBar else None
            if progress:
                progress.update_absolute(2, frame_count + 3)
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                "-pixel_format", "rgb24", "-video_size", f"{width}x{height}", "-framerate", str(int(fps)),
                "-i", "-", "-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0", "-t", f"{duration:.9f}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output_path),
            ]
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                for frame_index in range(frame_count):
                    frame = base.copy()
                    seconds = frame_index / float(fps)
                    for plan in plans:
                        layer = plan["layer"]
                        x0, y0, x1, y1 = layer.bounds
                        changed = frame[y0:y1, x0:x1].astype(np.float32)
                        phase = plan["phase"]
                        beat = float(plan["on_beat_strength"]) * (0.72 * features["beat"][frame_index] + 0.28 * features["onset"][frame_index])
                        autonomous = float(plan["off_beat_strength"]) * (0.55 + 0.25 * math.sin(seconds * 0.83 + phase) + 0.20 * math.sin(seconds * 1.91 + phase * 1.7))
                        flow = 0.5 * (
                            np.sin(plan["columns"] * 0.008 + plan["rows"] * 0.005 - seconds * 0.55 + phase)
                            + np.cos(plan["columns"] * 0.004 - plan["rows"] * 0.009 + seconds * 0.37 + phase)
                        )
                        text = f"{plan['object_name']} {plan['animation_prompt']}".casefold()
                        for mode in plan["effect_modes"]:
                            if mode == "drift":
                                changed *= 1.0 + 0.045 * beat + autonomous * (0.035 + 0.10 * flow)
                            elif mode == "flicker":
                                irregular = max(0.0, 0.55 + 0.30 * math.sin(seconds * 17.3 + phase) + 0.15 * math.sin(seconds * 7.1 + phase * 2.0))
                                drive = beat + float(plan["off_beat_strength"]) * irregular
                                changed *= 1.0 + 0.22 * drive
                                if any(word in text for word in ("candle", "flame", "fire", "warm")):
                                    changed[..., 0] += 36.0 * drive
                                    changed[..., 1] += 14.0 * drive
                            elif mode == "flash":
                                sporadic = max(0.0, math.sin(seconds * 0.47 + phase)) ** 14
                                drive = beat + float(plan["off_beat_strength"]) * sporadic
                                changed += (45.0 if "lightning" in text else 28.0) * drive
                            elif mode == "scan":
                                scan = (np.sin(plan["rows"] * 0.22 + seconds * 8.0 + phase) + 1.0) * 0.5
                                drive = beat + autonomous
                                changed *= 1.0 + 0.08 * scan + 0.12 * drive
                                changed[..., 2] += 14.0 * drive
                            elif mode == "rain":
                                streak = ((plan["rows"] + plan["columns"] * 0.18 + seconds * 95.0 + phase * 11.0) % 43.0) < 1.4
                                drive = min(2.0, 0.35 + beat + autonomous)
                                changed += streak * (24.0 * drive)
                            elif mode == "shimmer":
                                shimmer = 0.5 + 0.5 * np.sin(plan["rows"] * 0.09 + seconds * 2.7 + phase)
                                drive = beat + autonomous
                                changed *= 1.0 + 0.16 * drive * shimmer
                        _blend(frame, changed, layer)
                    for overlay in overlays:
                        _apply_overlay(frame, overlay)
                    process.stdin.write(np.ascontiguousarray(frame).tobytes())
                    if progress:
                        progress.update_absolute(frame_index + 3, frame_count + 3)
                process.stdin.close()
                error = process.stderr.read().decode("utf-8", errors="replace").strip()
                return_code = process.wait()
                if return_code:
                    raise RuntimeError(f"FFmpeg failed: {error or return_code}")
            except BaseException:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                process.kill()
                process.wait()
                raise

        preview = {"filename": output_file, "subfolder": subfolder, "type": "output"}
        return {"ui": {"images": [preview], "animated": (True,)}, "result": (str(output_path),)}


NODE_CLASS_MAPPINGS = {
    "VisualizerCandidateRegions": VisualizerCandidateRegions,
    "VisualizerRegionMask": VisualizerRegionMask,
    "BeatAwareLocalVisualizer": BeatAwareLocalVisualizer,
    "BeatAwareLocalVisualizerV2": BeatAwareLocalVisualizer,
    "BeatAwareLocalVisualizerV3": BeatAwareLocalVisualizer,
    "VisualizerObjectDetector": VisualizerObjectDetector,
    "VisualizerAnimationTarget": VisualizerAnimationTarget,
    "VisualizerTargetStack": VisualizerTargetStack,
    "GenericBeatAwareLocalVisualizer": GenericBeatAwareLocalVisualizer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VisualizerCandidateRegions": "Suggest Local Visualizer Regions",
    "VisualizerRegionMask": "Local Visualizer Region Mask",
    "BeatAwareLocalVisualizer": "Render Beat-Aware Local Visualizer",
    "BeatAwareLocalVisualizerV2": "Render Beat-Aware Local Visualizer",
    "BeatAwareLocalVisualizerV3": "Render Beat-Aware Local Visualizer + Badging",
    "VisualizerObjectDetector": "Detect Animation Target",
    "VisualizerAnimationTarget": "Configure Animation Target",
    "VisualizerTargetStack": "Add Animation Target",
    "GenericBeatAwareLocalVisualizer": "Render Generic Target Visualizer",
}
