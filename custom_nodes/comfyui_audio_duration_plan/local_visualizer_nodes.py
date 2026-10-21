from __future__ import annotations

import math
import base64
import hashlib
import io
import json
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


def _image_identity(image) -> dict:
    pixels = _image_pixels(image)
    height, width = pixels.shape[:2]
    digest = hashlib.sha256()
    digest.update(f"{width}x{height}:rgb8:".encode("ascii"))
    digest.update(pixels.tobytes())
    return {"sha256": digest.hexdigest(), "width": int(width), "height": int(height)}


def _manifest_path(value: str) -> Path:
    """Resolve an Infra Choir manifest below Comfy's user directory."""
    try:
        import folder_paths

        user_root = Path(folder_paths.get_user_directory())
    except (ImportError, AttributeError):
        user_root = Path(__file__).resolve().parents[2] / "user"
    relative = Path(str(value or "infra_choir/auto_targets.json").replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("manifest_path must be relative to the ComfyUI user directory.")
    destination = (user_root / relative).resolve()
    root = user_root.resolve()
    if root not in destination.parents:
        raise ValueError("manifest_path must remain inside the ComfyUI user directory.")
    return destination


def _mask_png_base64(mask) -> str:
    import numpy as np
    from PIL import Image

    value = mask.detach().to("cpu", dtype=__import__("torch").float32)
    if value.ndim == 3:
        value = value[0]
    pixels = np.clip(value.numpy() * 255.0, 0, 255).round().astype(np.uint8)
    stream = io.BytesIO()
    Image.fromarray(pixels, "L").save(stream, format="PNG", optimize=True)
    return base64.b64encode(stream.getvalue()).decode("ascii")


def _mask_from_png_base64(value: str):
    import numpy as np
    import torch
    from PIL import Image

    try:
        payload = base64.b64decode(str(value), validate=True)
        with Image.open(io.BytesIO(payload)) as opened:
            pixels = np.asarray(opened.convert("L"), dtype=np.float32) / 255.0
    except Exception as exc:
        raise ValueError(f"Invalid mask_png_base64 payload: {exc}") from exc
    return torch.from_numpy(pixels.copy())


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


def _normalize_feature_matrix(values):
    """Normalize each frequency band independently while preserving frame order."""
    import numpy as np

    values = np.asarray(values, dtype=np.float32)
    if values.ndim != 2:
        raise ValueError("Expected a frame-by-band feature matrix.")
    output = np.zeros_like(values)
    for band in range(values.shape[1]):
        output[:, band] = _normalize_feature(values[:, band])
    return output


def _stable_phase(value: str) -> float:
    """Return a deterministic phase without Python's process-randomized hash()."""
    digest = hashlib.sha256(str(value).encode("utf-8")).digest()
    integer = int.from_bytes(digest[:8], "big")
    return (integer / float(2**64)) * math.tau


def _audio_features(audio: dict, fps: int, duration: float):
    """Extract shared deterministic envelopes and compact log-frequency EQ bands."""
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
    upper_frequency = max(90.0, min(12000.0, sample_rate / 2.0))
    band_edges = np.geomspace(45.0, upper_frequency, 25)
    band_bins = [
        (frequencies >= band_edges[index]) & (frequencies < band_edges[index + 1])
        for index in range(len(band_edges) - 1)
    ]
    rms, low, high, onset, spectrum_bands = [], [], [], [], []
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
        spectrum_bands.append([
            float(np.log1p(np.mean(spectrum[bins]))) if np.any(bins) else 0.0
            for bins in band_bins
        ])
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
    return {
        "beat": beat,
        "onset": onset,
        "high": high,
        "slow": slow,
        "energy": energy,
        "spectrum_bands": _normalize_feature_matrix(spectrum_bands),
    }


def _asymmetric_smooth(values, attack_seconds: float, release_seconds: float, fps: float):
    """Apply independent attack/release smoothing to a vector or matrix."""
    import numpy as np

    source = np.asarray(values, dtype=np.float32)
    output = np.empty_like(source)
    state = np.zeros(source.shape[1:], dtype=np.float32)
    attack = math.exp(-1.0 / max(1.0, float(fps) * max(0.001, float(attack_seconds))))
    release = math.exp(-1.0 / max(1.0, float(fps) * max(0.001, float(release_seconds))))
    for index, value in enumerate(source):
        coefficient = np.where(value > state, attack, release)
        state = coefficient * state + (1.0 - coefficient) * value
        output[index] = state
    return output


def _transient_envelope(flux, fps: int, sensitivity: float, release_seconds: float):
    """Turn spectral-flux local maxima into a normalized transient envelope."""
    import numpy as np

    values = _normalize_feature(flux)
    if not values.size:
        return values
    sensitivity = min(1.0, max(0.0, float(sensitivity)))
    threshold = float(np.percentile(values, 72.0 - 34.0 * sensitivity))
    hits = np.zeros_like(values)
    minimum_gap = max(1, round(float(fps) * 0.055))
    last_hit = -minimum_gap
    for index in range(1, len(values) - 1):
        if index - last_hit < minimum_gap:
            continue
        if values[index] >= threshold and values[index] >= values[index - 1] and values[index] > values[index + 1]:
            hits[index] = values[index]
            last_hit = index
    return _asymmetric_smooth(hits, 0.012, release_seconds, fps)


def _audio_cache_key(waveform, sample_rate: int, configuration: dict) -> str:
    import numpy as np

    digest = hashlib.sha256()
    digest.update(str(int(sample_rate)).encode("ascii"))
    digest.update(json.dumps(configuration, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    samples = np.ascontiguousarray(waveform, dtype=np.float32).view(np.uint8)
    chunk = 8 * 1024 * 1024
    for offset in range(0, samples.size, chunk):
        digest.update(samples[offset:offset + chunk])
    return digest.hexdigest()


def _enhanced_audio_features(
    audio: dict,
    fps: int,
    duration: float,
    band_count: int,
    fft_size: int,
    hop_size: int,
    frequency_scale: str,
    minimum_frequency: float,
    maximum_frequency: float,
    dynamic_range_db: float,
    noise_floor_db: float,
    sensitivity: float,
    transient_emphasis: float,
):
    """Compute and persist one frame-aligned STFT analysis for every visual consumer.

    The transient-band and ADSR concepts are adapted from the locally installed
    Apache-2.0 ComfyUI_Fill-Nodes audio nodes. The implementation is deliberately
    streaming/NumPy based so it does not create a full-song IMAGE batch.
    """
    import numpy as np

    waveform = audio["waveform"].detach().to("cpu", dtype=__import__("torch").float32).numpy()
    sample_rate = int(audio["sample_rate"])
    if waveform.ndim == 3:
        waveform = waveform[0]
    if waveform.ndim == 2:
        waveform = waveform.mean(axis=0)
    waveform = np.ascontiguousarray(waveform, dtype=np.float32)
    fft_size = int(fft_size)
    hop_size = int(hop_size)
    band_count = int(band_count)
    if fft_size < 1024 or fft_size & (fft_size - 1):
        raise ValueError("EQ FFT size must be a power of two of at least 1024.")
    if hop_size < 64 or hop_size > fft_size:
        raise ValueError("EQ hop size must be between 64 and the FFT size.")
    nyquist = sample_rate / 2.0
    lower = min(max(1.0, float(minimum_frequency)), nyquist - 1.0)
    upper = min(max(lower + 1.0, float(maximum_frequency)), nyquist)
    configuration = {
        "version": 3, "fps": int(fps), "duration": round(float(duration), 9),
        "bands": band_count, "fft": fft_size, "hop": hop_size,
        "scale": str(frequency_scale), "minimum": lower, "maximum": upper,
        "dynamic_range_db": float(dynamic_range_db), "noise_floor_db": float(noise_floor_db),
        "sensitivity": float(sensitivity), "transient_emphasis": float(transient_emphasis),
    }
    cache_key = _audio_cache_key(waveform, sample_rate, configuration)
    try:
        import folder_paths
        cache_root = Path(folder_paths.get_temp_directory()) / "infra_choir_audio_analysis"
    except (ImportError, AttributeError):
        cache_root = Path(tempfile.gettempdir()) / "infra_choir_audio_analysis"
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_path = cache_root / f"{cache_key}.npz"
    if cache_path.exists():
        try:
            with np.load(cache_path, allow_pickle=False) as stored:
                result = {name: stored[name] for name in stored.files}
            result["cache_status"] = "hit"
            result["cache_key"] = cache_key
            return result
        except (OSError, ValueError, KeyError):
            cache_path.unlink(missing_ok=True)

    frequencies = np.fft.rfftfreq(fft_size, 1.0 / sample_rate)
    first_bin = int(np.searchsorted(frequencies, lower, side="left"))
    final_bin = int(np.searchsorted(frequencies, upper, side="right"))
    available_bins = max(0, final_bin - first_bin)
    if band_count > available_bins:
        raise ValueError(
            f"{band_count} EQ bands require at least {band_count} distinct FFT bins between "
            f"{lower:.0f} and {upper:.0f} Hz; {fft_size}-point FFT provides {available_bins}. "
            "Choose a larger FFT or fewer bands."
        )
    if str(frequency_scale) == "linear":
        edges = np.linspace(lower, upper, band_count + 1)
    else:
        edges = np.geomspace(lower, upper, band_count + 1)
    # Quantize requested edges to strictly increasing FFT-bin boundaries. This
    # preserves the requested scale as far as the finite FFT permits while
    # guaranteeing that every advertised band owns at least one distinct bin.
    boundaries = np.searchsorted(frequencies, edges, side="left").astype(int)
    boundaries[0], boundaries[-1] = first_bin, final_bin
    for index in range(1, band_count):
        lower_bound = boundaries[index - 1] + 1
        upper_bound = final_bin - (band_count - index)
        boundaries[index] = min(upper_bound, max(lower_bound, int(boundaries[index])))
    band_indices = [np.arange(boundaries[index], boundaries[index + 1]) for index in range(band_count)]
    masks = {
        "low": (frequencies >= 30.0) & (frequencies < 180.0),
        "mid": (frequencies >= 180.0) & (frequencies < 2500.0),
        "high": (frequencies >= 2500.0) & (frequencies <= min(16000.0, nyquist)),
    }
    analysis_count = max(1, 1 + math.ceil(max(0, len(waveform) - 1) / hop_size))
    analysis_times = np.arange(analysis_count, dtype=np.float64) * hop_size / sample_rate
    taper = np.hanning(fft_size).astype(np.float32)
    spectra = np.empty((analysis_count, band_count), dtype=np.float32)
    raw = {name: np.zeros(analysis_count, dtype=np.float32) for name in ("rms", "low", "mid", "high", "onset", "kick_flux", "snare_flux", "hihat_flux")}
    previous = None
    half = fft_size // 2
    for index in range(analysis_count):
        center = index * hop_size
        start, end = center - half, center + half
        segment = np.zeros(fft_size, dtype=np.float32)
        source_start, source_end = max(0, start), min(len(waveform), end)
        if source_end > source_start:
            target_start = source_start - start
            segment[target_start:target_start + source_end - source_start] = waveform[source_start:source_end]
        magnitude = np.abs(np.fft.rfft(segment * taper)).astype(np.float32)
        spectra[index] = [float(np.sqrt(np.mean(magnitude[bins] ** 2) + 1e-12)) for bins in band_indices]
        raw["rms"][index] = float(np.sqrt(np.mean(segment * segment) + 1e-12))
        for name, mask in masks.items():
            raw[name][index] = float(np.sqrt(np.mean(magnitude[mask] ** 2) + 1e-12)) if np.any(mask) else 0.0
        if previous is not None:
            delta = np.maximum(magnitude - previous, 0.0)
            raw["onset"][index] = float(np.mean(delta))
            raw["kick_flux"][index] = float(np.mean(delta[masks["low"]])) if np.any(masks["low"]) else 0.0
            raw["snare_flux"][index] = float(np.mean(delta[masks["mid"]])) if np.any(masks["mid"]) else 0.0
            raw["hihat_flux"][index] = float(np.mean(delta[masks["high"]])) if np.any(masks["high"]) else 0.0
        previous = magnitude

    frame_count = max(1, math.ceil(float(duration) * int(fps)))
    frame_times = np.arange(frame_count, dtype=np.float64) / float(fps)
    interpolate = lambda values: np.interp(frame_times, analysis_times, values).astype(np.float32)
    spectra = np.stack([interpolate(spectra[:, band]) for band in range(band_count)], axis=1)
    reference_db = float(np.max(20.0 * np.log10(np.maximum(spectra, 1e-12))))
    spectrum_db = 20.0 * np.log10(np.maximum(spectra, 1e-12)) - reference_db
    floor = max(float(noise_floor_db), -max(12.0, float(dynamic_range_db)))
    spectrum = np.clip((spectrum_db - floor) / max(6.0, -floor), 0.0, 1.0)
    spectrum = np.clip(spectrum * max(0.05, float(sensitivity)), 0.0, 1.0).astype(np.float32)
    features = {name: _normalize_feature(interpolate(values)) for name, values in raw.items()}
    features["energy"] = features.pop("rms")
    features["kick"] = _transient_envelope(features.pop("kick_flux"), fps, sensitivity, 0.18)
    features["snare"] = _transient_envelope(features.pop("snare_flux"), fps, sensitivity, 0.14)
    features["hihat"] = _transient_envelope(features.pop("hihat_flux"), fps, sensitivity, 0.09)
    features["onset"] = np.clip(
        features["onset"] + float(transient_emphasis) * np.maximum.reduce((features["kick"], features["snare"], features["hihat"])),
        0.0, 1.0,
    ).astype(np.float32)
    features["slow"] = _asymmetric_smooth(features["energy"], 1.2, 3.2, fps)
    features["phrase"] = _asymmetric_smooth(0.55 * features["energy"] + 0.25 * features["mid"] + 0.20 * features["low"], 1.8, 4.0, fps)
    features["vocal_energy"] = _normalize_feature(0.70 * features["mid"] + 0.30 * features["high"])
    features["instrument_energy"] = _normalize_feature(0.55 * features["low"] + 0.25 * features["mid"] + 0.20 * features["high"])
    beat_source = np.clip(0.58 * features["kick"] + 0.42 * features["onset"], 0.0, 1.0)
    minimum_lag = max(2, round(fps * 60.0 / 180.0))
    maximum_lag = min(len(beat_source) // 2, max(minimum_lag + 1, round(fps * 60.0 / 60.0)))
    best_lag, confidence = max(1, round(fps * 0.5)), 0.0
    centered = beat_source - float(np.mean(beat_source))
    denominator = float(np.dot(centered, centered)) + 1e-9
    if maximum_lag > minimum_lag:
        correlations = [float(np.dot(centered[:-lag], centered[lag:]) / denominator) for lag in range(minimum_lag, maximum_lag + 1)]
        best_offset = int(np.argmax(correlations))
        best_lag = minimum_lag + best_offset
        confidence = min(1.0, max(0.0, correlations[best_offset]) * 2.5)
    anchor_window = min(len(beat_source), max(best_lag, 1))
    anchor = int(np.argmax(beat_source[:anchor_window])) if anchor_window else 0
    indices = np.arange(frame_count)
    phase = ((indices - anchor) % max(1, best_lag)) / max(1, best_lag)
    features["beat_phase"] = (0.5 + 0.5 * np.cos(math.tau * phase)).astype(np.float32)
    features["beat_confidence"] = np.full(frame_count, confidence, dtype=np.float32)
    features["beat"] = np.clip(beat_source * (0.65 + 0.35 * features["beat_phase"]), 0.0, 1.0).astype(np.float32)
    features["spectrum_bands"] = spectrum
    temporary_path = cache_path.with_suffix(".part.npz")
    np.savez_compressed(temporary_path, **features)
    temporary_path.replace(cache_path)
    features["cache_status"] = "miss"
    features["cache_key"] = cache_key
    return features


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


def _translate_pixels(pixels, offset_x: float, offset_y: float):
    """Translate an RGB crop with subpixel sampling and edge replication."""
    import numpy as np
    from PIL import Image

    if abs(float(offset_x)) < 0.01 and abs(float(offset_y)) < 0.01:
        return pixels
    height, width = pixels.shape[:2]
    padding = max(2, int(math.ceil(max(abs(float(offset_x)), abs(float(offset_y))))) + 2)
    padded = np.pad(
        np.clip(pixels, 0, 255).astype(np.uint8),
        ((padding, padding), (padding, padding), (0, 0)),
        mode="edge",
    )
    translated = Image.fromarray(padded, "RGB").transform(
        (width, height),
        Image.Transform.AFFINE,
        (1.0, 0.0, padding - float(offset_x), 0.0, 1.0, padding - float(offset_y)),
        resample=Image.Resampling.BICUBIC,
    )
    return np.asarray(translated, dtype=np.float32)


def _deform_pixels(pixels, seconds: float, phase: float, amplitude: float, profile: str):
    """Apply a smooth non-rigid mesh deformation for billow or anchored sway."""
    import numpy as np
    from PIL import Image

    strength = max(0.0, float(amplitude))
    if strength < 0.01:
        return pixels
    height, width = pixels.shape[:2]
    padding = max(4, int(math.ceil(strength * 2.4)) + 3)
    padded = np.pad(
        np.clip(pixels, 0, 255).astype(np.uint8),
        ((padding, padding), (padding, padding), (0, 0)),
        mode="edge",
    )
    step_x = max(24, min(96, max(1, width // 10)))
    step_y = max(24, min(96, max(1, height // 8)))
    xs = list(range(0, width, step_x)) + ([width] if width % step_x else [])
    ys = list(range(0, height, step_y)) + ([height] if height % step_y else [])
    if xs[-1] != width:
        xs.append(width)
    if ys[-1] != height:
        ys.append(height)

    def displacement(x, y):
        normalized_x = float(x) / max(1.0, width)
        normalized_y = float(y) / max(1.0, height)
        if profile == "sway":
            freedom = max(0.0, 1.0 - normalized_y) ** 1.45
            horizontal = (
                math.sin(seconds * 1.35 + phase)
                + 0.34 * math.sin(seconds * 2.75 + phase * 1.9 + normalized_y * 3.2)
            )
            vertical = 0.22 * math.cos(seconds * 1.08 + phase * 0.7 + normalized_x * 2.4)
            return strength * freedom * horizontal, strength * freedom * vertical
        horizontal = (
            0.58 * math.sin(normalized_x * 7.1 + normalized_y * 4.3 + seconds * 0.62 + phase)
            + 0.31 * math.cos(normalized_x * 3.7 - normalized_y * 8.2 - seconds * 0.39 + phase * 1.7)
            + 0.18 * math.sin(normalized_x * 13.4 + seconds * 0.21 + phase * 0.4)
        )
        vertical = (
            0.52 * math.cos(normalized_x * 5.2 - normalized_y * 5.9 + seconds * 0.48 + phase * 1.3)
            + 0.29 * math.sin(normalized_x * 9.7 + normalized_y * 3.1 - seconds * 0.33 + phase * 0.6)
        )
        return strength * horizontal, strength * vertical

    offsets = {(x, y): displacement(x, y) for y in ys for x in xs}
    mesh = []
    for y0, y1 in zip(ys, ys[1:]):
        for x0, x1 in zip(xs, xs[1:]):
            dx00, dy00 = offsets[(x0, y0)]
            dx01, dy01 = offsets[(x1, y0)]
            dx10, dy10 = offsets[(x0, y1)]
            dx11, dy11 = offsets[(x1, y1)]
            mesh.append((
                (x0, y0, x1, y1),
                (
                    padding + x0 + dx00, padding + y0 + dy00,
                    padding + x0 + dx10, padding + y1 + dy10,
                    padding + x1 + dx11, padding + y1 + dy11,
                    padding + x1 + dx01, padding + y0 + dy01,
                ),
            ))
    deformed = Image.fromarray(padded, "RGB").transform(
        (width, height), Image.Transform.MESH, mesh, resample=Image.Resampling.BICUBIC,
    )
    return np.asarray(deformed, dtype=np.float32)


def _motion_interior(mask, radius: int):
    """Contract a mask so non-rigid sampling cannot pull protected boundary pixels inward."""
    import numpy as np
    from PIL import Image, ImageFilter

    amount = max(0, int(radius))
    if amount == 0:
        return mask
    size = amount * 2 + 1
    contracted = np.asarray(
        Image.fromarray(np.clip(mask * 255.0, 0, 255).astype(np.uint8), "L").filter(ImageFilter.MinFilter(size=size)),
        dtype=np.float32,
    ) / 255.0
    if np.any(contracted > 0.005):
        return contracted
    return mask


def _procedural_motion_pixels(motion_type: str, height: int, expansion_radius: int = 0) -> float:
    """Bound deformation amplitude independently from mask-support expansion."""
    profile = str(motion_type).casefold()
    scale = max(0.75, float(height) / 720.0)
    pixels = {"billow": 11.0, "sway": 5.0, "drift": 6.0, "still": 0.0}.get(profile, 4.0) * scale
    radius = max(0.0, float(expansion_radius))
    if radius:
        if profile == "billow":
            pixels += min(8.0 * scale, radius * 0.08)
        elif profile in {"sway", "drift"}:
            pixels += min(3.0 * scale, radius * 0.05)
    return pixels


def _phase_correlation_shift(reference, moving, maximum_fraction: float = 0.08):
    """Estimate the translation that aligns moving to reference.

    The estimate intentionally uses a small grayscale proxy. It is only a
    stabilization guard for short generated clips; the final compositor still
    applies generated pixels exclusively inside a verified mask.
    """
    if float(maximum_fraction) <= 0.0:
        return 0.0, 0.0, False

    import numpy as np
    from PIL import Image

    height, width = reference.shape[:2]
    proxy_width = min(256, width)
    proxy_height = max(16, round(height * proxy_width / max(1, width)))

    def proxy(pixels):
        image = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8), "RGB")
        image = image.resize((proxy_width, proxy_height), Image.Resampling.BILINEAR).convert("L")
        values = np.asarray(image, dtype=np.float32)
        values -= float(values.mean())
        return values

    fixed, candidate = proxy(reference), proxy(moving)
    fixed_spectrum = np.fft.fft2(fixed)
    candidate_spectrum = np.fft.fft2(candidate)
    cross = fixed_spectrum * np.conj(candidate_spectrum)
    cross /= np.maximum(np.abs(cross), 1e-8)
    correlation = np.abs(np.fft.ifft2(cross))
    peak_y, peak_x = np.unravel_index(int(np.argmax(correlation)), correlation.shape)
    if peak_x > proxy_width // 2:
        peak_x -= proxy_width
    if peak_y > proxy_height // 2:
        peak_y -= proxy_height
    shift_x = float(peak_x) * width / proxy_width
    shift_y = float(peak_y) * height / proxy_height
    limit_x = max(1.0, width * max(0.0, float(maximum_fraction)))
    limit_y = max(1.0, height * max(0.0, float(maximum_fraction)))
    clipped = abs(shift_x) > limit_x or abs(shift_y) > limit_y
    return float(np.clip(shift_x, -limit_x, limit_x)), float(np.clip(shift_y, -limit_y, limit_y)), clipped


def _prepare_generated_motion(motion_clip, width: int, height: int, base, maximum_fraction: float):
    """Move a bounded short IMAGE batch to CPU, resize, and remove global translation."""
    import numpy as np
    from PIL import Image

    value = motion_clip.detach().to("cpu")
    if value.ndim == 3:
        value = value[None, ...]
    if value.ndim != 4 or value.shape[-1] < 3:
        raise ValueError("Generated motion must be a ComfyUI IMAGE batch.")
    frame_count = int(value.shape[0])
    if frame_count <= 1:
        return (), {"frames": frame_count, "max_shift_px": 0.0, "clipped_shifts": 0}
    if frame_count > 161:
        raise ValueError(
            f"Generated motion has {frame_count} frames; use a reusable short clip of at most 161 frames."
        )
    prepared = []
    max_shift = 0.0
    clipped_count = 0
    for index in range(frame_count):
        pixels = np.clip(value[index, ..., :3].numpy() * 255.0, 0, 255).round().astype(np.uint8)
        if (pixels.shape[1], pixels.shape[0]) != (width, height):
            pixels = np.asarray(
                Image.fromarray(pixels, "RGB").resize((width, height), Image.Resampling.LANCZOS),
                dtype=np.uint8,
            )
        shift_x, shift_y, clipped = _phase_correlation_shift(base, pixels, maximum_fraction)
        max_shift = max(max_shift, abs(shift_x), abs(shift_y))
        clipped_count += int(clipped)
        aligned = _translate_pixels(pixels, shift_x, shift_y)
        prepared.append(np.clip(aligned, 0, 255).astype(np.uint8))
    return tuple(prepared), {
        "frames": frame_count,
        "max_shift_px": round(max_shift, 3),
        "clipped_shifts": clipped_count,
    }


def _motion_source_similarity(reference, candidate) -> float:
    """Estimate whether a generated clip still depicts the selected artwork.

    Wan's first decoded frame need not be pixel-identical to the source, but its
    large-scale luminance structure should remain strongly correlated. This
    inexpensive guard catches accidental reuse of a cached clip from another
    song or illustration before it is composited through plausible-looking
    masks.
    """
    import numpy as np
    from PIL import Image

    def proxy(value):
        pixels = np.clip(value, 0, 255).astype(np.uint8)
        image = Image.fromarray(pixels, "RGB").resize((96, 54), Image.Resampling.BILINEAR).convert("L")
        data = np.asarray(image, dtype=np.float32)
        data -= float(data.mean())
        scale = float(np.sqrt(np.mean(data * data)))
        return data / max(scale, 1e-6)

    fixed = proxy(reference)
    moving = proxy(candidate)
    return float(np.clip(np.mean(fixed * moving), -1.0, 1.0))


_CACHED_MOTION_FILES = {}
_CACHED_MOTION_FILE_ORDER = []


def _resolve_cached_motion_path(value: str) -> Path:
    try:
        import folder_paths

        roots = [
            Path(folder_paths.get_input_directory()),
            Path(folder_paths.get_output_directory()),
            Path(folder_paths.get_temp_directory()),
        ]
    except (ImportError, AttributeError):
        roots = [Path(__file__).resolve().parents[2] / "input"]
    raw = str(value).strip().replace("\\", "/")
    labeled = re.match(r"^(input|output|temp):(.*)$", raw, flags=re.IGNORECASE)
    if labeled:
        root_by_label = dict(zip(("input", "output", "temp"), roots))
        requested = Path(labeled.group(2).lstrip("/"))
        candidates = [root_by_label[labeled.group(1).casefold()] / requested]
    else:
        requested = Path(raw)
        candidates = [requested] if requested.is_absolute() else [root / requested for root in roots]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file() and any(root.resolve() == resolved.parent or root.resolve() in resolved.parents for root in roots):
            return resolved
    raise FileNotFoundError(f"Cached motion clip was not found below a Comfy input/output/temp directory: {value}")


def _cached_motion_clip_choices() -> list[str]:
    """Return stable, root-labelled local video choices for a Comfy combo widget."""
    choices = ["(select a cached motion clip)"]
    try:
        import folder_paths

        roots = (
            ("input", Path(folder_paths.get_input_directory())),
            ("output", Path(folder_paths.get_output_directory())),
            ("temp", Path(folder_paths.get_temp_directory())),
        )
    except (ImportError, AttributeError):
        return choices
    extensions = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
    found = []
    for label, root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.casefold() in extensions:
                found.append(f"{label}:{path.relative_to(root).as_posix()}")
    return choices + sorted(found, key=str.casefold)


def _load_cached_motion_file(
    value: str, width: int, height: int, base, maximum_fraction: float,
    fps: int, maximum_seconds: float,
):
    """Decode a bounded offline clip; no model or diffusion work occurs here."""
    import numpy as np

    path = _resolve_cached_motion_path(value)
    frame_limit = max(2, min(161, round(max(0.25, float(maximum_seconds)) * max(1, int(fps)))))
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size, width, height, int(fps), frame_limit, round(maximum_fraction, 4))
    cached = _CACHED_MOTION_FILES.get(key)
    if cached is not None:
        return cached
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-vf", f"fps={int(fps)},scale={width}:{height}:flags=lanczos",
        "-frames:v", str(frame_limit), "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ]
    run = subprocess.run(command, capture_output=True, check=False)
    if run.returncode:
        raise RuntimeError(f"Could not decode cached motion clip: {run.stderr.decode('utf-8', errors='replace').strip()}")
    frame_bytes = width * height * 3
    count = len(run.stdout) // frame_bytes
    if count < 2:
        raise ValueError("Cached motion clip must decode to at least two frames.")
    prepared, max_shift, clipped_count = [], 0.0, 0
    for index in range(count):
        pixels = np.frombuffer(run.stdout[index * frame_bytes:(index + 1) * frame_bytes], dtype=np.uint8).reshape(height, width, 3)
        shift_x, shift_y, clipped = _phase_correlation_shift(base, pixels, maximum_fraction)
        max_shift = max(max_shift, abs(shift_x), abs(shift_y))
        clipped_count += int(clipped)
        prepared.append(np.clip(_translate_pixels(pixels, shift_x, shift_y), 0, 255).astype(np.uint8))
    source_similarity = _motion_source_similarity(base, prepared[0])
    if source_similarity < 0.45:
        raise ValueError(
            f"Cached motion clip appears to belong to different source artwork "
            f"(first-frame similarity {source_similarity:.3f}; required at least 0.450)."
        )
    result = (tuple(prepared), {
        "frames": count, "max_shift_px": round(max_shift, 3), "clipped_shifts": clipped_count,
        "path": str(path), "offline_cache": True,
        "source_similarity": round(source_similarity, 4),
    })
    _CACHED_MOTION_FILES[key] = result
    _CACHED_MOTION_FILE_ORDER.append(key)
    while len(_CACHED_MOTION_FILE_ORDER) > 2:
        expired = _CACHED_MOTION_FILE_ORDER.pop(0)
        _CACHED_MOTION_FILES.pop(expired, None)
    return result


def _looped_motion_frame(frames, frame_index: int, overlap_frames: int):
    """Loop forward with a bounded tail/head crossfade instead of a hard seam."""
    import numpy as np

    count = len(frames)
    overlap = min(max(0, int(overlap_frames)), max(0, count // 3))
    if not overlap:
        return frames[frame_index % count]
    # The overlap consumes the head and tail portions, so the repeated period is
    # N-overlap frames. Start after the consumed head, play the middle, then
    # blend tail[j] into head[j]. The frame after the final blend is head[overlap],
    # not head[0]; resetting to head[0] caused the visible production jump.
    period = count - overlap
    position = frame_index % period
    middle_count = count - 2 * overlap
    if position < middle_count:
        return frames[position + overlap]
    blend_index = position - middle_count
    amount = (blend_index + 1) / float(overlap + 1)
    tail = frames[count - overlap + blend_index]
    head = frames[blend_index]
    return np.clip(tail.astype(np.float32) * (1.0 - amount) + head.astype(np.float32) * amount, 0, 255)


def _ping_pong_index(frame_index: int, frame_count: int) -> int:
    if frame_count <= 1:
        return 0
    period = (frame_count - 1) * 2
    position = frame_index % period
    return position if position < frame_count else period - position


def _shift_hue_and_saturation(pixels, hue_degrees: float, saturation_delta: float):
    """Apply a small bounded YIQ hue rotation and saturation adjustment."""
    import numpy as np

    rgb = np.clip(pixels, 0, 255).astype(np.float32) / 255.0
    angle = math.radians(float(hue_degrees))
    cosine, sine = math.cos(angle), math.sin(angle)
    yiq = np.empty_like(rgb)
    yiq[..., 0] = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    yiq[..., 1] = 0.596 * rgb[..., 0] - 0.274 * rgb[..., 1] - 0.322 * rgb[..., 2]
    yiq[..., 2] = 0.211 * rgb[..., 0] - 0.523 * rgb[..., 1] + 0.312 * rgb[..., 2]
    chroma_scale = max(0.0, 1.0 + float(saturation_delta))
    i_channel = (yiq[..., 1] * cosine - yiq[..., 2] * sine) * chroma_scale
    q_channel = (yiq[..., 1] * sine + yiq[..., 2] * cosine) * chroma_scale
    output = np.empty_like(rgb)
    output[..., 0] = yiq[..., 0] + 0.956 * i_channel + 0.621 * q_channel
    output[..., 1] = yiq[..., 0] - 0.272 * i_channel - 0.647 * q_channel
    output[..., 2] = yiq[..., 0] - 1.106 * i_channel + 1.703 * q_channel
    return np.clip(output * 255.0, 0, 255)


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


def _emissive_glow_layer(layer: _Layer, radius: float) -> _Layer:
    """Create a visible halo without diluting a small source mask to nothing."""
    import numpy as np
    from PIL import Image, ImageFilter

    if layer.bounds is None or radius <= 0:
        return layer
    source = np.clip(np.asarray(layer.mask, dtype=np.float32), 0.0, 1.0)
    blurred = np.asarray(
        Image.fromarray((source * 255.0).astype(np.uint8), "L").filter(
            ImageFilter.GaussianBlur(radius=float(radius))
        ),
        dtype=np.float32,
    ) / 255.0
    peak = float(blurred.max())
    halo = np.zeros_like(blurred) if peak <= 1e-6 else np.clip(blurred / peak * 0.55, 0.0, 0.55)
    expanded = np.maximum(source, halo)
    selected = np.argwhere(expanded > 0.005)
    if not selected.size:
        return layer
    y0, x0 = selected.min(axis=0)
    y1, x1 = selected.max(axis=0) + 1
    return _Layer(expanded, (int(x0), int(y0), int(x1), int(y1)))


def _dilated_layer(layer: _Layer, radius: float, feather: float = 2.0) -> _Layer:
    """Expand a verified mask without a radius-squared Pillow kernel stall."""
    import numpy as np
    from PIL import Image, ImageFilter

    amount = max(0, int(round(radius)))
    if layer.bounds is None or amount <= 0:
        return layer
    size = amount * 2 + 1
    source = np.clip(np.asarray(layer.mask, dtype=np.float32), 0.0, 1.0)
    try:
        # Pillow's MaxFilter cost becomes prohibitive for atmospheric radii
        # (for example, 28% of 1080p creates a 605x605 kernel). SciPy's
        # separable 1-D filters preserve the same square dilation in O(pixels).
        from scipy.ndimage import gaussian_filter, maximum_filter1d

        pixels = maximum_filter1d(source, size=size, axis=0, mode="constant", cval=0.0)
        pixels = maximum_filter1d(pixels, size=size, axis=1, mode="constant", cval=0.0)
        if feather > 0:
            pixels = gaussian_filter(pixels, sigma=float(feather), mode="constant", cval=0.0)
        pixels = np.clip(pixels, 0.0, 1.0).astype(np.float32, copy=False)
    except ImportError:
        # ComfyUI normally includes SciPy. Keep a bounded Pillow fallback for
        # lean installations instead of recreating the huge blocking kernel.
        scale = min(1.0, 48.0 / amount)
        mask = Image.fromarray((source * 255.0).astype(np.uint8), "L")
        if scale < 1.0:
            reduced_size = (
                max(1, int(round(mask.width * scale))),
                max(1, int(round(mask.height * scale))),
            )
            mask = mask.resize(reduced_size, Image.Resampling.BILINEAR)
        reduced_amount = max(1, int(round(amount * scale)))
        expanded = mask.filter(ImageFilter.MaxFilter(size=reduced_amount * 2 + 1))
        if feather > 0:
            expanded = expanded.filter(ImageFilter.GaussianBlur(radius=max(0.5, float(feather) * scale)))
        if scale < 1.0:
            expanded = expanded.resize((source.shape[1], source.shape[0]), Image.Resampling.BILINEAR)
        pixels = np.asarray(expanded, dtype=np.float32) / 255.0
    selected = np.argwhere(pixels > 0.005)
    if not selected.size:
        return _Layer(pixels, None)
    y0, x0 = selected.min(axis=0)
    y1, x1 = selected.max(axis=0) + 1
    return _Layer(pixels, (int(x0), int(y0), int(x1), int(y1)))


def _protected_expansion_layer(layer: _Layer, radius: float, feather: float, base) -> _Layer:
    """Expand atmosphere through low-detail surroundings while protecting edges."""
    import numpy as np
    from PIL import Image, ImageFilter

    expanded = _dilated_layer(layer, radius, feather)
    if expanded.bounds is None or expanded is layer:
        return expanded
    rgb = np.asarray(base, dtype=np.float32) / 255.0
    luma = rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722
    dx = np.abs(np.diff(luma, axis=1, prepend=luma[:, :1]))
    dy = np.abs(np.diff(luma, axis=0, prepend=luma[:1, :]))
    edge = np.clip((dx + dy) * 6.0, 0.0, 1.0)
    edge = np.asarray(
        Image.fromarray((edge * 255.0).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(radius=max(1.0, feather))),
        dtype=np.float32,
    ) / 255.0
    original = np.asarray(layer.mask, dtype=np.float32)
    ring = np.clip(expanded.mask - original, 0.0, 1.0) * np.clip(1.0 - edge, 0.0, 1.0) ** 2
    protected = np.clip(original + ring, 0.0, 1.0)
    selected = np.argwhere(protected > 0.005)
    if not selected.size:
        return layer
    y0, x0 = selected.min(axis=0)
    y1, x1 = selected.max(axis=0) + 1
    return _Layer(protected, (int(x0), int(y0), int(x1), int(y1)))


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


def _apply_wordmark_sparkle(frame, overlay, seconds: float, strength: float, audio_high: float, phase: float):
    """Apply an occasional traveling white glint clipped to the wordmark alpha."""
    import numpy as np

    amount = max(0.0, float(strength))
    if amount <= 0.0:
        return
    _, alpha, x, y = overlay
    height, width = alpha.shape
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(frame.shape[1], x + width), min(frame.shape[0], y + height)
    if x1 <= x0 or y1 <= y0:
        return
    sx0, sy0 = x0 - x, y0 - y
    sx1, sy1 = sx0 + x1 - x0, sy0 + y1 - y0
    local_alpha = alpha[sy0:sy1, sx0:sx1]

    # One short pass every six seconds keeps the branding alive without
    # becoming a constant scanner. pattern_key offsets the deterministic cycle.
    cycle = (float(seconds) + float(phase)) % 6.0
    if cycle >= 1.15:
        return
    progress = cycle / 1.15
    pulse = math.sin(math.pi * progress) ** 2
    rows = np.arange(sy0, sy1, dtype=np.float32)[:, None]
    columns = np.arange(sx0, sx1, dtype=np.float32)[None, :]
    center_x = -0.08 * width + progress * 1.16 * width
    center_y = height * (0.58 - 0.16 * math.sin(progress * math.pi))
    radius = max(2.0, min(width, height) * 0.055)
    core = np.exp(-((columns - center_x) ** 2 + (rows - center_y) ** 2) / (2.0 * radius * radius))
    horizontal = np.exp(-np.abs(rows - center_y) / max(1.0, radius * 0.20)) * np.exp(
        -np.abs(columns - center_x) / max(1.0, radius * 3.6)
    )
    diagonal = np.exp(-np.abs((rows - center_y) + (columns - center_x)) / max(1.0, radius * 0.24)) * np.exp(
        -(np.abs(rows - center_y) + np.abs(columns - center_x)) / max(1.0, radius * 4.5)
    )
    sparkle = np.clip(core + 0.45 * horizontal + 0.30 * diagonal, 0.0, 1.0)
    sparkle *= local_alpha * pulse * min(1.5, amount) * (0.70 + 0.30 * float(audio_high))
    original = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = np.clip(
        original + (255.0 - original) * sparkle[..., None], 0, 255
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


_GENERATED_TITLE_CARD = "(generate from text)"
_NO_OVERLAY_IMAGE = "(none)"


def _title_card_choices():
    """Expose an upload-capable selector without making an external image mandatory."""
    try:
        import folder_paths

        extensions = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
        input_directory = Path(folder_paths.get_input_directory())
        files = [
            path.relative_to(input_directory).as_posix()
            for path in input_directory.rglob("*")
            if path.is_file() and path.suffix.casefold() in extensions
        ]
    except (ImportError, AttributeError, OSError):
        files = []
    return [_GENERATED_TITLE_CARD, *sorted(files, key=str.casefold)]


def _optional_overlay_choices():
    return [_NO_OVERLAY_IMAGE, *[choice for choice in _title_card_choices() if choice != _GENERATED_TITLE_CARD]]


def _load_title_font(size: int, italic: bool = False):
    """Load a local serif font; no font is bundled or redistributed by this project."""
    from PIL import ImageFont

    windows_name = "georgiai.ttf" if italic else "georgia.ttf"
    dejavu_name = "DejaVuSerif-Italic.ttf" if italic else "DejaVuSerif.ttf"
    candidates = (
        Path("C:/Windows/Fonts") / windows_name,
        Path("/usr/share/fonts/truetype/dejavu") / dejavu_name,
        dejavu_name,
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(str(candidate), int(size))
        except OSError:
            continue
    return ImageFont.load_default(size=max(8, int(size)))


def _wrap_title_lines(draw, text: str, font, maximum_width: int, maximum_lines: int):
    """Wrap words, and split a single overlong token only when necessary."""
    paragraphs = str(text).replace("\r", "").split("\n")
    lines = []
    for paragraph in paragraphs:
        words = paragraph.split() or [""]
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if draw.textlength(candidate, font=font) <= maximum_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            if draw.textlength(word, font=font) <= maximum_width:
                current = word
                continue
            fragment = ""
            for character in word:
                candidate = fragment + character
                if fragment and draw.textlength(candidate, font=font) > maximum_width:
                    lines.append(fragment)
                    fragment = character
                else:
                    fragment = candidate
            current = fragment
        lines.append(current)
    if len(lines) > maximum_lines:
        return None
    return lines


def _fit_title_text(draw, text: str, maximum_width: int, maximum_height: int, maximum_size: int, minimum_size: int, maximum_lines: int, italic: bool = False):
    for size in range(int(maximum_size), int(minimum_size) - 1, -2):
        font = _load_title_font(size, italic=italic)
        lines = _wrap_title_lines(draw, text, font, maximum_width, maximum_lines)
        if lines is None:
            continue
        line_height = max(1, font.getbbox("Ag")[3] - font.getbbox("Ag")[1])
        spacing = max(2, round(size * 0.18))
        total_height = len(lines) * line_height + max(0, len(lines) - 1) * spacing
        if total_height <= maximum_height:
            return font, lines, line_height, spacing, total_height
    font = _load_title_font(minimum_size, italic=italic)
    lines = _wrap_title_lines(draw, text, font, maximum_width, maximum_lines) or [str(text)[:80]]
    line_height = max(1, font.getbbox("Ag")[3] - font.getbbox("Ag")[1])
    spacing = max(2, round(minimum_size * 0.18))
    return font, lines, line_height, spacing, len(lines) * line_height + max(0, len(lines) - 1) * spacing


def _draw_title_text_lines(
    draw, outline_draw, fill_draw, lines, font, left, width, top,
    line_height, spacing, fill, outline, stroke_width, alignment="center",
):
    """Draw inside a fixed horizontal title box; alignment never changes its bounds."""
    y = float(top)
    alignment = str(alignment or "center").casefold()
    if alignment not in {"left", "center", "right"}:
        alignment = "center"
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
        text_width = box[2] - box[0]
        if alignment == "left":
            x = float(left) - box[0]
        elif alignment == "right":
            x = float(left + width) - text_width - box[0]
        else:
            x = float(left + width / 2.0) - text_width / 2.0 - box[0]
        draw.text((x, y), line, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=outline)
        outline_draw.text((x, y), line, font=font, fill=255, stroke_width=stroke_width, stroke_fill=255)
        fill_draw.text((x, y), line, font=font, fill=255)
        y += line_height + spacing


def _render_generated_title_card(
    base, band_name: str, song_title: str, placement: str,
    reserved_bottom: int = 0, source_visibility: float = 0.20,
    text_alignment: str = "center",
):
    """Render deterministic title text over a subdued version of the source artwork."""
    import numpy as np
    from PIL import Image, ImageDraw

    source = np.clip(base, 0, 255).astype(np.float32)
    height, width = source.shape[:2]
    luminance = source[..., 0] * 0.2126 + source[..., 1] * 0.7152 + source[..., 2] * 0.0722
    muted = source * 0.30 + luminance[..., None] * 0.70
    visibility = min(0.50, max(0.05, float(source_visibility)))
    card = Image.fromarray(np.clip(muted * visibility, 0, 255).astype(np.uint8), "RGB")
    draw = ImageDraw.Draw(card)
    outline_image = Image.new("L", (width, height), 0)
    fill_image = Image.new("L", (width, height), 0)
    outline_draw = ImageDraw.Draw(outline_image)
    fill_draw = ImageDraw.Draw(fill_image)
    maximum_width = round(width * 0.86)
    available_height = max(round(height * 0.42), height - reserved_bottom - round(height * 0.18))
    band = (str(band_name).strip() or "Infra Choir").upper()
    title = (str(song_title).strip() or "Untitled").upper()
    band_fit = _fit_title_text(draw, band, maximum_width, round(height * 0.28), round(height * 0.23), round(height * 0.050), 2)
    title_fit = _fit_title_text(draw, title, maximum_width, round(height * 0.22), round(height * 0.10), round(height * 0.032), 3)
    band_font, band_lines, band_height, band_spacing, band_total = band_fit
    title_font, title_lines, title_height, title_spacing, title_total = title_fit
    gap = max(round(height * 0.045), round(band_height * 0.50))
    total_height = band_total + gap + title_total
    center_fraction = {"upper_center": 0.42, "center": 0.50, "lower_center": 0.58}.get(str(placement), 0.50)
    center_y = min(height - reserved_bottom - total_height / 2.0 - height * 0.04, height * center_fraction)
    center_y = max(total_height / 2.0 + height * 0.04, center_y)
    top = center_y - total_height / 2.0
    stroke_width = max(1, round(height / 540.0))
    fill = (104, 12, 25)
    outline = (232, 230, 224)
    title_left = (width - maximum_width) / 2.0
    _draw_title_text_lines(
        draw, outline_draw, fill_draw, band_lines, band_font, title_left, maximum_width,
        top, band_height, band_spacing, fill, outline, stroke_width, text_alignment,
    )
    _draw_title_text_lines(
        draw, outline_draw, fill_draw, title_lines, title_font, title_left, maximum_width,
        top + band_total + gap, title_height, title_spacing, fill, outline, stroke_width, text_alignment,
    )
    outline_pixels = np.asarray(outline_image, dtype=np.float32) / 255.0
    fill_pixels = np.asarray(fill_image, dtype=np.float32) / 255.0
    outline_mask = np.clip(outline_pixels - fill_pixels, 0.0, 1.0)
    return (
        np.asarray(card, dtype=np.uint8), outline_mask,
        f"generated over faded source ({visibility:.0%} visibility), {text_alignment}-aligned inside fixed title bounds, "
        f"with {band_font.getname()[0]} / {title_font.getname()[0]}",
    )


def _render_generated_wordmark(width: int, height: int, band_name: str, song_title: str, target_width: int, opacity: float, margin: int):
    """Render the band and title as a persistent transparent upper-left wordmark."""
    import numpy as np
    from PIL import Image, ImageDraw

    canvas_width = max(120, min(width - max(0, margin), int(target_width)))
    canvas_height = max(64, min(round(height * 0.30), round(canvas_width * 0.48)))
    card = Image.new("RGB", (canvas_width, canvas_height), (0, 0, 0))
    alpha_image = Image.new("L", (canvas_width, canvas_height), 0)
    outline_image = Image.new("L", (canvas_width, canvas_height), 0)
    fill_image = Image.new("L", (canvas_width, canvas_height), 0)
    draw = ImageDraw.Draw(card)
    alpha_draw = ImageDraw.Draw(alpha_image)
    outline_draw = ImageDraw.Draw(outline_image)
    fill_draw = ImageDraw.Draw(fill_image)
    maximum_width = max(40, canvas_width - round(canvas_width * 0.04))
    band = (str(band_name).strip() or "Infra Choir").upper()
    title = (str(song_title).strip() or "Untitled").upper()
    band_fit = _fit_title_text(draw, band, maximum_width, round(canvas_height * 0.48), round(canvas_height * 0.34), max(12, round(canvas_height * 0.13)), 2)
    title_fit = _fit_title_text(draw, title, maximum_width, round(canvas_height * 0.34), round(canvas_height * 0.18), max(9, round(canvas_height * 0.09)), 3, italic=True)
    band_font, band_lines, band_height, band_spacing, band_total = band_fit
    title_font, title_lines, title_height, title_spacing, title_total = title_fit
    gap = max(3, round(canvas_height * 0.035))
    total_height = band_total + gap + title_total
    top = max(1, round((canvas_height - total_height) * 0.18))
    stroke_width = max(1, round(height / 720.0))
    fill = (112, 13, 29)
    outline = (238, 236, 230)

    def draw_left(lines, font, y, line_height, spacing):
        for line in lines:
            x = max(stroke_width + 1, round(canvas_width * 0.02))
            draw.text((x, y), line, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=outline)
            alpha_draw.text((x, y), line, font=font, fill=255, stroke_width=stroke_width, stroke_fill=255)
            outline_draw.text((x, y), line, font=font, fill=255, stroke_width=stroke_width, stroke_fill=255)
            fill_draw.text((x, y), line, font=font, fill=255)
            y += line_height + spacing
        return y

    next_y = draw_left(band_lines, band_font, top, band_height, band_spacing)
    draw_left(title_lines, title_font, next_y + gap, title_height, title_spacing)
    alpha = np.asarray(alpha_image, dtype=np.float32) / 255.0
    outline_mask = np.clip(
        np.asarray(outline_image, dtype=np.float32) / 255.0 - np.asarray(fill_image, dtype=np.float32) / 255.0,
        0.0, 1.0,
    )
    overlay = (np.asarray(card, dtype=np.float32), np.clip(alpha * float(opacity), 0.0, 1.0), int(margin), int(margin))
    full_outline = np.zeros((height, width), dtype=np.float32)
    y1 = min(height, margin + canvas_height)
    x1 = min(width, margin + canvas_width)
    if y1 > margin and x1 > margin:
        full_outline[margin:y1, margin:x1] = outline_mask[:y1 - margin, :x1 - margin]
    return overlay, full_outline, f"generated from band/song text with {band_font.getname()[0]} / {title_font.getname()[0]}"


def _load_external_title_card(selection: str, width: int, height: int):
    """Load an optional input image and conservatively detect a pale text outline."""
    import numpy as np
    import folder_paths
    from PIL import Image, ImageOps

    path = folder_paths.get_annotated_filepath(selection)
    with Image.open(path) as opened:
        rgba = ImageOps.exif_transpose(opened).convert("RGBA")
    contained = ImageOps.contain(rgba, (width, height), Image.Resampling.LANCZOS)
    card = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    card.alpha_composite(contained, ((width - contained.width) // 2, (height - contained.height) // 2))
    rgb = np.asarray(card.convert("RGB"), dtype=np.uint8)
    maximum = rgb.max(axis=2)
    minimum = rgb.min(axis=2)
    luminance = rgb.astype(np.float32).mean(axis=2)
    outline_mask = ((luminance >= 185.0) & ((maximum - minimum) <= 52)).astype(np.float32)
    coverage = float(outline_mask.mean())
    dark_background = float((luminance <= 28.0).mean())
    if dark_background < 0.45:
        return rgb, None, f"external image selected; sparkle skipped because the image lacks a title-card-like dark field ({dark_background:.1%} dark coverage)"
    if coverage < 0.00015:
        return rgb, None, f"external image selected; sparkle skipped because no reliable pale outline was detected ({coverage:.4%} coverage)"
    if coverage > 0.12:
        return rgb, None, f"external image selected; sparkle skipped because pale regions were too broad for reliable outline detection ({coverage:.2%} coverage)"
    return rgb, outline_mask, f"external image selected; pale outline detected ({coverage:.3%} coverage)"


def _load_overlay_selection(selection: str, target_width: int, opacity: float, x: int, y: int):
    """Load a selected input image as a transparency-aware stationary overlay."""
    import folder_paths
    import numpy as np
    from PIL import Image, ImageOps

    path = folder_paths.get_annotated_filepath(selection)
    with Image.open(path) as opened:
        rgba = ImageOps.exif_transpose(opened).convert("RGBA")
    target_height = max(1, round(rgba.height * target_width / max(1, rgba.width)))
    rgba = rgba.resize((int(target_width), target_height), Image.Resampling.LANCZOS)
    pixels = np.asarray(rgba, dtype=np.float32)
    return pixels[..., :3], np.clip(pixels[..., 3] / 255.0 * float(opacity), 0.0, 1.0), int(x), int(y)


def _title_card_alpha(seconds: float, start: float, duration: float, fade: float) -> float:
    local = float(seconds) - max(0.0, float(start))
    length = max(0.0, float(duration))
    if local < 0.0 or local >= length or length <= 0.0:
        return 0.0
    transition = min(max(0.0, float(fade)), length * 0.5)
    if transition <= 1e-6:
        return 1.0
    return min(1.0, local / transition, (length - local) / transition)


def _smooth_spectrum_bands(values, smoothing: float):
    import numpy as np

    values = np.asarray(values, dtype=np.float32)
    result = np.empty_like(values)
    state = np.zeros(values.shape[1], dtype=np.float32)
    coefficient = min(0.98, max(0.0, float(smoothing)))
    for index, row in enumerate(values):
        state = coefficient * state + (1.0 - coefficient) * row
        result[index] = state
    return result


def _parse_overlay_color(value: str):
    text = str(value).strip().lstrip("#")
    if len(text) == 3:
        text = "".join(character * 2 for character in text)
    if len(text) == 6 and all(character in "0123456789abcdefABCDEF" for character in text):
        return tuple(int(text[index:index + 2], 16) for index in (0, 2, 4))
    raise ValueError("EQ color must be a hexadecimal RGB value such as #8E1325.")


def _apply_eq_overlay(frame, band_values, mode: str, height_percent: float, opacity: float, color):
    """Composite a restrained bottom-only spectrum treatment."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    frame_height, frame_width = frame.shape[:2]
    region_height = max(8, round(frame_height * min(18.0, max(4.0, float(height_percent))) / 100.0))
    baseline = region_height - max(2, round(region_height * 0.08))
    count = max(24, min(56, round(frame_width / 46)))
    samples = np.interp(np.linspace(0, len(band_values) - 1, count), np.arange(len(band_values)), band_values)
    mask = Image.new("L", (frame_width, region_height), 0)
    draw = ImageDraw.Draw(mask)
    if mode == "continuous_waveform":
        points = []
        for index, value in enumerate(samples):
            x = round(index * (frame_width - 1) / max(1, count - 1))
            y = baseline - round((0.12 + 0.76 * float(value)) * region_height)
            points.append((x, y))
        draw.polygon([(0, baseline), *points, (frame_width - 1, baseline)], fill=68)
        draw.line(points, fill=220, width=max(1, round(frame_height / 540.0)), joint="curve")
    else:
        slot = frame_width / count
        gap = max(1, round(slot * 0.30))
        for index, value in enumerate(samples):
            x0 = round(index * slot + gap / 2)
            x1 = max(x0 + 1, round((index + 1) * slot - gap / 2))
            bar_height = round((0.08 + 0.84 * float(value)) * region_height)
            draw.rounded_rectangle((x0, baseline - bar_height, x1, baseline), radius=max(1, gap // 3), fill=205)
    glow = mask.filter(ImageFilter.GaussianBlur(radius=max(1.0, frame_height / 420.0)))
    core = np.asarray(mask, dtype=np.float32) / 255.0
    glow_pixels = np.asarray(glow, dtype=np.float32) / 255.0
    vertical_fade = np.linspace(0.25, 1.0, region_height, dtype=np.float32)[:, None]
    alpha = np.clip((core + 0.34 * glow_pixels) * vertical_fade * min(0.85, max(0.0, float(opacity))), 0.0, 1.0)
    y0 = frame_height - region_height
    original = frame[y0:].astype(np.float32)
    overlay = np.empty_like(original)
    overlay[:] = np.asarray(color, dtype=np.float32)
    frame[y0:] = np.clip(original * (1.0 - alpha[..., None]) + overlay * alpha[..., None], 0, 255).astype(np.uint8)


def _shape_audio_response(values, fps: int, settings: dict):
    """Shape a shared driver into a target-local ADSHR response."""
    import numpy as np

    source = np.asarray(values, dtype=np.float32)
    delay = round(float(settings.get("group_delay_ms", 0.0)) * fps / 1000.0)
    if delay:
        shifted = np.zeros_like(source)
        if delay > 0:
            shifted[delay:] = source[:-delay]
        else:
            shifted[:delay] = source[-delay:]
        source = shifted
    subdivision = max(1, int(settings.get("rhythmic_subdivision", 1)))
    accent = max(0.0, float(settings.get("accent_weight", 0.0)))
    if subdivision > 1 and accent > 0.0:
        phase = np.arange(len(source), dtype=np.float32) * subdivision / max(1.0, float(fps))
        source = np.clip(source * (1.0 + accent * (0.5 + 0.5 * np.cos(math.tau * phase))), 0.0, 1.0)
    source = np.clip(source * max(0.0, float(settings.get("response_sensitivity", 1.0))), 0.0, 1.0)
    curve = max(0.1, float(settings.get("response_curve", 1.0)))
    source = np.power(source, curve)
    attack_frames = max(1, round(float(settings.get("response_attack_ms", 40.0)) * fps / 1000.0))
    decay_frames = max(1, round(float(settings.get("response_decay_ms", 180.0)) * fps / 1000.0))
    hold_frames = max(0, round(float(settings.get("response_hold_ms", 0.0)) * fps / 1000.0))
    release_frames = max(1, round(float(settings.get("response_release_ms", 280.0)) * fps / 1000.0))
    sustain = min(1.0, max(0.0, float(settings.get("response_sustain", 0.0))))
    output = np.empty_like(source)
    state = 0.0
    peak = 0.0
    hold = 0
    for index, target in enumerate(source):
        target = float(target)
        if target > state:
            state += (target - state) / attack_frames
            peak = max(peak, state)
            hold = hold_frames
        elif hold > 0:
            hold -= 1
        elif state > peak * sustain:
            state += (max(target, peak * sustain) - state) / decay_frames
        else:
            state += (target - state) / release_frames
            peak = max(target, peak * (1.0 - 1.0 / release_frames))
        output[index] = state
    smoothing = min(0.98, max(0.0, float(settings.get("response_smoothing", 0.0))))
    if smoothing:
        state = 0.0
        for index, value in enumerate(output):
            state = smoothing * state + (1.0 - smoothing) * float(value)
            output[index] = state
    lower = min(1.0, max(0.0, float(settings.get("response_min", 0.0))))
    upper = min(1.0, max(lower, float(settings.get("response_max", 1.0))))
    gain = max(0.0, float(settings.get("group_gain", 1.0)))
    return np.clip((lower + (upper - lower) * output) * gain, 0.0, 1.0)


def _lighting_luminance_amount(maximum_change: float, reactive: float, autonomous: float, enhanced: bool) -> float:
    """Map a light envelope to a visible, bounded luminance change.

    The production renderer retains its original conservative transfer. The
    enhanced renderer interprets ``maximum_change`` as a real perceptual cap
    instead of attenuating the already shaped envelope by another factor of
    0.18. A small floor keeps the emitting source present while the shaped
    attack/release still carries the musical movement.
    """
    maximum = max(0.0, float(maximum_change))
    activity = max(0.0, float(reactive) + 0.45 * float(autonomous))
    if not enhanced:
        return min(maximum, activity * 0.18)
    # Turn the shaped envelope into an actual dark-to-bright excursion. A
    # linear transfer spent most jazz material in a narrow middle band, and a
    # soft manual mask reduced that to roughly one decoded luma level. This
    # smooth gate keeps quiet passages close to the source and lets accents use
    # the user-selected cap without introducing discontinuous flashes.
    normalized = min(1.0, max(0.0, (activity - 0.04) / 0.55))
    pulse = normalized * normalized * (3.0 - 2.0 * normalized)
    return min(maximum, maximum * pulse)


def _lighting_glow_amount(glow_strength: float, audio_drive: float, autonomous: float, enhanced: bool) -> float:
    """Return a bounded source-glow amount before the spatial mask blend."""
    strength = max(0.0, float(glow_strength))
    if not enhanced:
        return min(0.20, strength * (max(0.0, float(audio_drive)) + 0.20 * max(0.0, float(autonomous))) * 0.16)
    activity = min(1.0, max(0.0, float(audio_drive)) + 0.20 * max(0.0, float(autonomous)))
    return min(0.24, strength * (0.14 + 0.55 * activity))


def _non_geometric_atmospheric_billow(
    pixels, alpha, rows, columns, seconds: float, phase: float, motion_amount: float,
    effect_strength: float = 1.0,
):
    """Transport existing smoke texture without painting a synthetic haze veil.

    This is the safe procedural fallback for a still image. It moves the
    image's broad and fine atmospheric structure relative to itself, so the
    result reads as rolling wisps rather than a white opacity pulse. The
    average colour is intentionally stable; a Wan/cached clip remains the
    higher-fidelity route when genuinely new smoke detail is required.
    """
    import numpy as np
    from PIL import Image, ImageFilter

    source = np.asarray(pixels, dtype=np.float32)
    coverage = np.clip(np.asarray(alpha, dtype=np.float32), 0.0, 1.0)
    # The caller performs the final soft-mask composite. Use only binary support
    # here so soft values are not multiplied twice (alpha squared), which made
    # manually boxed smoke nearly static after video encoding.
    support = (coverage > (1.0 / 255.0)).astype(np.float32)
    neutral = np.mean(source, axis=2, keepdims=True)
    luma = neutral / 255.0
    chroma = (np.max(source, axis=2, keepdims=True) - np.min(source, axis=2, keepdims=True)) / 255.0
    smoke_likelihood = np.clip((luma - 0.10) / 0.18, 0.0, 1.0) * np.clip(1.0 - chroma / 0.35, 0.0, 1.0)
    height, width = source.shape[:2]
    fine_radius = max(1.5, min(7.0, min(height, width) * 0.018))
    broad_radius = max(fine_radius * 2.5, min(22.0, min(height, width) * 0.055))

    image = Image.fromarray(np.clip(source, 0, 255).astype(np.uint8), "RGB")
    fine_base = np.asarray(image.filter(ImageFilter.GaussianBlur(radius=fine_radius)), dtype=np.float32)
    broad_base = np.asarray(image.filter(ImageFilter.GaussianBlur(radius=broad_radius)), dtype=np.float32)
    fine_texture = source - fine_base
    broad_texture = fine_base - broad_base

    amplitude = max(1.5, min(28.0, float(motion_amount)))

    def advect(texture, time_scale: float, local_phase: float, local_amplitude: float):
        encoded = np.clip(texture + 128.0, 0, 255)
        moved = _deform_pixels(
            encoded, seconds * time_scale, local_phase, local_amplitude, "billow",
        ) - 128.0
        # A slow oscillating lift prevents a static wobble while remaining
        # seamless enough for short-loop reuse.
        lift = -0.34 * local_amplitude * math.sin(seconds * 0.46 + local_phase)
        curl = 0.18 * local_amplitude * math.sin(seconds * 0.31 + local_phase * 1.9)
        return _translate_pixels(moved + 128.0, curl, lift) - 128.0

    moved_fine = advect(fine_texture, 1.0, phase, amplitude)
    moved_broad = advect(broad_texture, 0.64, phase * 1.37 + 0.8, amplitude * 1.35)
    transported = 1.20 * (moved_fine - fine_texture) + 0.90 * (moved_broad - broad_texture)

    strength = min(1.35, (0.18 + 0.34 * min(1.0, amplitude / 18.0)) * max(0.0, float(effect_strength)))
    # The reviewed mask is authoritative, but the neutral/luminous preference
    # reduces accidental motion on saturated foreground details inside a loose
    # box. The final renderer applies the soft mask exactly once.
    texture_gate = support * (0.30 + 0.70 * smoke_likelihood)
    return np.clip(source + transported * texture_gate * strength, 0, 255)


def _spectrum_peak_envelope(values, fps: int, hold_seconds: float, decay_per_second: float):
    import numpy as np

    values = np.asarray(values, dtype=np.float32)
    peaks = np.empty_like(values)
    state = np.zeros(values.shape[1], dtype=np.float32)
    holds = np.zeros(values.shape[1], dtype=np.int32)
    hold_frames = max(0, round(float(hold_seconds) * fps))
    decay = max(0.0, float(decay_per_second)) / max(1.0, float(fps))
    for index, row in enumerate(values):
        rising = row >= state
        state = np.where(rising, row, state)
        holds = np.where(rising, hold_frames, np.maximum(holds - 1, 0))
        state = np.where(holds > 0, state, np.maximum(row, state - decay))
        peaks[index] = state
    return peaks


def _section_override_curve(value: str, frame_count: int, fps: int):
    """Parse optional [{start,end,gain}] song-section overrides."""
    import numpy as np

    curve = np.ones(frame_count, dtype=np.float32)
    text = str(value or "").strip()
    if not text or text in {"[]", "{}"}:
        return curve, "none"
    try:
        entries = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"section_override_json must be valid JSON: {exc}") from exc
    if not isinstance(entries, list):
        raise ValueError("section_override_json must be a list of {start,end,gain} objects.")
    applied = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Every section override must be an object.")
        start = max(0, round(float(entry.get("start", 0.0)) * fps))
        end = min(frame_count, round(float(entry.get("end", frame_count / fps)) * fps))
        gain = min(2.0, max(0.0, float(entry.get("gain", 1.0))))
        if end > start:
            curve[start:end] *= gain
            applied += 1
    return np.clip(curve, 0.0, 2.0), f"{applied} override(s)"


def _apply_high_resolution_eq(
    frame, band_values, peak_values, mode: str, height_percent: float,
    opacity: float, color, secondary_color=(224, 188, 166), margin_percent: float = 2.0,
    density_mode: str = "auto",
):
    """Draw genuine cached spectrum values, aggregating only when pixels demand it."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    frame_height, frame_width = frame.shape[:2]
    region_height = max(8, round(frame_height * min(24.0, max(3.0, float(height_percent))) / 100.0))
    margin = max(0, round(frame_width * min(20.0, max(0.0, float(margin_percent))) / 100.0))
    available = max(2, frame_width - margin * 2)
    values = np.asarray(band_values, dtype=np.float32)
    peaks = np.asarray(peak_values, dtype=np.float32) if peak_values is not None else None
    requested_count = len(values)
    density = str(density_mode or "auto").casefold()
    if density not in {"auto", "peak", "rms", "mean"}:
        density = "auto"
    # More bands than output columns cannot be represented independently. Reduce
    # contiguous, genuinely computed bins into pixel-density buckets; never
    # synthesize extra bins by interpolating a lower-resolution analysis.
    maximum_columns = max(2, available)
    if requested_count > maximum_columns:
        boundaries = np.linspace(0, requested_count, maximum_columns + 1).astype(int)
        method = "peak" if density == "auto" and "bar" in mode else "rms" if density == "auto" else density
        reducer = {
            "peak": lambda chunk: float(np.max(chunk)),
            "mean": lambda chunk: float(np.mean(chunk)),
            "rms": lambda chunk: float(np.sqrt(np.mean(chunk * chunk))),
        }[method]
        values = np.asarray([reducer(values[boundaries[i]:boundaries[i + 1]]) for i in range(maximum_columns)], dtype=np.float32)
        if peaks is not None:
            peaks = np.asarray([float(np.max(peaks[boundaries[i]:boundaries[i + 1]])) for i in range(maximum_columns)], dtype=np.float32)
    count = len(values)
    if count < 2:
        return
    baseline = region_height - max(2, round(region_height * 0.07))
    mask = Image.new("L", (frame_width, region_height), 0)
    peak_mask = Image.new("L", (frame_width, region_height), 0)
    draw = ImageDraw.Draw(mask)
    peak_draw = ImageDraw.Draw(peak_mask)
    line_width = max(1, round(frame_width / 1920.0))
    points = [
        (margin + round(index * (available - 1) / max(1, count - 1)), baseline - round((0.03 + 0.92 * float(value)) * region_height))
        for index, value in enumerate(values)
    ]
    if mode in {"spectrum_line", "filled_spectrum"}:
        if mode == "filled_spectrum":
            draw.polygon([(margin, baseline), *points, (margin + available - 1, baseline)], fill=82)
        draw.line(points, fill=225, width=line_width, joint="curve")
    elif mode == "mirrored_spectrum":
        center = baseline - region_height // 2
        for index, value in enumerate(values):
            x = margin + round(index * (available - 1) / max(1, count - 1))
            extent = round(float(value) * region_height * 0.43)
            draw.line((x, center - extent, x, center + extent), fill=190, width=max(1, round(available / count * 0.58)))
    else:
        slot = available / count
        bar_width = max(1, round(slot * 0.68))
        for index, value in enumerate(values):
            center_x = margin + (index + 0.5) * slot
            x0 = round(center_x - bar_width / 2)
            x1 = max(x0, round(center_x + bar_width / 2))
            bar_height = round((0.025 + 0.94 * float(value)) * region_height)
            draw.rectangle((x0, baseline - bar_height, x1, baseline), fill=202)
    if peaks is not None:
        for index, value in enumerate(peaks):
            x = margin + round(index * (available - 1) / max(1, count - 1))
            y = baseline - round((0.03 + 0.92 * float(value)) * region_height)
            peak_draw.line((x, y, x + max(1, round(available / count * 0.55)), y), fill=210, width=line_width)
    glow = mask.filter(ImageFilter.GaussianBlur(radius=max(0.8, frame_height / 620.0)))
    core = np.asarray(mask, dtype=np.float32) / 255.0
    glow_pixels = np.asarray(glow, dtype=np.float32) / 255.0
    peak_pixels = np.asarray(peak_mask, dtype=np.float32) / 255.0
    vertical_fade = np.linspace(0.18, 1.0, region_height, dtype=np.float32)[:, None]
    alpha = np.clip((core + 0.24 * glow_pixels) * vertical_fade * min(0.85, max(0.0, float(opacity))), 0.0, 1.0)
    peak_alpha = np.clip(peak_pixels * min(0.70, max(0.0, float(opacity))) * 0.62, 0.0, 1.0)
    y0 = frame_height - region_height
    original = frame[y0:].astype(np.float32)
    overlay = np.empty_like(original)
    overlay[:] = np.asarray(color, dtype=np.float32)
    composed = original * (1.0 - alpha[..., None]) + overlay * alpha[..., None]
    accent = np.empty_like(original)
    accent[:] = np.asarray(secondary_color, dtype=np.float32)
    frame[y0:] = np.clip(composed * (1.0 - peak_alpha[..., None]) + accent * peak_alpha[..., None], 0, 255).astype(np.uint8)


def _masked_edge_alpha(mask, radius: float):
    """Create a bounded soft edge from an already approved target mask."""
    import numpy as np
    from PIL import Image, ImageFilter

    values = np.asarray(mask, dtype=np.float32)
    dy, dx = np.gradient(values)
    edge = np.clip(np.sqrt(dx * dx + dy * dy) * 3.0, 0.0, 1.0)
    image = Image.fromarray(np.clip(edge * 255.0, 0, 255).astype(np.uint8), "L")
    if float(radius) > 0.0:
        image = image.filter(ImageFilter.GaussianBlur(radius=max(0.5, float(radius))))
    return np.asarray(image, dtype=np.float32) / 255.0


def _apply_title_outline_sparkle(frame, outline_mask, seconds: float, strength: float, audio_response: float, pattern_key: int, title_alpha: float):
    """Brighten sparse points strictly inside the rendered or detected outline mask."""
    import numpy as np

    if outline_mask is None or float(strength) <= 0.0 or title_alpha <= 0.0:
        return
    coordinates = np.argwhere(outline_mask > 0.18)
    if len(coordinates) < 8:
        return
    cycle_length = 2.6
    cycle_index = math.floor(float(seconds) / cycle_length)
    local = float(seconds) - cycle_index * cycle_length
    active_length = 0.24
    if local >= active_length:
        return
    pulse = math.sin(math.pi * local / active_length) ** 2
    point_index = int((cycle_index * 104729 + int(pattern_key) * 8191) % len(coordinates))
    center_y, center_x = coordinates[point_index]
    radius = max(2, round(frame.shape[0] / 360.0))
    y0, y1 = max(0, center_y - radius * 2), min(frame.shape[0], center_y + radius * 2 + 1)
    x0, x1 = max(0, center_x - radius * 2), min(frame.shape[1], center_x + radius * 2 + 1)
    rows, columns = np.ogrid[y0:y1, x0:x1]
    glint = np.exp(-((columns - center_x) ** 2 + (rows - center_y) ** 2) / (2.0 * radius * radius))
    local_outline = outline_mask[y0:y1, x0:x1]
    glint *= np.where(local_outline > 0.18, local_outline, 0.0)
    amount = np.clip(glint * pulse * float(strength) * (0.72 + 0.28 * float(audio_response)) * title_alpha, 0.0, 1.0)
    original = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = np.clip(original + (255.0 - original) * amount[..., None], 0, 255).astype(np.uint8)


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
    if any(word in value for word in ("candle", "flame", "fire", "lamp", "warm", "sun")):
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


class VisualizerSemanticObjectDetector:
    _result_cache = {}
    _result_cache_order = []
    _result_cache_limit = 6
    _semantic_model_id = "CIDAS/clipseg-rd64-refined"
    _semantic_model = None
    _semantic_processor = None
    _semantic_model_location = None

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
                "detection_provider": (["semantic_or_heuristic", "semantic_only", "heuristic"],),
            }
        }

    RETURN_TYPES = ("MASK", "IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("detected_mask", "verification_preview", "suggested_regions", "detector_report")
    FUNCTION = "detect"
    CATEGORY = "audio/local visualizer/targets"
    DESCRIPTION = "Find a text-described target with optional local CLIPSeg semantics and produce an inspectable mask."

    @classmethod
    def _semantic_model_dir(cls) -> Path:
        try:
            import folder_paths

            models_dir = Path(folder_paths.models_dir)
        except (ImportError, AttributeError):
            models_dir = Path(__file__).resolve().parents[2] / "models"
        return models_dir / "detection" / "clipseg-rd64-refined"

    @classmethod
    def _semantic_assets_available(cls) -> bool:
        model_dir = cls._semantic_model_dir()
        return (
            (model_dir / "config.json").is_file()
            and (model_dir / "preprocessor_config.json").is_file()
            and ((model_dir / "model.safetensors").is_file() or (model_dir / "pytorch_model.bin").is_file())
        )

    @classmethod
    def _load_semantic_model(cls):
        model_dir = cls._semantic_model_dir()
        if not cls._semantic_assets_available():
            raise FileNotFoundError(
                f"CLIPSeg model assets are not installed at {model_dir}. "
                "Run scripts/install_visualizer_semantic_assets.py with the ComfyUI Python environment."
            )
        location = str(model_dir.resolve())
        if cls._semantic_model is not None and cls._semantic_model_location == location:
            return cls._semantic_processor, cls._semantic_model
        try:
            from transformers import CLIPSegForImageSegmentation, CLIPSegProcessor
        except ImportError as exc:
            raise RuntimeError(
                "The ComfyUI Python environment needs Transformers with CLIPSeg support."
            ) from exc
        processor = CLIPSegProcessor.from_pretrained(location, local_files_only=True, use_fast=False)
        model = CLIPSegForImageSegmentation.from_pretrained(location, local_files_only=True)
        model.eval().to("cpu")
        cls._semantic_processor = processor
        cls._semantic_model = model
        cls._semantic_model_location = location
        return processor, model

    @classmethod
    def _semantic_score(cls, pixels, target, area):
        import numpy as np
        import torch
        from PIL import Image

        processor, model = cls._load_semantic_model()
        eligible = np.argwhere(area > 0.05)
        if not eligible.size:
            raise ValueError("search_area does not cover any image pixels.")
        y0, x0 = eligible.min(axis=0)
        y1, x1 = eligible.max(axis=0) + 1
        cropped_pixels = pixels[y0:y1, x0:x1]
        crop_fraction = float(cropped_pixels.shape[0] * cropped_pixels.shape[1]) / float(
            pixels.shape[0] * pixels.shape[1]
        )
        queries = [target]
        target_words = set(re.findall(r"[a-z]+", target.casefold()))
        smoke_is_unqualified = "smoke" in target_words and not target_words.intersection(
            {"white", "gray", "grey", "black", "dark", "brown", "pale"}
        )
        if smoke_is_unqualified:
            # Absolute CLIPSeg confidence for smoke is poor, and color-qualified
            # phrases tend to lock onto white glass or black clothing. These two
            # complementary prompts reliably localize thin plumes and broad
            # low-contrast smoke respectively; normalize them spatially below.
            queries = ["haze from smoke", "fog"]
        semantic_image = Image.fromarray(cropped_pixels, "RGB")
        inputs = processor(
            text=queries,
            images=[semantic_image] * len(queries),
            padding=True,
            return_tensors="pt",
        )
        with torch.inference_mode():
            logits = model(**inputs).logits
        probabilities = torch.sigmoid(logits)
        if probabilities.ndim == 2:
            probabilities = probabilities[None, ...]
        resized = torch.nn.functional.interpolate(
            probabilities[:, None, ...],
            size=cropped_pixels.shape[:2],
            mode="bilinear",
            align_corners=False,
        )[:, 0]
        resized = resized.to("cpu").numpy()
        if smoke_is_unqualified:
            normalized = []
            for response in resized:
                low = float(np.quantile(response, 0.50))
                high = float(np.quantile(response, 0.999))
                normalized.append(np.clip((response - low) / max(1e-6, high - low), 0.0, 1.0))
            crop_score = np.max(normalized, axis=0)
        else:
            crop_score = np.max(resized, axis=0)
        score = np.zeros(pixels.shape[:2], dtype=np.float32)
        score[y0:y1, x0:x1] = np.clip(crop_score, 0.0, 1.0).astype(np.float32)
        details = []
        if crop_fraction < 0.98:
            details.append(f"semantic inference used the {crop_fraction:.1%} search-area crop")
        if smoke_is_unqualified:
            details.append("first-class smoke used relative thin-plume and broad-fog responses")
        return score, "; ".join(details)

    @staticmethod
    def _heuristic_score(rgb, candidate_type):
        import numpy as np

        red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        luma = red * 0.2126 + green * 0.7152 + blue * 0.0722
        spread = np.max(rgb, axis=2) - np.min(rgb, axis=2)
        if candidate_type == "bright highlights":
            return luma * luma
        if candidate_type == "warm lights":
            return np.clip(red - blue * 0.65, 0, 1) * np.clip(luma * 1.4, 0, 1)
        if candidate_type == "red accents":
            return np.clip(red - np.maximum(green, blue) * 0.85, 0, 1) * red
        if candidate_type == "neutral atmosphere":
            return np.clip(luma * 1.5, 0, 1) * np.clip(1.0 - spread * 3.0, 0, 1)
        dx = np.abs(np.diff(luma, axis=1, prepend=luma[:, :1]))
        dy = np.abs(np.diff(luma, axis=0, prepend=luma[:1, :]))
        return np.clip((dx + dy) * 3.0, 0, 1)

    @staticmethod
    def _guided_sun_disk_score(rgb, area):
        """Find a compact warm luminance peak inside a user-supplied sun search area."""
        import numpy as np
        from PIL import Image, ImageFilter

        eligible = np.argwhere(area > 0.05)
        score = np.zeros(area.shape, dtype=np.float32)
        if not eligible.size:
            return score
        y0, x0 = eligible.min(axis=0)
        y1, x1 = eligible.max(axis=0) + 1
        crop = rgb[y0:y1, x0:x1]
        luma = crop[..., 0] * 0.2126 + crop[..., 1] * 0.7152 + crop[..., 2] * 0.0722
        blur_radius = max(3, round(min(crop.shape[:2]) * 0.012))
        blurred = np.asarray(
            Image.fromarray(np.clip(luma * 255.0, 0, 255).astype(np.uint8), "L").filter(
                ImageFilter.GaussianBlur(radius=blur_radius)
            ),
            dtype=np.float32,
        ) / 255.0
        peak_y, peak_x = np.unravel_index(int(np.argmax(blurred)), blurred.shape)
        rows, columns = np.ogrid[: crop.shape[0], : crop.shape[1]]
        radius = max(4.0, min(crop.shape[:2]) * 0.025)
        radial = np.exp(-((columns - peak_x) ** 2 + (rows - peak_y) ** 2) / (2.0 * radius * radius))
        warm = np.clip((crop[..., 0] - crop[..., 2] * 0.45) * 1.5, 0.0, 1.0)
        local = np.clip((luma ** 3) * warm * radial, 0.0, 1.0)
        maximum = float(local.max())
        if maximum > 1e-8:
            local /= maximum
        score[y0:y1, x0:x1] = local * (area[y0:y1, x0:x1] > 0.05)
        return score

    def detect(
        self,
        image,
        find,
        search_area,
        sensitivity,
        max_regions,
        padding_percent,
        detection_provider="semantic_or_heuristic",
    ):
        import hashlib
        import numpy as np
        import torch
        from PIL import Image, ImageDraw, ImageFilter

        target = str(find).strip()
        if not target:
            raise ValueError("Describe the object class to find.")
        candidate_type = _target_candidate_type(target)
        pixels = _image_pixels(image)
        provider = str(detection_provider).strip().casefold()
        if provider not in {"semantic_or_heuristic", "semantic_only", "heuristic"}:
            raise ValueError(f"Unsupported detection provider: {detection_provider}")
        cache_key = (
            hashlib.blake2b(pixels.tobytes(), digest_size=16).digest(),
            target.casefold(), str(search_area), round(float(sensitivity), 4),
            int(max_regions), round(float(padding_percent), 4), provider,
            self._semantic_assets_available() if provider != "heuristic" else False,
        )
        cached = self._result_cache.get(cache_key)
        if cached is not None:
            return cached

        rgb = pixels.astype(np.float32) / 255.0
        height, width = pixels.shape[:2]
        area = _mask_pixels(pixels, search_area, "none", 0.0, 2.0)
        provider_note = ""
        semantic_note = ""
        used_provider = "heuristic"
        target_words = set(re.findall(r"[a-z]+", target.casefold()))
        guided_sun = "sun" in target_words and bool(target_words.intersection({"disk", "orb", "source"}))
        if guided_sun:
            score = self._guided_sun_disk_score(rgb, area)
            used_provider = "guided sun-disk locator"
            semantic_note = "a compact warm luminance peak refined the requested sun source"
        elif provider == "heuristic":
            score = self._heuristic_score(rgb, candidate_type)
        else:
            try:
                score, semantic_note = self._semantic_score(pixels, target, area)
                used_provider = "semantic CLIPSeg"
            except Exception as exc:
                if provider == "semantic_only":
                    raise RuntimeError(f"Semantic detection failed: {exc}") from exc
                score = self._heuristic_score(rgb, candidate_type)
                provider_note = f" Semantic detection was unavailable, so this run used the heuristic fallback ({exc})."

        # CLIPSeg's useful part-level responses can peak below 0.5. Keep the
        # absolute floor conservative while letting the quantile controls below
        # make higher sensitivity progressively more selective.
        if used_provider == "semantic CLIPSeg" and "smoke" in target_words:
            # Observed useful smoke responses peak much lower than solid-object
            # responses. Spatial quantiles still reject the weak background;
            # this floor merely stops discarding every smoke tile up front.
            semantic_floor = 0.08 + float(sensitivity) * 0.14
        else:
            semantic_floor = 0.24 + float(sensitivity) * 0.30 if used_provider == "semantic CLIPSeg" else 0.0

        columns, rows = ((32, 18) if "smoke" in target_words else (16, 9))
        grid = np.full((rows, columns), -1.0, dtype=np.float32)
        for row in range(rows):
            y0, y1 = row * height // rows, (row + 1) * height // rows
            for column in range(columns):
                x0, x1 = column * width // columns, (column + 1) * width // columns
                tile_area = area[y0:y1, x0:x1] > 0.05
                if np.any(tile_area):
                    grid[row, column] = float(np.percentile(score[y0:y1, x0:x1][tile_area], 85))
        valid_values = grid[grid >= 0.0]
        if not valid_values.size:
            raise ValueError("search_area does not cover any image pixels.")
        grid_cutoff = max(
            semantic_floor,
            float(np.quantile(valid_values, min(0.98, 0.50 + float(sensitivity) * 0.48))),
        )
        active = (grid >= grid_cutoff) & (grid >= 0.0)
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
                if candidate_type in {"bright highlights", "warm lights", "red accents"}:
                    value /= math.sqrt(len(cells))
                groups.append((value, cells))
        groups.sort(key=lambda item: item[0], reverse=True)
        padding = float(padding_percent) / 100.0
        lines = [f"# Suggested {target} inside the outlined search area; inspect before verifying."]
        for _, cells in groups[: int(max_regions)]:
            row_values, column_values = zip(*cells)
            x0 = max(0.0, min(column_values) / columns - padding)
            y0 = max(0.0, min(row_values) / rows - padding)
            x1 = min(1.0, (max(column_values) + 1) / columns + padding)
            y1 = min(1.0, (max(row_values) + 1) / rows + padding)
            lines.append(f"box {x0:.4f} {y0:.4f} {x1:.4f} {y1:.4f}")
        regions = "\n".join(lines)
        proposal = (
            np.clip(_mask_pixels(pixels, regions, "none", 0.0, 4.0) * area, 0.0, 1.0)
            if len(lines) > 1
            else np.zeros((height, width), dtype=np.float32)
        )
        eligible = proposal > 0.05
        cutoff = max(
            semantic_floor,
            float(np.quantile(score[eligible], min(0.97, 0.58 + float(sensitivity) * 0.37))) if np.any(eligible) else 1.0,
        )
        if used_provider == "guided sun-disk locator":
            cutoff = max(0.35, cutoff)
        mask = ((score >= cutoff) & eligible).astype(np.float32)
        mask = np.asarray(
            Image.fromarray((mask * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(radius=4.0)),
            dtype=np.float32,
        ) / 255.0
        preview = pixels.astype(np.float32) / 255.0
        preview = preview * (1.0 - mask[..., None] * 0.42)
        preview[..., 1] += mask * 0.42
        preview_image = Image.fromarray(np.clip(preview * 255.0, 0, 255).astype(np.uint8), "RGB")
        outline = ImageDraw.Draw(preview_image)
        outline_width = max(2, round(width / 480))
        for kind, coordinates in _parse_shapes(search_area, width, height):
            if kind == "box":
                outline.rectangle(coordinates, outline=(255, 215, 0), width=outline_width)
            elif kind == "ellipse":
                outline.ellipse(coordinates, outline=(255, 215, 0), width=outline_width)
            else:
                outline.line(coordinates + [coordinates[0]], fill=(255, 215, 0), width=outline_width, joint="curve")
        if preview_image.width > 640:
            preview_image = preview_image.resize(
                (640, max(1, round(preview_image.height * 640 / preview_image.width))),
                Image.Resampling.LANCZOS,
            )
        selected_fraction = float(np.mean(mask > 0.05))
        confidence = (
            f" Peak semantic confidence inside search_area was {float(np.max(score[area > 0.05])):.3f}."
            if used_provider == "semantic CLIPSeg" and np.any(area > 0.05)
            else ""
        )
        semantic_details = f" {semantic_note.capitalize()}." if semantic_note else ""
        provider_label = used_provider if used_provider in {"semantic CLIPSeg", "guided sun-disk locator"} else f"heuristic {candidate_type}"
        report = (
            f"'{target}' used {provider_label}; selected {selected_fraction:.2%} of the frame."
            f"{confidence}{semantic_details}{provider_note} The gold outline is search_area. "
            "Inspect verification_preview, adjust if needed, "
            "then explicitly verify the target."
        )
        result = (
            torch.from_numpy(mask.astype(np.float32)),
            torch.from_numpy(np.asarray(preview_image, dtype=np.float32) / 255.0)[None, ...],
            regions,
            report,
        )
        self._result_cache[cache_key] = result
        self._result_cache_order.append(cache_key)
        while len(self._result_cache_order) > self._result_cache_limit:
            expired = self._result_cache_order.pop(0)
            self._result_cache.pop(expired, None)
        return result


class VisualizerObjectDetector(VisualizerSemanticObjectDetector):
    """Stable model-free detector retained for the original target workflow."""

    @classmethod
    def INPUT_TYPES(cls):
        input_types = super().INPUT_TYPES()
        required = dict(input_types["required"])
        required.pop("detection_provider")
        return {"required": required}

    DESCRIPTION = "Find likely target pixels with lightweight color and texture heuristics."

    def detect(self, image, find, search_area, sensitivity, max_regions, padding_percent):
        return super().detect(
            image,
            find,
            search_area,
            sensitivity,
            max_regions,
            padding_percent,
            detection_provider="heuristic",
        )


class VisualizerManualTargetDetector(VisualizerSemanticObjectDetector):
    """Detector whose render-inclusion control lives beside the manual box."""

    @classmethod
    def INPUT_TYPES(cls):
        inputs = super().INPUT_TYPES()
        required = dict(inputs["required"])
        required["use_in_render"] = (
            "BOOLEAN",
            {
                "default": True,
                "label_on": "include this mask",
                "label_off": "exclude this mask",
                "tooltip": "Controls whether this detected/reviewed mask is included in the render.",
            },
        )
        return {"required": required}

    RETURN_TYPES = (*VisualizerSemanticObjectDetector.RETURN_TYPES, "BOOLEAN")
    RETURN_NAMES = (*VisualizerSemanticObjectDetector.RETURN_NAMES, "use_in_render")
    DESCRIPTION = "Box/detect a target, preview its mask, and choose here whether it is included in the render."

    def detect(
        self, image, find, search_area, sensitivity, max_regions, padding_percent,
        detection_provider, use_in_render,
    ):
        detected = super().detect(
            image, find, search_area, sensitivity, max_regions, padding_percent,
            detection_provider,
        )
        return (*detected, bool(use_in_render))


class VisualizerMaskReview:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "verification_preview": ("IMAGE",),
                "detected_mask": ("MASK",),
                "source_image": ("IMAGE",),
                # The frontend keeps this widget hidden. ComfyUI's Mask Editor
                # writes its saved clipspace image here, which makes Save feed
                # the painted mask into the next queue automatically.
                "image": ("STRING", {"default": ""}),
                # Bound to the source artwork by the frontend after execution.
                # This prevents a correction from leaking into a new image.
                "source_fingerprint": ("STRING", {"default": ""}),
            }
        }

    RETURN_TYPES = ("MASK", "STRING")
    RETURN_NAMES = ("reviewed_mask", "mask_source")
    FUNCTION = "review"
    CATEGORY = "audio/local visualizer/targets"
    OUTPUT_NODE = True
    DESCRIPTION = "Inspect a detection and optionally paint a correction in Mask Editor; Save applies it automatically."

    @staticmethod
    def _saved_correction(image_name, detected_mask):
        import numpy as np
        import torch
        import torch.nn.functional as functional
        from PIL import Image, ImageOps
        import folder_paths

        name = str(image_name or "").strip()
        if not name or not folder_paths.exists_annotated_filepath(name):
            return None
        path = folder_paths.get_annotated_filepath(name)
        with Image.open(path) as opened:
            loaded = ImageOps.exif_transpose(opened)
            if "A" not in loaded.getbands():
                return None
            saved_rgb = np.asarray(loaded.convert("RGB"), dtype=np.uint8)
            # Match LoadImage semantics: transparent pixels are selected mask.
            pixels = 1.0 - np.asarray(loaded.getchannel("A"), dtype=np.float32) / 255.0
        value = torch.from_numpy(np.array(pixels, copy=True))[None, ...]
        base = detected_mask.detach().to("cpu", dtype=torch.float32)
        if base.ndim == 2:
            base = base[None, ...]
        if value.shape[-2:] != base.shape[-2:]:
            value = functional.interpolate(
                value[:, None, ...], size=base.shape[-2:], mode="bilinear", align_corners=False,
            )[:, 0, ...]
        return value.clamp(0.0, 1.0), saved_rgb

    @staticmethod
    def _source_fingerprint(source_image):
        import hashlib

        pixels = _image_pixels(source_image)
        digest = hashlib.blake2b(digest_size=16)
        digest.update(str(pixels.shape).encode("ascii"))
        digest.update(pixels.tobytes())
        return digest.hexdigest()

    @staticmethod
    def _saved_preview_matches(saved_rgb, verification_preview):
        import numpy as np

        current = _image_pixels(verification_preview)
        if saved_rgb.shape != current.shape:
            return False
        difference = np.abs(saved_rgb.astype(np.int16) - current.astype(np.int16))
        return float(np.mean(difference)) <= 3.0 and float(np.mean(np.max(difference, axis=2) > 24)) <= 0.02

    @staticmethod
    def _saved_image_reference(image_name):
        name = str(image_name or "").strip()
        match = re.match(r"^(.*?)(?:\s+\[(input|output|temp)\])?$", name)
        relative = (match.group(1) if match else name).replace("\\", "/").lstrip("/")
        image_type = match.group(2) if match and match.group(2) else "input"
        path = Path(relative)
        subfolder = path.parent.as_posix()
        return {"filename": path.name, "subfolder": "" if subfolder == "." else subfolder, "type": image_type}

    def review(self, verification_preview, detected_mask, source_image, image="", source_fingerprint=""):
        import nodes

        current_fingerprint = self._source_fingerprint(source_image)
        correction = self._saved_correction(image, detected_mask)
        painted, saved_rgb = correction if correction is not None else (None, None)
        bound = painted is not None and str(source_fingerprint or "") == current_fingerprint
        legacy_match = (
            painted is not None
            and not str(source_fingerprint or "")
            and self._saved_preview_matches(saved_rgb, verification_preview)
        )
        painted_active = bound or legacy_match
        stale = bool(str(image or "").strip()) and not painted_active
        selected = painted if painted_active else detected_mask
        if painted_active:
            source = "painted Mask Editor correction"
        elif stale:
            source = "detector proposal (stale correction cleared after source change)"
        else:
            source = "detector proposal (no correction saved)"
        if painted_active:
            ui = {"images": [self._saved_image_reference(image)]}
        else:
            ui = nodes.PreviewImage().save_images(
                verification_preview, filename_prefix="local_visualizer_mask_review"
            ).get("ui", {})
        ui["mask_review_state"] = [{
            "source_fingerprint": current_fingerprint,
            "clear_saved_mask": stale,
        }]
        return {"ui": ui, "result": (selected, source)}


class VisualizerAnimationTarget:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mask": ("MASK",),
                "object_name": ("STRING", {"default": "clouds"}),
                "animation_prompt": ("STRING", {"multiline": True, "default": "clouds drifting slowly"}),
                "mask_verified": ("BOOLEAN", {"default": False}),
                "approved_mask_mode": (["add", "subtract", "replace"], {"default": "add"}),
                "motion_type": (["auto", "billow", "sway", "drift", "still"], {"default": "auto"}),
                "on_beat_flicker": ("FLOAT", {"default": 0.75, "min": 0.0, "max": 2.0, "step": 0.05}),
                "off_beat_flicker": ("FLOAT", {"default": 0.65, "min": 0.0, "max": 2.0, "step": 0.05}),
                "on_beat_motion": ("FLOAT", {"default": 0.20, "min": 0.0, "max": 2.0, "step": 0.05}),
                "off_beat_motion": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 2.0, "step": 0.05}),
            },
            "optional": {
                "approved_mask": ("MASK",),
            },
        }

    RETURN_TYPES = ("LOCAL_VISUALIZER_TARGET", "STRING")
    RETURN_NAMES = ("animation_target", "resolved_effects")
    FUNCTION = "configure"
    CATEGORY = "audio/local visualizer/targets"
    DESCRIPTION = "Describe one verified target and independently mix beat/off-beat flicker and masked motion."

    def configure(
        self, mask, object_name, animation_prompt, mask_verified,
        approved_mask_mode, motion_type,
        on_beat_flicker, off_beat_flicker, on_beat_motion, off_beat_motion,
        approved_mask=None,
    ):
        name = str(object_name).strip()
        prompt = str(animation_prompt).strip()
        if not name or not prompt:
            raise ValueError("Each animation target needs an object name and animation description.")
        modes = _target_effect_modes(name, prompt)
        requested_motion = str(motion_type).casefold()
        if requested_motion == "auto":
            combined = f"{name} {prompt}".casefold()
            if any(word in combined for word in ("cloud", "smoke", "fog", "mist", "steam", "billow")):
                resolved_motion = "billow"
            elif any(word in combined for word in ("candle", "flame", "fire", "sway", "breeze")):
                resolved_motion = "sway"
            else:
                resolved_motion = "drift"
        elif requested_motion in {"billow", "sway", "drift", "still"}:
            resolved_motion = requested_motion
        else:
            raise ValueError(f"Unsupported motion type: {motion_type}")
        approved_active = False
        if approved_mask is not None:
            value = approved_mask.detach().to("cpu")
            approved_active = bool(value.numel() and float(value.max().item()) > (1.0 / 255.0))
        selected_mask = mask
        mode = str(approved_mask_mode).casefold()
        if approved_active:
            if mode in {"add", "subtract"}:
                import torch.nn.functional as functional

                base = mask.detach().to("cpu", dtype=__import__("torch").float32)
                adjustment = approved_mask.detach().to("cpu", dtype=base.dtype)
                if base.ndim == 2:
                    base = base[None, ...]
                if adjustment.ndim == 2:
                    adjustment = adjustment[None, ...]
                if adjustment.shape[-2:] != base.shape[-2:]:
                    adjustment = functional.interpolate(
                        adjustment[:, None, ...], size=base.shape[-2:], mode="bilinear", align_corners=False,
                    )[:, 0, ...]
                selected_mask = (base + adjustment if mode == "add" else base - adjustment).clamp(0.0, 1.0)
            elif mode == "replace":
                selected_mask = approved_mask
            else:
                raise ValueError(f"Unsupported approved mask mode: {approved_mask_mode}")
        target = {
            "mask": selected_mask,
            "object_name": name,
            "animation_prompt": prompt,
            "mask_verified": bool(mask_verified),
            "motion_type": resolved_motion,
            "on_beat_flicker": float(on_beat_flicker),
            "off_beat_flicker": float(off_beat_flicker),
            "on_beat_motion": float(on_beat_motion),
            "off_beat_motion": float(off_beat_motion),
            "effect_modes": modes,
        }
        source = f"approved mask ({mode})" if approved_active else "detector mask (approved input blank)" if approved_mask is not None else "detector mask"
        summary = (
            f"{name}: {', '.join(modes)}; {resolved_motion} motion; flicker {float(on_beat_flicker):.2f}/{float(off_beat_flicker):.2f}, "
            f"motion {float(on_beat_motion):.2f}/{float(off_beat_motion):.2f} (beat/off-beat); {source}"
        )
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
                "wordmark_sparkle_strength": ("FLOAT", {"default": 0.70, "min": 0.0, "max": 1.5, "step": 0.05}),
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
        overlay_margin_px, wordmark_halo_opacity, wordmark_halo_blur_px,
        output_prefix, wordmark_sparkle_strength=0.70,
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
        skipped = [target["object_name"] for target in targets if not target.get("mask_verified")]
        targets = tuple(target for target in targets if target.get("mask_verified"))
        if skipped:
            print("[Local Visualizer] Skipping unverified targets: " + ", ".join(skipped))
        if not targets:
            raise ValueError("Verify at least one animation target before rendering.")

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
        empty = []
        for index, target in enumerate(targets):
            layer = _prepare_layer(target["mask"], width, height)
            if layer.bounds is None:
                empty.append(target["object_name"])
                continue
            x0, y0, x1, y1 = layer.bounds
            plans.append({
                **target, "layer": layer,
                "motion_mask": _motion_interior(
                    layer.mask,
                    round(8.0 * max(0.75, height / 720.0)) if target.get("motion_type") == "billow" else 0,
                ),
                "rows": np.arange(y1 - y0, dtype=np.float32)[:, None, None],
                "columns": np.arange(x1 - x0, dtype=np.float32)[None, :, None],
                "phase": (int(pattern_key) * 0.0001 + index * 1.913) % (math.pi * 2.0),
            })
        if empty:
            print("[Local Visualizer] Skipping verified targets with empty masks: " + ", ".join(empty))
        if not plans:
            raise ValueError("No verified animation target produced a non-empty mask.")

        overlays = []
        wordmark_overlay = None
        margin = round(float(overlay_margin_px) * width / 1920)
        if bool(apply_wordmark):
            overlay = _prepare_overlay(wordmark, wordmark_mask, max(2, round(width * float(wordmark_width_percent) / 100.0)), float(wordmark_opacity), margin, margin)
            wordmark_overlay = overlay
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
                        unmoved = changed
                        phase = plan["phase"]
                        beat_signal = 0.72 * features["beat"][frame_index] + 0.28 * features["onset"][frame_index]
                        beat = float(plan.get("on_beat_flicker", plan.get("on_beat_strength", 0.0))) * beat_signal
                        off_beat_flicker = float(plan.get("off_beat_flicker", plan.get("off_beat_strength", 0.0)))
                        autonomous = off_beat_flicker * (0.55 + 0.25 * math.sin(seconds * 0.83 + phase) + 0.20 * math.sin(seconds * 1.91 + phase * 1.7))
                        flow = 0.5 * (
                            np.sin(plan["columns"] * 0.008 + plan["rows"] * 0.005 - seconds * 0.55 + phase)
                            + np.cos(plan["columns"] * 0.004 - plan["rows"] * 0.009 + seconds * 0.37 + phase)
                        )
                        text = f"{plan['object_name']} {plan['animation_prompt']}".casefold()
                        modes = set(plan["effect_modes"])
                        motion_type = str(plan.get("motion_type", "drift"))
                        motion_pixels = {"billow": 11.0, "sway": 5.0, "drift": 6.0, "still": 0.0}.get(motion_type, 4.0)
                        motion_pixels *= max(0.75, height / 720.0)
                        on_beat_motion = float(plan.get("on_beat_motion", 0.0)) * beat_signal
                        off_beat_motion = float(plan.get("off_beat_motion", 0.0))
                        motion_amplitude = motion_pixels * (off_beat_motion + on_beat_motion)
                        if motion_type in {"billow", "sway"}:
                            warped = _deform_pixels(changed, seconds, phase, motion_amplitude, motion_type)
                            motion_alpha = plan["motion_mask"][y0:y1, x0:x1, None]
                            changed = unmoved * (1.0 - motion_alpha) + warped * motion_alpha
                        elif motion_type == "drift":
                            offset_x = motion_amplitude * math.sin(seconds * 0.72 + phase)
                            offset_y = motion_amplitude * 0.45 * math.cos(seconds * 0.51 + phase * 1.7)
                            warped = _translate_pixels(changed, offset_x, offset_y)
                            motion_alpha = plan["motion_mask"][y0:y1, x0:x1, None]
                            changed = unmoved * (1.0 - motion_alpha) + warped * motion_alpha
                        for mode in plan["effect_modes"]:
                            if mode == "drift":
                                changed *= 1.0 + 0.045 * beat + autonomous * (0.035 + 0.10 * flow)
                            elif mode == "flicker":
                                irregular = max(0.0, 0.55 + 0.30 * math.sin(seconds * 17.3 + phase) + 0.15 * math.sin(seconds * 7.1 + phase * 2.0))
                                drive = beat + off_beat_flicker * irregular
                                changed *= 1.0 + 0.22 * drive
                                if any(word in text for word in ("candle", "flame", "fire", "warm")):
                                    changed[..., 0] += 36.0 * drive
                                    changed[..., 1] += 14.0 * drive
                            elif mode == "flash":
                                sporadic = max(0.0, math.sin(seconds * 0.47 + phase)) ** 14
                                drive = beat + off_beat_flicker * sporadic
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
                    if wordmark_overlay is not None:
                        _apply_wordmark_sparkle(
                            frame,
                            wordmark_overlay,
                            seconds,
                            float(wordmark_sparkle_strength),
                            float(features["high"][frame_index]),
                            (int(pattern_key) % 6000) / 1000.0,
                        )
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


class InfraChoirAnimationTarget:
    """One independently switchable target for the hybrid visualizer."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "enabled": ("BOOLEAN", {"default": False}),
                "target_id": ("STRING", {"default": "target_1"}),
                "object_name": ("STRING", {"default": ""}),
                "animation_prompt": ("STRING", {"multiline": True, "default": ""}),
                "mask_verified": ("BOOLEAN", {"default": False}),
                "target_role": (["organic", "light_source", "illumination", "reflection"], {"default": "organic"}),
                "envelope_group": ("STRING", {"default": "independent"}),
                "audio_driver": (["beat", "slow", "energy", "high", "onset"], {"default": "beat"}),
                "motion_source": (["procedural", "generated_clip", "generated_then_procedural"], {"default": "procedural"}),
                "motion_type": (["auto", "billow", "sway", "drift", "still"], {"default": "auto"}),
                "on_beat_flicker": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 2.0, "step": 0.05}),
                "off_beat_flicker": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 2.0, "step": 0.05}),
                "on_beat_motion": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 2.0, "step": 0.05}),
                "off_beat_motion": ("FLOAT", {"default": 0.45, "min": 0.0, "max": 2.0, "step": 0.05}),
                "generated_motion_strength": ("FLOAT", {"default": 0.85, "min": 0.0, "max": 1.0, "step": 0.05}),
                "max_luminance_change": ("FLOAT", {"default": 0.12, "min": 0.0, "max": 0.5, "step": 0.01}),
                "glow_strength": ("FLOAT", {"default": 0.15, "min": 0.0, "max": 1.0, "step": 0.05}),
                "glow_radius_px": ("FLOAT", {"default": 18.0, "min": 0.0, "max": 160.0, "step": 1.0}),
                "saturation_variation": ("FLOAT", {"default": 0.06, "min": -0.5, "max": 0.5, "step": 0.01}),
                "hue_variation_degrees": ("FLOAT", {"default": 3.0, "min": -30.0, "max": 30.0, "step": 0.5}),
                "approved_mask_mode": (["add", "subtract", "replace"], {"default": "add"}),
            },
            "optional": {
                "mask": ("MASK",),
                "approved_mask": ("MASK",),
                "generated_motion": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("LOCAL_VISUALIZER_TARGET", "STRING", "STRING")
    RETURN_NAMES = ("animation_target", "diagnostic", "configuration_json")
    FUNCTION = "configure"
    CATEGORY = "audio/infra choir"
    DESCRIPTION = "Configure an optional organic, light-source, illumination, or reflection target."

    def configure(
        self, enabled, target_id, object_name, animation_prompt, mask_verified,
        target_role, envelope_group, audio_driver, motion_source, motion_type,
        on_beat_flicker, off_beat_flicker, on_beat_motion, off_beat_motion,
        generated_motion_strength, max_luminance_change, glow_strength, glow_radius_px,
        saturation_variation, hue_variation_degrees, approved_mask_mode,
        mask=None, approved_mask=None, generated_motion=None, **enhancement_values,
    ):
        identifier = str(target_id).strip()
        name = str(object_name).strip()
        prompt = str(animation_prompt).strip()
        active = bool(enabled)
        diagnostic = "disabled"
        selected_mask = mask
        if active and (not identifier or not name):
            diagnostic = "skipped: enabled target needs target_id and object_name"
        elif active and selected_mask is None:
            diagnostic = "skipped: enabled target has no mask connection"
        elif active and not bool(mask_verified):
            diagnostic = "skipped: mask has not been verified"
        elif active:
            diagnostic = "ready"

        if selected_mask is not None and approved_mask is not None:
            import torch.nn.functional as functional

            base = selected_mask.detach().to("cpu", dtype=__import__("torch").float32)
            correction = approved_mask.detach().to("cpu", dtype=base.dtype)
            if base.ndim == 2:
                base = base[None, ...]
            if correction.ndim == 2:
                correction = correction[None, ...]
            if correction.shape[-2:] != base.shape[-2:]:
                correction = functional.interpolate(
                    correction[:, None, ...], size=base.shape[-2:], mode="bilinear", align_corners=False,
                )[:, 0, ...]
            mode = str(approved_mask_mode).casefold()
            if mode == "replace":
                selected_mask = correction
            elif mode == "add":
                selected_mask = (base + correction).clamp(0.0, 1.0)
            elif mode == "subtract":
                selected_mask = (base - correction).clamp(0.0, 1.0)

        requested_motion = str(motion_type).casefold()
        combined = f"{name} {prompt}".casefold()
        if requested_motion == "auto":
            if any(word in combined for word in ("cloud", "smoke", "fog", "mist", "steam", "billow")):
                resolved_motion = "billow"
            elif any(word in combined for word in ("hair", "fabric", "flag", "scarf", "flame", "sway", "breeze")):
                resolved_motion = "sway"
            else:
                resolved_motion = "drift"
        else:
            resolved_motion = requested_motion
        serializable = {
            "version": 1,
            "target_id": identifier,
            "object_name": name,
            "animation_prompt": prompt,
            "enabled": active,
            "mask_verified": bool(mask_verified),
            "target_role": str(target_role),
            "envelope_group": str(envelope_group).strip() or "independent",
            "audio_driver": str(audio_driver),
            "motion_source": str(motion_source),
            "motion_type": resolved_motion,
            "on_beat_flicker": float(on_beat_flicker),
            "off_beat_flicker": float(off_beat_flicker),
            "on_beat_motion": float(on_beat_motion),
            "off_beat_motion": float(off_beat_motion),
            "generated_motion_strength": float(generated_motion_strength),
            "max_luminance_change": float(max_luminance_change),
            "glow_strength": float(glow_strength),
            "glow_radius_px": float(glow_radius_px),
            "saturation_variation": float(saturation_variation),
            "hue_variation_degrees": float(hue_variation_degrees),
        }
        if enhancement_values:
            serializable["version"] = 2
            serializable.update({
                "secondary_audio_driver": str(enhancement_values.get("secondary_audio_driver", "none")),
                "secondary_driver_mix": float(enhancement_values.get("secondary_driver_mix", 0.0)),
                "response_attack_ms": float(enhancement_values.get("response_attack_ms", 40.0)),
                "response_decay_ms": float(enhancement_values.get("response_decay_ms", 180.0)),
                "response_hold_ms": float(enhancement_values.get("response_hold_ms", 0.0)),
                "response_sustain": float(enhancement_values.get("response_sustain", 0.0)),
                "response_release_ms": float(enhancement_values.get("response_release_ms", 280.0)),
                "response_smoothing": float(enhancement_values.get("response_smoothing", 0.15)),
                "response_min": float(enhancement_values.get("response_min", 0.0)),
                "response_max": float(enhancement_values.get("response_max", 1.0)),
                "response_sensitivity": float(enhancement_values.get("response_sensitivity", 1.0)),
                "response_curve": float(enhancement_values.get("response_curve", 1.0)),
                "rhythmic_subdivision": int(enhancement_values.get("rhythmic_subdivision", 1)),
                "accent_weight": float(enhancement_values.get("accent_weight", 0.0)),
                "group_gain": float(enhancement_values.get("group_gain", 1.0)),
                "group_delay_ms": float(enhancement_values.get("group_delay_ms", 0.0)),
                "lighting_gain": float(enhancement_values.get("lighting_gain", 1.0)),
                "edge_glow_enabled": bool(enhancement_values.get("edge_glow_enabled", False)),
                "edge_glow_amount": float(enhancement_values.get("edge_glow_amount", 0.0)),
                "shimmer_enabled": bool(enhancement_values.get("shimmer_enabled", False)),
                "shimmer_amount": float(enhancement_values.get("shimmer_amount", 0.0)),
                "section_response": float(enhancement_values.get("section_response", 0.0)),
                "atmospheric_motion_mode": str(enhancement_values.get("atmospheric_motion_mode", "auto")),
                "atmospheric_expansion_percent": float(enhancement_values.get("atmospheric_expansion_percent", 0.0)),
                "generated_clip_path": str(enhancement_values.get("generated_clip_path", "")).strip(),
                "generated_clip_max_seconds": float(enhancement_values.get("generated_clip_max_seconds", 6.0)),
                "generated_clip_overlap_seconds": float(
                    enhancement_values.get(
                        "generated_clip_overlap_seconds",
                        enhancement_values.get("clip_loop_blend_seconds", 0.6),
                    )
                ),
                "smoke_effect_strength": float(enhancement_values.get("smoke_effect_strength", 1.0)),
                "foreground_protection": bool(enhancement_values.get("foreground_protection", True)),
            })
        target = {
            **serializable,
            "mask": selected_mask,
            "generated_motion": generated_motion,
            "effect_modes": _target_effect_modes(name, prompt),
            "configuration_valid": diagnostic == "ready",
            "configuration_diagnostic": diagnostic,
        }
        return target, f"{identifier or 'unnamed'}: {diagnostic}", json.dumps(serializable, sort_keys=True)


class InfraChoirAnimationTargetEnhanced(InfraChoirAnimationTarget):
    """Backward-compatible target with optional Fill-inspired envelope shaping."""

    @classmethod
    def INPUT_TYPES(cls):
        inputs = InfraChoirAnimationTarget.INPUT_TYPES()
        required = dict(inputs["required"])
        drivers = [
            "beat", "energy", "low", "mid", "high", "kick", "snare", "hihat",
            "onset", "beat_phase", "phrase", "slow", "vocal_energy", "instrument_energy",
        ]
        required["audio_driver"] = (drivers, {"default": "beat"})
        required.update({
            "secondary_audio_driver": (["none", *drivers], {"default": "none"}),
            "secondary_driver_mix": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),
            "response_attack_ms": ("FLOAT", {"default": 40.0, "min": 0.0, "max": 2000.0, "step": 5.0}),
            "response_decay_ms": ("FLOAT", {"default": 180.0, "min": 5.0, "max": 4000.0, "step": 5.0}),
            "response_hold_ms": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 2000.0, "step": 5.0}),
            "response_sustain": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),
            "response_release_ms": ("FLOAT", {"default": 280.0, "min": 5.0, "max": 6000.0, "step": 5.0}),
            "response_smoothing": ("FLOAT", {"default": 0.15, "min": 0.0, "max": 0.98, "step": 0.01}),
            "response_min": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01}),
            "response_max": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
            "response_sensitivity": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 3.0, "step": 0.05}),
            "response_curve": ("FLOAT", {"default": 1.0, "min": 0.2, "max": 4.0, "step": 0.05}),
            "rhythmic_subdivision": ([1, 2, 4], {"default": 1}),
            "accent_weight": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),
            "group_gain": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05}),
            "group_delay_ms": ("FLOAT", {"default": 0.0, "min": -1000.0, "max": 2000.0, "step": 10.0}),
            "lighting_gain": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 3.0, "step": 0.05}),
            "edge_glow_enabled": ("BOOLEAN", {"default": False}),
            "edge_glow_amount": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),
            "shimmer_enabled": ("BOOLEAN", {"default": False}),
            "shimmer_amount": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),
            "section_response": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),
        })
        return {"required": required, "optional": inputs["optional"]}

    DESCRIPTION = "Configure an Infra Choir target with frame-aligned musical drivers and ADSHR shaping."


class InfraChoirAtmosphericTargetEnhanced(InfraChoirAnimationTargetEnhanced):
    """Enhanced target with offline cached-clip and protected expansion controls."""

    @classmethod
    def INPUT_TYPES(cls):
        inputs = InfraChoirAnimationTargetEnhanced.INPUT_TYPES()
        required = dict(inputs["required"])
        # Atmospheric lanes in the curated manual workflow are explicitly boxed
        # by the user.  Default them to active once enabled; automatic discovery
        # remains review-gated in its separate manifest path.
        required["mask_verified"] = (
            "BOOLEAN",
            {
                "default": True,
                "label_on": "use boxed mask",
                "label_off": "skip boxed mask",
                "tooltip": "Must be on for this manual smoke/cloud lane to render.",
            },
        )
        required.update({
            "atmospheric_motion_mode": (
                ["auto", "procedural", "cached_clip", "cached_clip_then_procedural"],
                {"default": "auto"},
            ),
            "smoke_boundary_expansion_percent": (
                "FLOAT", {"default": 15.0, "min": 0.0, "max": 50.0, "step": 1.0},
            ),
            "generated_clip_path": (
                "STRING",
                {
                    "default": "",
                    "tooltip": "Optional pre-rendered motion-video path. Leave empty for procedural smoke.",
                },
            ),
            "generated_clip_max_seconds": ("FLOAT", {"default": 6.0, "min": 0.25, "max": 10.0, "step": 0.25}),
            "smoke_intensity": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 3.0, "step": 0.05}),
            "foreground_protection": ("BOOLEAN", {"default": True}),
        })
        return {"required": required, "optional": inputs["optional"]}

    def configure(self, smoke_intensity, smoke_boundary_expansion_percent, **kwargs):
        kwargs["atmospheric_expansion_percent"] = smoke_boundary_expansion_percent
        kwargs["smoke_effect_strength"] = smoke_intensity
        return super().configure(**kwargs)

    DESCRIPTION = "Manually box smoke/clouds, set visible smoke intensity, and expand the animated boundary by an explicit percent."


def _manual_advanced_settings(value) -> dict:
    """Decode the popout-backed settings without exposing a graph-sized control wall."""
    if isinstance(value, dict):
        return dict(value)
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Advanced Settings contains invalid JSON: {error.msg}") from error
    if not isinstance(decoded, dict):
        raise ValueError("Advanced Settings must serialize as a JSON object.")
    return decoded


class InfraChoirManualAtmosphereTarget:
    """Compact procedural-smoke control fed by a manual detector/review lane."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mask": ("MASK",),
                "use_in_render": ("BOOLEAN", {"forceInput": True}),
                "target_id": ("STRING", {"default": "manual_smoke"}),
                "object_name": ("STRING", {"default": "smoke"}),
                "animation_prompt": ("STRING", {"multiline": True, "default": "smoke billowing organically"}),
                "smoke_intensity": ("FLOAT", {"default": 1.6, "min": 0.0, "max": 3.0, "step": 0.05}),
                "smoke_boundary_expansion_percent": (
                    "FLOAT", {"default": 28.0, "min": 0.0, "max": 50.0, "step": 1.0},
                ),
                "billow_amount": ("FLOAT", {"default": 0.62, "min": 0.0, "max": 2.0, "step": 0.05}),
                "foreground_protection": ("BOOLEAN", {"default": True}),
                "advanced_settings_json": (
                    "STRING",
                    {
                        "default": "{}",
                        "multiline": True,
                        "dynamicPrompts": False,
                        "tooltip": "Managed by the Advanced Settings popout.",
                    },
                ),
            }
        }

    RETURN_TYPES = ("LOCAL_VISUALIZER_TARGET", "STRING", "STRING")
    RETURN_NAMES = ("animation_target", "diagnostic", "configuration_json")
    FUNCTION = "configure"
    CATEGORY = "audio/infra choir"
    DESCRIPTION = "Compact manual smoke lane: inclusion lives on the detector; this card controls billow strength and boundary."

    def configure(
        self, mask, use_in_render, target_id, object_name, animation_prompt,
        smoke_intensity, smoke_boundary_expansion_percent, billow_amount,
        foreground_protection, advanced_settings_json="{}",
    ):
        advanced = _manual_advanced_settings(advanced_settings_json)
        target_id = str(target_id).strip()
        if not target_id:
            target_id = str(advanced.get("target_id", "")).strip()
        if not target_id:
            target_id = re.sub(r"[^a-z0-9]+", "_", str(object_name).casefold()).strip("_") or "manual_smoke"
        return InfraChoirAtmosphericTargetEnhanced().configure(
            mask=mask, enabled=bool(use_in_render), target_id=target_id,
            object_name=object_name, animation_prompt=animation_prompt,
            mask_verified=bool(use_in_render), target_role="organic",
            envelope_group=str(advanced.get("envelope_group", "atmosphere")),
            audio_driver=str(advanced.get("audio_driver", "slow")),
            motion_source=str(advanced.get("motion_source", "procedural")), motion_type="billow",
            on_beat_flicker=float(advanced.get("on_beat_flicker", 0.0)),
            off_beat_flicker=float(advanced.get("off_beat_flicker", 0.0)),
            on_beat_motion=float(advanced.get("on_beat_motion", 0.0)),
            off_beat_motion=float(billow_amount),
            generated_motion_strength=float(advanced.get("generated_motion_strength", 0.0)),
            max_luminance_change=float(advanced.get("max_luminance_change", 0.02)),
            glow_strength=float(advanced.get("glow_strength", 0.0)),
            glow_radius_px=float(advanced.get("glow_radius_px", 0.0)),
            saturation_variation=float(advanced.get("saturation_variation", -0.02)),
            hue_variation_degrees=float(advanced.get("hue_variation_degrees", 0.0)),
            approved_mask_mode=str(advanced.get("approved_mask_mode", "add")),
            secondary_audio_driver=str(advanced.get("secondary_audio_driver", "none")),
            secondary_driver_mix=float(advanced.get("secondary_driver_mix", 0.0)),
            response_attack_ms=float(advanced.get("response_attack_ms", 220.0)),
            response_decay_ms=float(advanced.get("response_decay_ms", 620.0)),
            response_hold_ms=float(advanced.get("response_hold_ms", 80.0)),
            response_sustain=float(advanced.get("response_sustain", 0.3)),
            response_release_ms=float(advanced.get("response_release_ms", 1150.0)),
            response_smoothing=float(advanced.get("response_smoothing", 0.42)),
            response_min=float(advanced.get("response_min", 0.12)),
            response_max=float(advanced.get("response_max", 0.78)),
            response_sensitivity=float(advanced.get("response_sensitivity", 0.9)),
            response_curve=float(advanced.get("response_curve", 1.15)),
            rhythmic_subdivision=int(advanced.get("rhythmic_subdivision", 1)),
            accent_weight=float(advanced.get("accent_weight", 0.0)),
            group_gain=float(advanced.get("group_gain", 1.0)),
            group_delay_ms=float(advanced.get("group_delay_ms", 0.0)),
            lighting_gain=float(advanced.get("lighting_gain", 1.0)),
            edge_glow_enabled=bool(advanced.get("edge_glow_enabled", False)),
            edge_glow_amount=float(advanced.get("edge_glow_amount", 0.0)),
            shimmer_enabled=bool(advanced.get("shimmer_enabled", False)),
            shimmer_amount=float(advanced.get("shimmer_amount", 0.0)),
            section_response=float(advanced.get("section_response", 0.0)),
            atmospheric_motion_mode=str(advanced.get("atmospheric_motion_mode", "procedural")),
            smoke_boundary_expansion_percent=float(smoke_boundary_expansion_percent),
            generated_clip_path=str(advanced.get("generated_clip_path", "")),
            generated_clip_max_seconds=float(advanced.get("generated_clip_max_seconds", 6.0)),
            generated_clip_overlap_seconds=float(advanced.get("generated_clip_overlap_seconds", 0.6)),
            smoke_intensity=float(smoke_intensity),
            foreground_protection=bool(foreground_protection),
        )


class InfraChoirCachedMotionTarget:
    """Compact full-frame cached-motion lane with an actual local-video selector."""

    @classmethod
    def INPUT_TYPES(cls):
        choices = _cached_motion_clip_choices()
        return {
            "required": {
                "mask": ("MASK",),
                "use_in_render": ("BOOLEAN", {"forceInput": True}),
                "generated_clip_path": (choices, {"default": choices[0]}),
                "generated_motion_strength": (
                    "FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05},
                ),
                "generated_clip_max_seconds": (
                    "FLOAT", {"default": 10.0, "min": 0.25, "max": 10.0, "step": 0.25},
                ),
                "generated_clip_overlap_seconds": (
                    "FLOAT", {"default": 0.8, "min": 0.0, "max": 3.0, "step": 0.05},
                ),
            }
        }

    RETURN_TYPES = ("LOCAL_VISUALIZER_TARGET", "STRING", "STRING")
    RETURN_NAMES = ("animation_target", "diagnostic", "configuration_json")
    FUNCTION = "configure"
    CATEGORY = "audio/infra choir"
    DESCRIPTION = "Select and loop a reviewed local motion clip without hiding its path in advanced JSON."

    def configure(
        self, mask, use_in_render, generated_clip_path, generated_motion_strength,
        generated_clip_max_seconds, generated_clip_overlap_seconds,
    ):
        selection = str(generated_clip_path).strip()
        placeholder = selection == "(select a cached motion clip)"
        active = bool(use_in_render) and not placeholder
        result = InfraChoirAnimationTargetEnhanced().configure(
            mask=mask, enabled=active, target_id="cached_full_scene_motion",
            object_name="cached full-scene motion",
            animation_prompt="Loop the reviewed motion clip without adding procedural geometry motion.",
            mask_verified=active, target_role="organic", envelope_group="environment",
            audio_driver="slow", motion_source="generated_clip", motion_type="still",
            on_beat_flicker=0.0, off_beat_flicker=0.0, on_beat_motion=0.0,
            off_beat_motion=0.0, generated_motion_strength=float(generated_motion_strength),
            max_luminance_change=0.0, glow_strength=0.0, glow_radius_px=0.0,
            saturation_variation=0.0, hue_variation_degrees=0.0, approved_mask_mode="add",
            secondary_audio_driver="none", secondary_driver_mix=0.0,
            response_min=0.0, response_max=1.0, foreground_protection=False,
            atmospheric_motion_mode="cached_clip", generated_clip_path="" if placeholder else selection,
            generated_clip_max_seconds=float(generated_clip_max_seconds),
            generated_clip_overlap_seconds=float(generated_clip_overlap_seconds),
        )
        if bool(use_in_render) and placeholder:
            return result[0], "cached_full_scene_motion: select a cached motion clip", result[2]
        return result


class InfraChoirManualTargetCompact:
    """Compact manual organic/lighting target with inclusion owned by its detector."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mask": ("MASK",),
                "use_in_render": ("BOOLEAN", {"forceInput": True}),
                "target_id": ("STRING", {"default": "manual_target"}),
                "object_name": ("STRING", {"default": "target"}),
                "animation_prompt": ("STRING", {"multiline": True, "default": "subtle local effect"}),
                "target_role": (["organic", "light_source", "illumination", "reflection"], {"default": "organic"}),
                "linked_group": ("STRING", {"default": "independent"}),
                "motion_type": (["billow", "sway", "drift", "still"], {"default": "still"}),
                "beat_flicker": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 2.0, "step": 0.05}),
                "ambient_flicker": ("FLOAT", {"default": 0.10, "min": 0.0, "max": 2.0, "step": 0.05}),
                "motion_amount": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 2.0, "step": 0.05}),
                "max_luminance_change": ("FLOAT", {"default": 0.10, "min": 0.0, "max": 0.5, "step": 0.01}),
                "glow_strength": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "glow_radius_px": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 160.0, "step": 1.0}),
                "saturation_variation": ("FLOAT", {"default": 0.0, "min": -0.5, "max": 0.5, "step": 0.01}),
                "hue_variation_degrees": ("FLOAT", {"default": 0.0, "min": -30.0, "max": 30.0, "step": 0.5}),
                "advanced_settings_json": (
                    "STRING",
                    {
                        "default": "{}",
                        "multiline": True,
                        "dynamicPrompts": False,
                        "tooltip": "Managed by the Advanced Settings popout.",
                    },
                ),
            }
        }

    RETURN_TYPES = ("LOCAL_VISUALIZER_TARGET", "STRING", "STRING")
    RETURN_NAMES = ("animation_target", "diagnostic", "configuration_json")
    FUNCTION = "configure"
    CATEGORY = "audio/infra choir"
    DESCRIPTION = "Compact manual target; inclusion is controlled on the associated box/detection card."

    def configure(
        self, mask, use_in_render, target_id, object_name, animation_prompt,
        target_role, linked_group, motion_type, beat_flicker, ambient_flicker,
        motion_amount, max_luminance_change, glow_strength, glow_radius_px,
        saturation_variation, hue_variation_degrees, advanced_settings_json="{}",
    ):
        role = str(target_role)
        advanced = _manual_advanced_settings(advanced_settings_json)
        target_id = str(target_id).strip()
        if not target_id:
            target_id = str(advanced.get("target_id", "")).strip()
        if not target_id:
            target_id = re.sub(r"[^a-z0-9]+", "_", str(object_name).casefold()).strip("_") or "manual_target"
        return InfraChoirAnimationTargetEnhanced().configure(
            mask=mask, enabled=bool(use_in_render), target_id=target_id,
            object_name=object_name, animation_prompt=animation_prompt,
            mask_verified=bool(use_in_render), target_role=role,
            envelope_group=str(linked_group).strip() or "independent",
            audio_driver=str(advanced.get("audio_driver", "slow" if role == "organic" else "beat")),
            motion_source=str(advanced.get("motion_source", "procedural")), motion_type=motion_type,
            on_beat_flicker=float(beat_flicker), off_beat_flicker=float(ambient_flicker),
            on_beat_motion=float(advanced.get("on_beat_motion", 0.0)), off_beat_motion=float(motion_amount),
            generated_motion_strength=float(advanced.get("generated_motion_strength", 0.0)),
            max_luminance_change=float(max_luminance_change),
            glow_strength=float(glow_strength), glow_radius_px=float(glow_radius_px),
            saturation_variation=float(saturation_variation),
            hue_variation_degrees=float(hue_variation_degrees),
            approved_mask_mode=str(advanced.get("approved_mask_mode", "add")),
            secondary_audio_driver=str(advanced.get("secondary_audio_driver", "none")),
            secondary_driver_mix=float(advanced.get("secondary_driver_mix", 0.0)),
            response_attack_ms=float(advanced.get("response_attack_ms", 80.0)),
            response_decay_ms=float(advanced.get("response_decay_ms", 260.0)),
            response_hold_ms=float(advanced.get("response_hold_ms", 0.0)),
            response_sustain=float(advanced.get("response_sustain", 0.0)),
            response_release_ms=float(advanced.get("response_release_ms", 420.0)),
            response_smoothing=float(advanced.get("response_smoothing", 0.2)),
            response_min=float(advanced.get("response_min", 0.0)),
            response_max=float(advanced.get("response_max", 1.0)),
            response_sensitivity=float(advanced.get("response_sensitivity", 1.0)),
            response_curve=float(advanced.get("response_curve", 1.0)),
            rhythmic_subdivision=int(advanced.get("rhythmic_subdivision", 1)),
            accent_weight=float(advanced.get("accent_weight", 0.0)),
            group_gain=float(advanced.get("group_gain", 1.0)),
            group_delay_ms=float(advanced.get("group_delay_ms", 0.0)),
            lighting_gain=float(advanced.get("lighting_gain", 1.0)),
            edge_glow_enabled=bool(advanced.get("edge_glow_enabled", False)),
            edge_glow_amount=float(advanced.get("edge_glow_amount", 0.0)),
            shimmer_enabled=bool(advanced.get("shimmer_enabled", role == "reflection")),
            shimmer_amount=float(advanced.get("shimmer_amount", 0.12 if role == "reflection" else 0.0)),
            section_response=float(advanced.get("section_response", 0.0)),
            atmospheric_motion_mode=str(advanced.get("atmospheric_motion_mode", "auto")),
            atmospheric_expansion_percent=float(advanced.get("atmospheric_expansion_percent", 0.0)),
            generated_clip_path=str(advanced.get("generated_clip_path", "")),
            generated_clip_max_seconds=float(advanced.get("generated_clip_max_seconds", 6.0)),
            generated_clip_overlap_seconds=float(advanced.get("generated_clip_overlap_seconds", 0.6)),
            smoke_effect_strength=float(advanced.get("smoke_effect_strength", 1.0)),
            foreground_protection=bool(advanced.get("foreground_protection", True)),
        )


def _auto_target_settings(object_class: str) -> dict:
    presets = {
        "light_source": {
            "object_name": "light source", "animation_prompt": "bounded emitting light pulsing gently",
            "target_role": "light_source", "envelope_group": "linked_light", "audio_driver": "beat",
            "motion_type": "still", "on_beat_flicker": 0.42, "off_beat_flicker": 0.10,
            "max_luminance_change": 0.10, "glow_strength": 0.24, "glow_radius_px": 24.0,
        },
        "illumination": {
            "object_name": "illumination", "animation_prompt": "illumination linked to the nearby light source",
            "target_role": "illumination", "envelope_group": "linked_light", "audio_driver": "phrase",
            "motion_type": "still", "on_beat_flicker": 0.24, "off_beat_flicker": 0.10,
            "max_luminance_change": 0.07,
        },
        "atmosphere": {
            "object_name": "smoke fog or clouds", "animation_prompt": "atmosphere billowing slowly without camera motion",
            "target_role": "organic", "envelope_group": "atmosphere", "audio_driver": "slow",
            "motion_type": "billow", "on_beat_motion": 0.0, "off_beat_motion": 0.45,
            "max_luminance_change": 0.04, "atmospheric_expansion_percent": 18.0,
        },
        "smoke": {
            "object_name": "smoke", "animation_prompt": "smoke wisps billowing slowly without camera motion",
            "target_role": "organic", "envelope_group": "smoke", "audio_driver": "slow",
            "motion_type": "billow", "on_beat_motion": 0.0, "off_beat_motion": 0.90,
            "max_luminance_change": 0.035, "atmospheric_expansion_percent": 28.0,
        },
        "flame": {
            "object_name": "flame or fire", "animation_prompt": "flame flickering in place",
            "target_role": "light_source", "envelope_group": "flame", "audio_driver": "high",
            "motion_type": "sway", "on_beat_flicker": 0.34, "off_beat_flicker": 0.22,
            "off_beat_motion": 0.30, "max_luminance_change": 0.10, "glow_strength": 0.20,
        },
        "reflection": {
            "object_name": "reflection or shiny surface", "animation_prompt": "reflections shimmering in place",
            "target_role": "reflection", "envelope_group": "linked_light", "audio_driver": "high",
            "motion_type": "still", "on_beat_flicker": 0.30, "off_beat_flicker": 0.12,
            "max_luminance_change": 0.08, "shimmer_enabled": True, "shimmer_amount": 0.30,
        },
        "hair": {
            "object_name": "hair", "animation_prompt": "hair moving gently in a light breeze",
            "target_role": "organic", "envelope_group": "wind", "audio_driver": "slow",
            "motion_type": "sway", "off_beat_motion": 0.28,
        },
        "fabric": {
            "object_name": "fabric", "animation_prompt": "fabric moving softly in a light breeze",
            "target_role": "organic", "envelope_group": "wind", "audio_driver": "slow",
            "motion_type": "sway", "off_beat_motion": 0.32,
        },
        "person": {
            "object_name": "person", "animation_prompt": "very subtle body motion; no lip sync",
            "target_role": "organic", "envelope_group": "person", "audio_driver": "slow",
            "motion_type": "still", "off_beat_motion": 0.0,
        },
    }
    common = {
        "version": 2, "enabled": False, "mask_verified": False, "review_state": "proposed",
        "motion_source": "procedural", "on_beat_flicker": 0.0, "off_beat_flicker": 0.08,
        "on_beat_motion": 0.0, "off_beat_motion": 0.0, "generated_motion_strength": 0.85,
        "max_luminance_change": 0.03, "glow_strength": 0.0, "glow_radius_px": 0.0,
        "saturation_variation": 0.0, "hue_variation_degrees": 0.0,
        "secondary_audio_driver": "none", "secondary_driver_mix": 0.0,
        "response_attack_ms": 180.0, "response_decay_ms": 520.0, "response_hold_ms": 80.0,
        "response_sustain": 0.25, "response_release_ms": 900.0, "response_smoothing": 0.35,
        "response_min": 0.05, "response_max": 0.85, "response_sensitivity": 0.9,
        "response_curve": 1.0, "rhythmic_subdivision": 1, "accent_weight": 0.0,
        "group_gain": 0.9, "group_delay_ms": 0.0, "lighting_gain": 1.0,
        "edge_glow_enabled": False, "edge_glow_amount": 0.0,
        "shimmer_enabled": False, "shimmer_amount": 0.0, "section_response": 0.25,
        "atmospheric_motion_mode": "auto", "atmospheric_expansion_percent": 0.0,
        "generated_clip_path": "", "generated_clip_max_seconds": 6.0,
        "generated_clip_overlap_seconds": 0.6, "foreground_protection": True,
    }
    common.update(presets[object_class])
    return common


def _enforce_auto_target_behavior(target: dict) -> dict:
    """Apply non-negotiable class semantics to automatically discovered targets."""
    constrained = dict(target)
    if str(constrained.get("provenance", "")).casefold() != "auto_discovery":
        return constrained
    object_class = str(constrained.get("object_class", "")).casefold()
    lighting_minimums = {
        "light_source": (1.60, 0.45, 0.45),
        "illumination": (1.20, 0.35, 0.32),
        "reflection": (0.90, 0.25, 0.22),
        "flame": (1.50, 0.55, 0.40),
    }
    if object_class in lighting_minimums:
        # These targets may vary luminance, glow, color, or shimmer, but pixels
        # belonging to the fixture or reflected surface never translate.
        beat_flicker, ambient_flicker, luminance = lighting_minimums[object_class]
        constrained.update({
            "motion_type": "still", "on_beat_motion": 0.0, "off_beat_motion": 0.0,
            "on_beat_flicker": max(beat_flicker, float(constrained.get("on_beat_flicker", 0.0))),
            "off_beat_flicker": max(ambient_flicker, float(constrained.get("off_beat_flicker", 0.0))),
            "max_luminance_change": max(luminance, float(constrained.get("max_luminance_change", 0.0))),
            "audio_driver": "high" if object_class == "reflection" else "beat",
            "response_attack_ms": min(35.0, float(constrained.get("response_attack_ms", 35.0))),
            "response_decay_ms": min(160.0, float(constrained.get("response_decay_ms", 160.0))),
            "response_release_ms": min(220.0, float(constrained.get("response_release_ms", 220.0))),
            "response_smoothing": min(0.10, float(constrained.get("response_smoothing", 0.10))),
            "response_min": 0.0, "response_max": 1.0,
            "response_sensitivity": max(1.15, float(constrained.get("response_sensitivity", 1.0))),
            "motion_source": "procedural", "generated_motion_strength": 0.0,
            "generated_clip_path": "", "atmospheric_motion_mode": "procedural",
        })
    elif object_class in {"person", "people", "face", "human", "hair", "fabric"}:
        # Procedural warps cannot create credible articulated human motion.
        # Keep people as protected static content instead of sliding heads.
        constrained.update({
            "motion_type": "still", "on_beat_motion": 0.0, "off_beat_motion": 0.0,
            "on_beat_flicker": 0.0, "off_beat_flicker": 0.0,
            "motion_source": "procedural", "generated_motion_strength": 0.0,
            "generated_clip_path": "", "max_luminance_change": 0.0,
            "glow_strength": 0.0, "saturation_variation": 0.0,
            "hue_variation_degrees": 0.0, "atmospheric_motion_mode": "procedural",
        })
    elif object_class == "smoke":
        constrained.update({
            "motion_type": "billow", "on_beat_motion": 0.0,
            "off_beat_motion": max(0.90, float(constrained.get("off_beat_motion", 0.0))),
            "atmospheric_expansion_percent": max(
                28.0, float(constrained.get("atmospheric_expansion_percent", 0.0)),
            ),
            "foreground_protection": True,
        })
    return constrained


def _protect_auto_motion_overlaps(plans: list[dict]) -> list[str]:
    """Keep moving auto-atmosphere from warping static semantic classes."""
    import numpy as np

    protected_classes = {
        "light_source", "illumination", "reflection", "flame",
        "person", "people", "face", "human", "hair", "fabric",
    }
    protected_masks = [
        plan["source_layer"].mask
        for plan in plans
        if str(plan.get("provenance", "")).casefold() == "auto_discovery"
        and str(plan.get("object_class", "")).casefold() in protected_classes
    ]
    if not protected_masks:
        return []
    guard = np.maximum.reduce(protected_masks).astype(np.float32, copy=False)
    hard_guard = guard > 0.005
    selected = np.argwhere(guard > 0.005)
    if selected.size:
        y0, x0 = selected.min(axis=0)
        y1, x1 = selected.max(axis=0) + 1
        margin = max(2, round(min(guard.shape) * 0.006))
        guard = _dilated_layer(
            _Layer(guard, (int(x0), int(y0), int(x1), int(y1))), margin, 1.0,
        ).mask
        guard = np.maximum(guard, hard_guard.astype(np.float32))
    reports = []
    for plan in plans:
        if str(plan.get("provenance", "")).casefold() != "auto_discovery":
            continue
        if str(plan.get("object_class", "")).casefold() not in {"smoke", "atmosphere"}:
            continue
        if str(plan.get("motion_type", "still")).casefold() == "still":
            continue
        effect = np.asarray(plan["layer"].mask, dtype=np.float32)
        before = float(np.sum(effect))
        safe_effect = np.clip(effect * (1.0 - guard), 0.0, 1.0)
        safe_motion = np.clip(np.asarray(plan["motion_mask"], dtype=np.float32) * (1.0 - guard), 0.0, 1.0)
        plan["layer"] = _Layer(safe_effect, plan["layer"].bounds)
        plan["motion_mask"] = safe_motion
        excluded = 0.0 if before <= 1e-6 else max(0.0, min(1.0, 1.0 - float(np.sum(safe_effect)) / before))
        label = plan.get("target_id") or plan.get("object_name") or "atmosphere"
        reports.append(f"{label}: protected {excluded:.1%} overlapping light/person detail from spatial motion")
    return reports


def _subtract_protected_mask(mask, protected, dilation_percent: float = 1.25):
    """Remove people/face pixels plus a small safety margin from an effect mask."""
    import numpy as np
    import torch
    from PIL import Image, ImageFilter

    effect = mask.detach().to("cpu", dtype=torch.float32)
    guard = protected.detach().to("cpu", dtype=torch.float32)
    if effect.ndim == 3:
        effect = effect[0]
    if guard.ndim == 3:
        guard = guard[0]
    if guard.shape != effect.shape:
        import torch.nn.functional as functional

        guard = functional.interpolate(
            guard[None, None], size=effect.shape[-2:], mode="bilinear", align_corners=False,
        )[0, 0]
    radius = max(1, round(min(effect.shape[-2:]) * max(0.0, float(dilation_percent)) / 100.0))
    size = radius * 2 + 1
    expanded = np.asarray(
        Image.fromarray(np.clip(guard.numpy() * 255.0, 0, 255).astype(np.uint8), "L").filter(
            ImageFilter.MaxFilter(size=size)
        ),
        dtype=np.float32,
    ) / 255.0
    return effect * torch.from_numpy(np.clip(1.0 - expanded, 0.0, 1.0))


def _manifest_preview(image, targets):
    import numpy as np
    import torch
    from PIL import Image, ImageDraw

    pixels = _image_pixels(image)
    preview = Image.fromarray(pixels, "RGB").convert("RGBA")
    colors = [(255, 194, 46), (82, 206, 255), (170, 120, 255), (255, 99, 71), (87, 220, 150)]
    for index, target in enumerate(targets):
        encoded = target.get("mask_png_base64")
        if not encoded:
            continue
        mask = _mask_from_png_base64(encoded).numpy()
        if mask.shape != pixels.shape[:2]:
            mask = np.asarray(
                Image.fromarray((mask * 255).astype(np.uint8), "L").resize((pixels.shape[1], pixels.shape[0]), Image.Resampling.BILINEAR),
                dtype=np.float32,
            ) / 255.0
        color = colors[index % len(colors)]
        alpha = Image.fromarray(np.clip(mask * 88.0, 0, 88).astype(np.uint8), "L")
        overlay = Image.new("RGBA", preview.size, (*color, 0))
        overlay.putalpha(alpha)
        preview = Image.alpha_composite(preview, overlay)
        selected = np.argwhere(mask > 0.10)
        if selected.size:
            y0, x0 = selected.min(axis=0)
            y1, x1 = selected.max(axis=0) + 1
            draw = ImageDraw.Draw(preview)
            draw.rectangle((int(x0), int(y0), int(x1), int(y1)), outline=(*color, 255), width=max(2, pixels.shape[1] // 480))
            draw.text((int(x0) + 3, int(y0) + 3), str(target.get("object_class", target.get("target_id", "target"))), fill=(*color, 255))
    return torch.from_numpy(np.asarray(preview.convert("RGB"), dtype=np.float32) / 255.0)[None, ...]


def _auto_discover_response(manifest_text: str, preview, report: str, action: str, show_preview: bool):
    """Return graph outputs plus node-local UI state and an optional temp preview."""
    ui = {
        "infra_choir_setup": [{
            "action": str(action),
            "status": str(report),
            "manifest": str(manifest_text),
        }],
    }
    if show_preview:
        from PIL import Image

        pixels = _image_pixels(preview)
        height, width = pixels.shape[:2]
        try:
            import folder_paths

            temporary_root = Path(folder_paths.get_temp_directory())
            output_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
                "infra_choir/discovery_preview", temporary_root, width, height,
            )
        except (ImportError, AttributeError):
            output_folder = Path(tempfile.gettempdir()) / "infra_choir"
            output_folder.mkdir(parents=True, exist_ok=True)
            filename, counter, subfolder = "discovery_preview", 1, "infra_choir"
        output_folder = Path(output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)
        output_file = f"{filename}_{counter:05}_.png"
        Image.fromarray(pixels, "RGB").save(output_folder / output_file, format="PNG")
        ui["images"] = [{"filename": output_file, "subfolder": subfolder, "type": "temp"}]
    return {"ui": ui, "result": (manifest_text, preview, str(report))}


def approve_infra_choir_discovery(
    manifest_text: str,
    manifest_path: str,
    preserve_reviewed_targets: bool = True,
    approve_all: bool = True,
):
    """Approve every visible discovery candidate and persist it atomically."""
    text = str(manifest_text or "").strip()
    if not text:
        raise ValueError("Run discovery before pushing candidates into the flow.")
    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Candidate manifest is invalid JSON: {exc}") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("targets"), list):
        raise ValueError("Candidate manifest must be an object with a targets list.")
    identity = manifest.get("image") or {}
    if not isinstance(identity, dict) or not identity.get("sha256"):
        raise ValueError("Candidate manifest is missing its source-image fingerprint.")

    approved = []
    for item in manifest["targets"]:
        if not isinstance(item, dict) or not item.get("mask_png_base64"):
            raise ValueError("Every discovered target must contain an embedded mask_png_base64.")
        _mask_from_png_base64(item["mask_png_base64"])
        candidate = dict(item)
        if approve_all:
            candidate["enabled"] = True
            candidate["mask_verified"] = True
            candidate["review_state"] = "approved"
        approved.append(candidate)
    manifest["version"] = 1
    manifest["targets"] = approved

    destination = _manifest_path(manifest_path)
    if bool(preserve_reviewed_targets) and destination.is_file():
        try:
            prior = json.loads(destination.read_text(encoding="utf-8"))
            same_image = (prior.get("image") or {}).get("sha256") == identity.get("sha256")
            incoming = {str(item.get("stable_id") or item.get("target_id")) for item in approved}
            if same_image:
                approved.extend(
                    item for item in prior.get("targets", []) if isinstance(item, dict)
                    and str(item.get("stable_id") or item.get("target_id")) not in incoming
                    and str(item.get("review_state", "")).casefold() in {"approved", "edited", "locked"}
                )
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    saved_text = json.dumps(manifest, indent=2, sort_keys=True)
    temporary.write_text(saved_text + "\n", encoding="utf-8")
    temporary.replace(destination)
    return manifest, saved_text, destination


class InfraChoirAutoDiscover:
    """Explicit setup-time target discovery with review/apply/reset persistence."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image": ("IMAGE",),
            "discovery_profile": ([
                "Primary: lights + reflections + smoke/fog/flame",
                "Expanded: primary + people/hair/fabric",
            ],),
            "max_candidates": ("INT", {"default": 8, "min": 1, "max": 16}),
            "action": (["idle", "discover", "apply_reviewed_manifest", "reset_saved_manifest"], {"default": "idle"}),
            "manifest_path": ("STRING", {"default": "infra_choir/auto_targets.json"}),
            "reviewed_manifest_json": ("STRING", {"multiline": True, "default": ""}),
            "preserve_reviewed_targets": ("BOOLEAN", {"default": True}),
        }}

    RETURN_TYPES = ("STRING", "IMAGE", "STRING")
    RETURN_NAMES = ("candidate_manifest", "annotated_preview", "discovery_report")
    FUNCTION = "run"
    CATEGORY = "audio/infra choir/setup"
    OUTPUT_NODE = True
    DESCRIPTION = "Setup only. Discover previews first-class smoke plus lights/reflections/fog/flame; use Push This Discovery Into Flow, then render normally."

    def run(self, image, discovery_profile, max_candidates, action, manifest_path, reviewed_manifest_json, preserve_reviewed_targets):
        identity = _image_identity(image)
        destination = _manifest_path(manifest_path)
        action = str(action)
        if action == "idle":
            report = "IDLE — safety no-op: no discovery, manifest write, or reset was performed. Choose Discover and Queue Selected Output to analyze the image."
            return _auto_discover_response("", image[:1], report, action, False)
        if action == "reset_saved_manifest":
            existed = destination.exists()
            destination.unlink(missing_ok=True)
            report = f"RESET — {'removed' if existed else 'no manifest at'} {destination}"
            return _auto_discover_response("", image[:1], report, action, False)
        if action == "apply_reviewed_manifest":
            text = str(reviewed_manifest_json or "").strip()
            if not text:
                raise ValueError("Paste the reviewed candidate manifest before selecting apply_reviewed_manifest.")
            try:
                manifest = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"reviewed_manifest_json is invalid JSON: {exc}") from exc
            if not isinstance(manifest, dict) or not isinstance(manifest.get("targets"), list):
                raise ValueError("Reviewed manifest must be an object with a targets list.")
            supplied = manifest.get("image") or {}
            if supplied.get("sha256") not in {None, identity["sha256"]}:
                raise ValueError("Reviewed manifest belongs to a different source image.")
            manifest["version"], manifest["image"] = 1, identity
            manifest, manifest_text, destination = approve_infra_choir_discovery(
                json.dumps(manifest), manifest_path, preserve_reviewed_targets, approve_all=False,
            )
            preview = _manifest_preview(image, manifest["targets"])
            report = f"APPLIED — {len(manifest['targets'])} reviewed target(s) saved to {destination}"
            return _auto_discover_response(manifest_text, preview, report, action, True)

        specs = [
            ("light_source", "bright light source sun lamp flame", "box 0 0 1 1", 0.72),
            ("illumination", "lit haze or illuminated area", "box 0 0 1 1", 0.58),
            ("smoke", "smoke", "box 0 0 1 1", 0.85),
            ("atmosphere", "fog mist haze or clouds", "box 0 0 1 1", 0.52),
            ("flame", "flame or fire", "box 0 0 1 1", 0.72),
            ("reflection", "reflection on water metal or glass", "box 0 .25 1 1", 0.62),
        ]
        expanded_profile = str(discovery_profile) in {
            "Expanded: primary + people/hair/fabric",
            "include_optional_people_hair_fabric",
        }
        if expanded_profile:
            specs.extend([
                ("hair", "hair", "box 0 0 1 1", 0.68),
                ("fabric", "fabric scarf flag or clothing", "box 0 0 1 1", 0.66),
                ("person", "person or face", "box 0 0 1 1", 0.74),
            ])
        detector = VisualizerSemanticObjectDetector()
        targets, reports = [], []
        person_protection = None
        if detector._semantic_assets_available():
            protection_reports = []
            for protection_query in ("person", "human face"):
                try:
                    protection, _, _, protection_report = detector.detect(
                        image, protection_query, "box 0 0 1 1", 0.65, 12, 2.0, "semantic_only",
                    )
                    person_protection = (
                        protection if person_protection is None
                        else __import__("torch").maximum(person_protection, protection)
                    )
                    protection_reports.append(protection_report)
                except (RuntimeError, ValueError) as exc:
                    protection_reports.append(f"{protection_query}: unavailable ({exc})")
            reports.append("human protection: " + " | ".join(protection_reports))
        for object_class, query, area, sensitivity in specs[: int(max_candidates)]:
            region_limit = 8 if object_class == "smoke" else 4
            padding = 2.5 if object_class == "smoke" else 1.5
            mask, _, regions, report = detector.detect(
                image, query, area, sensitivity, region_limit, padding, "semantic_or_heuristic",
            )
            if person_protection is not None and object_class not in {"person", "hair", "fabric"}:
                mask = _subtract_protected_mask(mask, person_protection, 2.5)
            if float(mask.max()) <= 0.01:
                reports.append(f"{object_class}: no usable region after human-protection exclusion")
                continue
            encoded = _mask_png_base64(mask)
            stable = hashlib.sha256((identity["sha256"] + object_class + encoded).encode("utf-8")).hexdigest()[:16]
            item = _auto_target_settings(object_class)
            item.update({
                "stable_id": f"auto_{object_class}_{stable}", "target_id": f"auto_{object_class}_{stable}",
                "object_class": object_class, "image_sha256": identity["sha256"],
                "mask_png_base64": encoded, "suggested_regions": regions,
                "provenance": "auto_discovery", "priority": "low" if object_class in {"hair", "fabric", "person"} else "normal",
                "lip_sync": False,
            })
            item = _enforce_auto_target_behavior(item)
            targets.append(item)
            reports.append(f"{object_class}: {report}")
        manifest = {"version": 1, "image": identity, "targets": targets}
        profile_report = (
            "DISCOVERED — primary target set: first-class smoke, lights, illumination, reflections, fog/mist/cloud atmosphere, and flame/fire"
            + ("; optional people/hair/fabric also enabled" if expanded_profile else "")
            + f". Produced {len(targets)} candidate mask(s)."
        )
        manifest_text = json.dumps(manifest, indent=2, sort_keys=True)
        return _auto_discover_response(
            manifest_text, _manifest_preview(image, targets),
            profile_report + "\n" + "\n".join(reports), action, True,
        )


class InfraChoirApprovedTargets:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image": ("IMAGE",), "manifest_path": ("STRING", {"default": "infra_choir/auto_targets.json"}),
            "enabled": ("BOOLEAN", {"default": True}),
            "stale_image_policy": (["empty", "error"], {"default": "empty"}),
        }}

    RETURN_TYPES = ("LOCAL_VISUALIZER_TARGETS", "STRING")
    RETURN_NAMES = ("targets", "status")
    FUNCTION = "load"
    CATEGORY = "audio/infra choir"
    DESCRIPTION = "Load only reviewed, image-matched targets; missing or stale manifests predictably return an empty collection."

    def load(self, image, manifest_path, enabled, stale_image_policy="empty"):
        if not bool(enabled):
            return (), "disabled: empty auto-target collection"
        path = _manifest_path(manifest_path)
        if not path.is_file():
            return (), f"no manifest: {path}; empty auto-target collection"
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            if str(stale_image_policy) == "error":
                raise ValueError(f"Could not read approved-target manifest: {exc}") from exc
            return (), f"invalid manifest: {exc}; empty auto-target collection"
        identity = _image_identity(image)
        if (manifest.get("image") or {}).get("sha256") != identity["sha256"]:
            message = "stale manifest: source-image fingerprint mismatch"
            if str(stale_image_policy) == "error":
                raise ValueError(message)
            return (), message + "; empty auto-target collection"
        loaded, skipped = [], 0
        for item in manifest.get("targets", []):
            if not isinstance(item, dict) or str(item.get("review_state", "")).casefold() not in {"approved", "edited", "locked"}:
                skipped += 1
                continue
            try:
                mask = _mask_from_png_base64(item.get("mask_png_base64", ""))
            except ValueError:
                skipped += 1
                continue
            target = dict(item)
            target.update({
                "mask": mask, "generated_motion": None, "enabled": bool(item.get("enabled", True)),
                "mask_verified": True, "configuration_valid": bool(item.get("enabled", True)),
                "configuration_diagnostic": "ready", "image_identity": identity["sha256"],
                "effect_modes": _target_effect_modes(item.get("object_name", ""), item.get("animation_prompt", "")),
            })
            target = _enforce_auto_target_behavior(target)
            loaded.append(target)
        return tuple(loaded), f"loaded {len(loaded)} reviewed target(s); skipped {skipped} unreviewed/invalid target(s)"


def _target_masks_overlap(left, right) -> float:
    import torch
    import torch.nn.functional as functional

    first, second = left.get("mask"), right.get("mask")
    if first is None or second is None:
        return 0.0
    first = first.detach().to("cpu", dtype=torch.float32)
    second = second.detach().to("cpu", dtype=torch.float32)
    if first.ndim == 3:
        first = first[0]
    if second.ndim == 3:
        second = second[0]
    if second.shape != first.shape:
        second = functional.interpolate(second[None, None], size=first.shape[-2:], mode="bilinear", align_corners=False)[0, 0]
    first, second = first > 0.15, second > 0.15
    union = torch.logical_or(first, second).sum().item()
    return 0.0 if not union else float(torch.logical_and(first, second).sum().item() / union)


class InfraChoirTargetMerge:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "manual_targets": ("LOCAL_VISUALIZER_TARGETS",), "auto_targets": ("LOCAL_VISUALIZER_TARGETS",),
            "merge_policy": (["auto_only", "manual_only", "manual_wins", "auto_wins", "keep_both"], {"default": "auto_only"}),
            "overlap_threshold": ("FLOAT", {"default": 0.45, "min": 0.0, "max": 1.0, "step": 0.05}),
        }}

    RETURN_TYPES = ("LOCAL_VISUALIZER_TARGETS", "STRING")
    RETURN_NAMES = ("targets", "merge_report")
    FUNCTION = "merge"
    CATEGORY = "audio/infra choir"
    DESCRIPTION = "Deterministically combine manual and reviewed auto targets with stable-ID/class/mask collision handling."

    def merge(self, manual_targets, auto_targets, merge_policy, overlap_threshold=0.45):
        manual, automatic = list(manual_targets or ()), list(auto_targets or ())
        policy = str(merge_policy)
        if policy == "manual_only":
            return tuple(manual), f"manual only: {len(manual)} target(s)"
        if policy == "auto_only":
            return tuple(automatic), f"auto only: {len(automatic)} target(s)"
        if policy == "keep_both":
            return tuple(manual + automatic), f"kept both: {len(manual)} manual + {len(automatic)} auto"
        winners, candidates = (manual, automatic) if policy == "manual_wins" else (automatic, manual)
        result, dropped = list(winners), []
        winner_ids = {str(item.get("stable_id") or item.get("target_id") or "") for item in winners}
        for candidate in candidates:
            identifier = str(candidate.get("stable_id") or candidate.get("target_id") or "")
            candidate_class = str(candidate.get("object_class") or candidate.get("target_role") or "").casefold()
            collision = identifier and identifier in winner_ids
            if not collision:
                for winner in winners:
                    winner_class = str(winner.get("object_class") or winner.get("target_role") or "").casefold()
                    if candidate_class and candidate_class == winner_class and _target_masks_overlap(candidate, winner) >= float(overlap_threshold):
                        collision = True
                        break
            if collision:
                dropped.append(identifier or candidate.get("object_name", "unnamed"))
            else:
                result.append(candidate)
        return tuple(result), f"{policy}: {len(result)} retained; dropped {len(dropped)} collision(s)" + (f" ({', '.join(dropped)})" if dropped else "")


class InfraChoirVisualizer:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "audio": ("AUDIO",),
                "targets": ("LOCAL_VISUALIZER_TARGETS",),
                "fps": ("INT", {"default": 16, "min": 8, "max": 30}),
                "delivery_resolution": (["720p", "1080p", "source"], {"default": "1080p"}),
                "pattern_key": ("INT", {"default": 20261009, "min": 0, "max": 0x7FFFFFFF}),
                "maximum_stabilization_percent": ("FLOAT", {"default": 4.0, "min": 0.0, "max": 10.0, "step": 0.5, "tooltip": "Maximum per-frame translation correction. Set to 0 to preserve the generated clip exactly and disable stabilization."}),
                "apply_brand_logo": ("BOOLEAN", {"default": False}),
                "brand_logo_width_percent": ("FLOAT", {"default": 10.0, "min": 2.0, "max": 40.0, "step": 1.0}),
                "brand_logo_opacity": ("FLOAT", {"default": 0.68, "min": 0.05, "max": 1.0, "step": 0.01}),
                "apply_wordmark": ("BOOLEAN", {"default": False}),
                "wordmark_width_percent": ("FLOAT", {"default": 32.0, "min": 5.0, "max": 80.0, "step": 1.0}),
                "wordmark_opacity": ("FLOAT", {"default": 0.95, "min": 0.05, "max": 1.0, "step": 0.01}),
                "overlay_margin_px": ("INT", {"default": 24, "min": 0, "max": 200}),
                "title_card_enabled": ("BOOLEAN", {"default": True}),
                "band_name": ("STRING", {"default": "Infra Choir"}),
                "song_title": ("STRING", {"default": "Bella Ciao"}),
                "title_card_image": (_title_card_choices(), {"default": _GENERATED_TITLE_CARD, "image_upload": True}),
                "title_card_placement": (["center", "upper_center", "lower_center"], {"default": "center"}),
                "title_card_start_seconds": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 3600.0, "step": 0.1}),
                "title_card_duration_seconds": ("FLOAT", {"default": 4.5, "min": 0.0, "max": 60.0, "step": 0.1}),
                "title_card_fade_seconds": ("FLOAT", {"default": 0.55, "min": 0.0, "max": 5.0, "step": 0.05}),
                "title_sparkle_enabled": ("BOOLEAN", {"default": True}),
                "title_sparkle_strength": ("FLOAT", {"default": 0.55, "min": 0.0, "max": 1.0, "step": 0.05}),
                "title_sparkle_audio_response": ("FLOAT", {"default": 0.30, "min": 0.0, "max": 1.0, "step": 0.05}),
                "eq_enabled": ("BOOLEAN", {"default": True}),
                "eq_mode": (["spectrum_bars", "continuous_waveform"], {"default": "spectrum_bars"}),
                "eq_height_percent": ("FLOAT", {"default": 11.0, "min": 4.0, "max": 18.0, "step": 0.5}),
                "eq_opacity": ("FLOAT", {"default": 0.46, "min": 0.0, "max": 0.85, "step": 0.01}),
                "eq_color": ("STRING", {"default": "#8E1325"}),
                "eq_smoothing": ("FLOAT", {"default": 0.72, "min": 0.0, "max": 0.98, "step": 0.01}),
                "organic_motion_expansion_percent": ("FLOAT", {"default": 2.5, "min": 0.0, "max": 8.0, "step": 0.25}),
                "title_card_source_visibility": ("FLOAT", {"default": 0.20, "min": 0.05, "max": 0.50, "step": 0.01}),
                "brand_logo_image": (_optional_overlay_choices(), {"default": _NO_OVERLAY_IMAGE}),
                "output_prefix": ("STRING", {"default": "infra_choir/render"}),
            },
            "optional": {
                "brand_logo": ("IMAGE",),
                "brand_logo_mask": ("MASK",),
                "wordmark": ("IMAGE",),
                "wordmark_mask": ("MASK",),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("output_path", "qa_report")
    OUTPUT_NODE = True
    FUNCTION = "render"
    CATEGORY = "audio/infra choir"
    DESCRIPTION = "Render a fixed-frame hybrid visualizer with linked local lighting and optional stabilized generated motion."

    @staticmethod
    def _audio_drive(features, frame_index: int, driver: str) -> float:
        if driver == "beat":
            return float(0.72 * features["beat"][frame_index] + 0.28 * features["onset"][frame_index])
        return float(features.get(driver, features["energy"])[frame_index])

    def render(
        self, image, audio, targets, fps, delivery_resolution, pattern_key,
        maximum_stabilization_percent, apply_brand_logo, brand_logo_width_percent,
        brand_logo_opacity, apply_wordmark, wordmark_width_percent, wordmark_opacity,
        overlay_margin_px, title_card_enabled, band_name, song_title, title_card_image,
        title_card_placement, title_card_start_seconds, title_card_duration_seconds,
        title_card_fade_seconds, title_sparkle_enabled, title_sparkle_strength,
        title_sparkle_audio_response, eq_enabled, eq_mode, eq_height_percent,
        eq_opacity, eq_color, eq_smoothing, organic_motion_expansion_percent,
        title_card_source_visibility, brand_logo_image, output_prefix, brand_logo=None, brand_logo_mask=None,
        wordmark=None, wordmark_mask=None, **enhancements,
    ):
        import folder_paths
        import numpy as np
        import time
        from PIL import Image

        render_started = time.perf_counter()

        try:
            from comfy.utils import ProgressBar
        except ImportError:
            ProgressBar = None
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("FFmpeg must be available on PATH for Infra Choir rendering.")

        enhanced = bool(enhancements.get("enhancements_enabled", False))
        if enhancements and not enhanced:
            # The enhanced node's master switch is a strict production-regression
            # path, including the original workflow's EQ presentation defaults.
            eq_mode = "spectrum_bars"
            eq_height_percent = 11.0
            eq_opacity = 0.46
        all_targets = tuple(targets or ())
        if enhancements and not bool(enhancements.get("auto_targets_enabled", True)):
            all_targets = tuple(target for target in all_targets if target.get("provenance") != "auto_discovery")
        diagnostics = []
        usable = []
        for target in all_targets:
            label = target.get("target_id") or target.get("object_name") or "unnamed"
            if not target.get("enabled"):
                diagnostics.append(f"{label}: disabled")
            elif not target.get("configuration_valid"):
                diagnostics.append(f"{label}: {target.get('configuration_diagnostic', 'invalid configuration')}")
            else:
                usable.append(target)
        if not usable:
            raise ValueError("No usable targets. Enable and verify at least one non-empty target; disabled and incomplete lanes are safe to leave connected.")

        source = Image.fromarray(_image_pixels(image), "RGB")
        source_width, source_height = source.size
        sizes = {"720p": (1280, 720), "1080p": (1920, 1080), "source": (source_width, source_height)}
        if delivery_resolution not in sizes:
            raise ValueError(f"Unsupported delivery resolution: {delivery_resolution}")
        width, height = sizes[delivery_resolution]
        if source.size != (width, height):
            source = source.resize((width, height), Image.Resampling.LANCZOS)
        base = np.asarray(source, dtype=np.uint8)

        motion_cache = {}
        plans = []
        for index, raw_target in enumerate(usable):
            target = _enforce_auto_target_behavior(raw_target)
            layer = _prepare_layer(target["mask"], width, height)
            label = target.get("target_id") or target["object_name"]
            if layer.bounds is None:
                diagnostics.append(f"{label}: skipped empty verified mask")
                continue
            generated_frames = ()
            motion_report = None
            requested_generated = target.get("motion_source") in {"generated_clip", "generated_then_procedural"}
            motion_clip = target.get("generated_motion")
            if requested_generated and motion_clip is not None:
                cache_key = id(motion_clip)
                if cache_key not in motion_cache:
                    motion_cache[cache_key] = _prepare_generated_motion(
                        motion_clip, width, height, base, float(maximum_stabilization_percent) / 100.0,
                    )
                generated_frames, motion_report = motion_cache[cache_key]
            cached_path = str(target.get("generated_clip_path", "")).strip()
            atmospheric_mode = str(target.get("atmospheric_motion_mode", "auto"))
            requested_cached = atmospheric_mode in {"cached_clip", "cached_clip_then_procedural"} or (atmospheric_mode == "auto" and bool(cached_path))
            if enhanced and atmospheric_mode == "cached_clip" and not cached_path:
                raise ValueError(
                    f"{label}: atmospheric motion mode requires a cached clip, but Generated clip path is blank. "
                    "Choose procedural/cached-then-procedural or select an approved motion asset."
                )
            if enhanced and bool(enhancements.get("generated_clip_cache_enabled", True)) and requested_cached and cached_path:
                try:
                    generated_frames, motion_report = _load_cached_motion_file(
                        cached_path, width, height, base, float(maximum_stabilization_percent) / 100.0,
                        int(fps), float(target.get("generated_clip_max_seconds", 6.0)),
                    )
                except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
                    if atmospheric_mode == "cached_clip":
                        raise ValueError(f"{label}: required cached motion clip is unusable: {exc}") from exc
                    diagnostics.append(f"{label}: cached clip unavailable ({exc}); procedural fallback used")
            if requested_generated and not generated_frames and not requested_cached:
                if motion_clip is None:
                    diagnostics.append(f"{label}: generated clip not connected; procedural fallback used")
                else:
                    diagnostics.append(f"{label}: generated clip has fewer than two frames; procedural fallback used")
            role = target.get("target_role", "organic")
            motion_type = str(target.get("motion_type", "drift"))
            expansion_radius = 0
            composite_layer = layer
            if role == "organic" and motion_type != "still":
                expansion_radius = round(height * min(8.0, max(0.0, float(organic_motion_expansion_percent))) / 100.0)
                if enhanced and bool(enhancements.get("expansive_atmosphere_enabled", False)) and motion_type == "billow":
                    local_percent = min(50.0, max(0.0, float(target.get("atmospheric_expansion_percent", 0.0))))
                    lx0, ly0, lx1, ly1 = layer.bounds
                    mask_extent = max(1, lx1 - lx0, ly1 - ly0)
                    local_radius = round(mask_extent * local_percent / 100.0)
                    expansion_radius = max(expansion_radius, local_radius)
                if bool(target.get("foreground_protection", False)):
                    composite_layer = _protected_expansion_layer(layer, expansion_radius, max(1.0, height / 720.0), base)
                else:
                    composite_layer = _dilated_layer(layer, expansion_radius, max(1.0, height / 720.0))
            x0, y0, x1, y1 = composite_layer.bounds
            glow_radius = float(target.get("glow_radius_px", 0.0)) * height / 1080.0
            if enhanced:
                glow_radius *= min(2.0, math.sqrt(max(0.0, float(target.get("lighting_gain", 1.0)))))
            glow_layer = _emissive_glow_layer(layer, glow_radius) if role == "light_source" else None
            phase_key = target.get("envelope_group", label)
            phase_offset = 0.0 if role in {"light_source", "illumination", "reflection"} else index * 0.173
            atmosphere_description = " ".join((
                str(target.get("object_class", "")), str(target.get("object_name", "")),
                str(target.get("animation_prompt", "")),
            )).casefold()
            non_geometric_atmosphere = motion_type == "billow" and any(
                word in atmosphere_description for word in ("smoke", "fog", "mist", "steam", "cloud", "haze")
            )
            if expansion_radius and non_geometric_atmosphere:
                motion_mask = composite_layer.mask
            elif expansion_radius:
                motion_mask = layer.mask
            else:
                motion_mask = _motion_interior(layer.mask, round(8.0 * max(0.75, height / 720.0)))
            plans.append({
                **target,
                "layer": composite_layer,
                "source_layer": layer,
                "expansion_radius": expansion_radius,
                "glow_layer": glow_layer,
                "generated_frames": generated_frames,
                "motion_report": motion_report,
                "motion_mask": motion_mask,
                "non_geometric_atmosphere": non_geometric_atmosphere,
                "rows": np.arange(y1 - y0, dtype=np.float32)[:, None, None],
                "columns": np.arange(x1 - x0, dtype=np.float32)[None, :, None],
                "phase": (_stable_phase(phase_key) + int(pattern_key) * 0.0001 + phase_offset) % math.tau,
                "edge_alpha": _masked_edge_alpha(
                    layer.mask,
                    max(0.75, float(target.get("glow_radius_px", 8.0)) * height / 1080.0 * 0.18),
                )[y0:y1, x0:x1] if enhanced and bool(target.get("edge_glow_enabled", False)) else None,
            })
            detail = f"{label}: ready ({role}, {target.get('motion_source', 'procedural')})"
            if expansion_radius:
                detail += f"; organic support expanded {expansion_radius}px beyond verified mask"
            if motion_report:
                detail += f"; stabilized {motion_report['frames']} frames, max shift {motion_report['max_shift_px']:.1f}px"
                if "source_similarity" in motion_report:
                    detail += f", source match {motion_report['source_similarity']:.3f}"
                if motion_report["clipped_shifts"]:
                    detail += f", {motion_report['clipped_shifts']} bounded shift(s)"
            diagnostics.append(detail)
        diagnostics.extend(_protect_auto_motion_overlaps(plans))
        if not plans:
            raise ValueError("Every enabled target produced an empty mask.")

        overlays = []
        wordmark_outline_mask = None
        margin = round(float(overlay_margin_px) * width / 1920)
        if bool(apply_wordmark):
            if wordmark is None or wordmark_mask is None:
                generated_wordmark, wordmark_outline_mask, wordmark_report = _render_generated_wordmark(
                    width, height, band_name, song_title,
                    max(2, round(width * float(wordmark_width_percent) / 100.0)),
                    float(wordmark_opacity), margin,
                )
                overlays.append(generated_wordmark)
                diagnostics.append(f"wordmark: {wordmark_report}")
            else:
                overlays.append(_prepare_overlay(wordmark, wordmark_mask, max(2, round(width * float(wordmark_width_percent) / 100.0)), float(wordmark_opacity), margin, margin))
                diagnostics.append("wordmark: external image override")
        else:
            diagnostics.append("wordmark: disabled")
        if bool(apply_brand_logo):
            if brand_logo is not None and brand_logo_mask is not None:
                target_width = max(2, round(width * float(brand_logo_width_percent) / 100.0))
                rgb, _ = _overlay_pixels(brand_logo, brand_logo_mask)
                target_height = max(1, round(rgb.shape[0] * target_width / rgb.shape[1]))
                overlays.append(_prepare_overlay(brand_logo, brand_logo_mask, target_width, float(brand_logo_opacity), width - target_width - margin, height - target_height - margin))
                diagnostics.append("brand logo: connected image/mask override")
            elif str(brand_logo_image or _NO_OVERLAY_IMAGE) != _NO_OVERLAY_IMAGE:
                try:
                    target_width = max(2, round(width * float(brand_logo_width_percent) / 100.0))
                    selected_overlay = _load_overlay_selection(str(brand_logo_image), target_width, float(brand_logo_opacity), 0, 0)
                    target_height = selected_overlay[0].shape[0]
                    overlays.append((selected_overlay[0], selected_overlay[1], width - target_width - margin, height - target_height - margin))
                    diagnostics.append(f"brand logo: selected {brand_logo_image}")
                except (FileNotFoundError, OSError, ValueError) as exc:
                    diagnostics.append(f"brand logo: selected image unavailable ({exc}); skipped")
            else:
                diagnostics.append("brand logo: enabled but no selected or connected image; skipped")

        title_card = None
        title_outline_mask = None
        if bool(title_card_enabled):
            selected_card = str(title_card_image or _GENERATED_TITLE_CARD)
            if selected_card != _GENERATED_TITLE_CARD:
                try:
                    title_card, title_outline_mask, title_report = _load_external_title_card(selected_card, width, height)
                except (FileNotFoundError, OSError, ValueError) as exc:
                    diagnostics.append(f"title card: external image unavailable ({exc}); generated text fallback used")
                    title_card, title_outline_mask, title_report = _render_generated_title_card(
                        base, band_name, song_title, title_card_placement,
                        round(height * float(eq_height_percent) / 100.0) if bool(eq_enabled) else 0,
                        float(title_card_source_visibility),
                        str(enhancements.get("title_text_alignment", "center")),
                    )
            else:
                title_card, title_outline_mask, title_report = _render_generated_title_card(
                    base, band_name, song_title, title_card_placement,
                    round(height * float(eq_height_percent) / 100.0) if bool(eq_enabled) else 0,
                    float(title_card_source_visibility),
                    str(enhancements.get("title_text_alignment", "center")),
                )
            diagnostics.append(f"title card: {title_report}")
        else:
            diagnostics.append("title card: disabled")
        eq_color_rgb = _parse_overlay_color(eq_color) if bool(eq_enabled) else None
        diagnostics.append(
            f"EQ overlay: {eq_mode}, {float(eq_height_percent):.1f}% height, {float(eq_opacity):.2f} opacity"
            if bool(eq_enabled) else "EQ overlay: disabled"
        )
        if enhanced:
            diagnostics.append(
                "enhancements: shared cached STFT, target ADSHR drivers, selective edge glow, bounded shimmer, and section dynamics"
            )

        prefix = _safe_name(str(output_prefix).replace("\\", "/").split("/")[-1])
        parent = Path(str(output_prefix).replace("\\", "/")).parent.as_posix()
        save_prefix = f"{parent}/{prefix}" if parent not in {"", "."} else prefix
        output_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(save_prefix, folder_paths.get_output_directory(), width, height)
        output_file = f"{filename}_{counter:05}_.mp4"
        output_path = Path(output_folder) / output_file
        partial_path = output_path.with_name(output_path.stem + ".part.mp4")

        with tempfile.TemporaryDirectory(prefix="infra-choir-") as temporary:
            audio_path = Path(temporary) / "audio.wav"
            duration = _write_audio_wav(audio, audio_path)
            analysis_started = time.perf_counter()
            if enhanced:
                ultra_count = int(enhancements.get("eq_ultra_band_count", 0))
                analysis_band_count = ultra_count if ultra_count in {1024, 2048} else int(enhancements.get("eq_band_count", 256))
                features = _enhanced_audio_features(
                    audio, int(fps), duration,
                    analysis_band_count,
                    int(enhancements.get("eq_fft_size", 8192)),
                    int(enhancements.get("eq_hop_size", 2048)),
                    str(enhancements.get("eq_frequency_scale", "log")),
                    float(enhancements.get("eq_min_frequency", 20.0)),
                    float(enhancements.get("eq_max_frequency", 20000.0)),
                    float(enhancements.get("eq_dynamic_range_db", 66.0)),
                    float(enhancements.get("eq_noise_floor_db", -72.0)),
                    float(enhancements.get("analysis_sensitivity", 1.0)),
                    float(enhancements.get("transient_emphasis", 0.22)),
                )
                high_resolution_eq = bool(enhancements.get("high_resolution_eq_enabled", True))
                if bool(eq_enabled) and high_resolution_eq:
                    eq_bands = _asymmetric_smooth(
                        features["spectrum_bands"],
                        float(enhancements.get("eq_attack_ms", 35.0)) / 1000.0,
                        float(enhancements.get("eq_release_ms", 220.0)) / 1000.0,
                        int(fps),
                    )
                elif bool(eq_enabled):
                    legacy_eq_features = _audio_features(audio, int(fps), duration)
                    eq_bands = _smooth_spectrum_bands(legacy_eq_features["spectrum_bands"], float(eq_smoothing))
                else:
                    eq_bands = None
                if eq_bands is not None:
                    eq_bands = np.clip(eq_bands * float(enhancements.get("eq_gain", 1.0)), 0.0, 1.0)
                eq_peaks = _spectrum_peak_envelope(
                    eq_bands, int(fps), float(enhancements.get("eq_peak_hold_seconds", 0.16)),
                    float(enhancements.get("eq_peak_decay_per_second", 1.6)),
                ) if bool(eq_enabled) and high_resolution_eq and bool(enhancements.get("eq_peak_enabled", True)) else None
                diagnostics.append(
                    f"audio analysis: cache {features.get('cache_status', 'unknown')} {str(features.get('cache_key', ''))[:12]}, "
                    f"{int(enhancements.get('eq_fft_size', 8192))}-point Hann FFT / {int(enhancements.get('eq_hop_size', 2048))} hop / "
                    f"{analysis_band_count} genuine {enhancements.get('eq_frequency_scale', 'log')} bands"
                )
                group_sources = {}
                section_override, section_override_report = _section_override_curve(
                    str(enhancements.get("section_override_json", "[]")), len(features["energy"]), int(fps),
                )
                diagnostics.append(f"section dynamics: {section_override_report}")
                for plan in plans:
                    driver = str(plan.get("audio_driver", "beat"))
                    group_key = (str(plan.get("envelope_group", "independent")), driver)
                    source = group_sources.setdefault(group_key, features.get(driver, features["energy"]))
                    secondary_name = str(plan.get("secondary_audio_driver", "none"))
                    mix = min(1.0, max(0.0, float(plan.get("secondary_driver_mix", 0.0))))
                    if secondary_name != "none" and secondary_name in features and mix > 0.0:
                        source = (1.0 - mix) * source + mix * features[secondary_name]
                    section_amount = min(1.0, max(0.0, float(plan.get("section_response", 0.0))))
                    if bool(enhancements.get("section_dynamics_enabled", True)) and section_amount > 0.0:
                        source = source * ((1.0 - section_amount) + section_amount * (0.45 + 0.55 * features["phrase"]))
                    source = np.clip(source * section_override, 0.0, 1.0)
                    if bool(enhancements.get("target_envelopes_enabled", True)):
                        plan["enhanced_drive"] = _shape_audio_response(source, int(fps), plan)
            else:
                features = _audio_features(audio, int(fps), duration)
                eq_bands = _smooth_spectrum_bands(features["spectrum_bands"], float(eq_smoothing)) if bool(eq_enabled) else None
                eq_peaks = None
            analysis_seconds = time.perf_counter() - analysis_started
            frame_count = len(features["energy"])
            progress = ProgressBar(frame_count + 3) if ProgressBar else None
            if progress:
                progress.update_absolute(2, frame_count + 3)
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                "-pixel_format", "rgb24", "-video_size", f"{width}x{height}", "-framerate", str(int(fps)),
                "-i", "-", "-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0", "-t", f"{duration:.9f}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(partial_path),
            ]
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                for frame_index in range(frame_count):
                    frame = base.copy()
                    seconds = frame_index / float(fps)
                    for plan in plans:
                        layer = plan["layer"]
                        x0, y0, x1, y1 = layer.bounds
                        original = frame[y0:y1, x0:x1].astype(np.float32)
                        changed = original.copy()
                        driver = str(plan.get("audio_driver", "beat"))
                        audio_drive = (
                            float(plan["enhanced_drive"][frame_index])
                            if enhanced and "enhanced_drive" in plan
                            else self._audio_drive(features, frame_index, driver)
                        )
                        beat_signal = self._audio_drive(features, frame_index, "beat")
                        phase = plan["phase"]
                        off_flicker = float(plan.get("off_beat_flicker", 0.0))
                        autonomous = off_flicker * (0.55 + 0.25 * math.sin(seconds * 0.83 + phase) + 0.20 * math.sin(seconds * 1.91 + phase * 1.7))
                        reactive = float(plan.get("on_beat_flicker", 0.0)) * audio_drive

                        generated_frames = plan["generated_frames"]
                        if generated_frames:
                            overlap_frames = round(float(plan.get("generated_clip_overlap_seconds", 0.6)) * int(fps))
                            clip_frame = _looped_motion_frame(generated_frames, frame_index, overlap_frames)
                            generated_crop = clip_frame[y0:y1, x0:x1].astype(np.float32)
                            amount = float(plan.get("generated_motion_strength", 0.85))
                            changed = changed * (1.0 - amount) + generated_crop * amount

                        atmospheric_mode = str(plan.get("atmospheric_motion_mode", "auto"))
                        clip_only = atmospheric_mode == "cached_clip" or (
                            atmospheric_mode == "auto" and plan.get("motion_source") == "generated_clip"
                        )
                        procedural = not clip_only or not generated_frames
                        if procedural:
                            motion_type = str(plan.get("motion_type", "drift"))
                            motion_pixels = _procedural_motion_pixels(
                                motion_type, height, int(plan.get("expansion_radius", 0)),
                            )
                            motion_amount = motion_pixels * (
                                float(plan.get("off_beat_motion", 0.0)) + float(plan.get("on_beat_motion", 0.0)) * beat_signal
                            )
                            if motion_type == "billow" and bool(plan.get("non_geometric_atmosphere", False)):
                                alpha = plan["motion_mask"][y0:y1, x0:x1, None]
                                changed = _non_geometric_atmospheric_billow(
                                    changed, alpha, plan["rows"], plan["columns"],
                                    seconds, phase, motion_amount,
                                    float(plan.get("smoke_effect_strength", 1.0)),
                                )
                            elif motion_type in {"billow", "sway"}:
                                warped = _deform_pixels(changed, seconds, phase, motion_amount, motion_type)
                                if plan.get("expansion_radius", 0):
                                    mask_pixels = np.repeat(
                                        np.clip(plan["motion_mask"][y0:y1, x0:x1, None] * 255.0, 0, 255),
                                        3, axis=2,
                                    )
                                    alpha = _deform_pixels(mask_pixels, seconds, phase, motion_amount, motion_type)[..., :1] / 255.0
                                else:
                                    alpha = plan["motion_mask"][y0:y1, x0:x1, None]
                                changed = changed * (1.0 - alpha) + warped * alpha
                            elif motion_type == "drift":
                                warped = _translate_pixels(
                                    changed,
                                    motion_amount * math.sin(seconds * 0.72 + phase),
                                    motion_amount * 0.45 * math.cos(seconds * 0.51 + phase * 1.7),
                                )
                                alpha = plan["motion_mask"][y0:y1, x0:x1, None]
                                changed = changed * (1.0 - alpha) + warped * alpha

                        role = plan.get("target_role", "organic")
                        lighting_gain = float(plan.get("lighting_gain", 1.0)) if enhanced else 1.0
                        bounded = _lighting_luminance_amount(
                            min(0.5, float(plan.get("max_luminance_change", 0.12)) * lighting_gain),
                            reactive, autonomous, enhanced,
                        )
                        if role in {"light_source", "illumination", "reflection"}:
                            changed *= 1.0 + bounded
                            hue = float(plan.get("hue_variation_degrees", 0.0)) * (reactive + 0.25 * autonomous)
                            saturation = float(plan.get("saturation_variation", 0.0)) * (reactive + 0.25 * autonomous)
                            changed = _shift_hue_and_saturation(changed, hue, saturation)
                            if role == "reflection":
                                shimmer = 0.5 + 0.5 * np.sin(plan["rows"] * 0.09 + seconds * 2.7 + phase)
                                shimmer_amount = (
                                    float(plan.get("shimmer_amount", 0.0))
                                    if enhanced and bool(enhancements.get("shimmer_effects_enabled", True)) and bool(plan.get("shimmer_enabled", False))
                                    else 0.0
                                )
                                high_drive = float(features.get("hihat", features["high"])[frame_index]) if enhanced else 0.0
                                changed *= 1.0 + min(0.18, bounded + shimmer_amount * high_drive * 0.07) * shimmer
                        else:
                            flow = 0.5 * (
                                np.sin(plan["columns"] * 0.008 + plan["rows"] * 0.005 - seconds * 0.55 + phase)
                                + np.cos(plan["columns"] * 0.004 - plan["rows"] * 0.009 + seconds * 0.37 + phase)
                            )
                            for mode in plan.get("effect_modes", ("drift",)):
                                if mode == "drift":
                                    changed *= 1.0 + 0.045 * reactive + autonomous * (0.035 + 0.10 * flow)
                                elif mode == "flicker":
                                    changed *= 1.0 + 0.16 * (reactive + autonomous)
                                elif mode == "flash":
                                    changed += 28.0 * reactive
                                elif mode == "shimmer":
                                    shimmer = 0.5 + 0.5 * np.sin(plan["rows"] * 0.09 + seconds * 2.7 + phase)
                                    changed *= 1.0 + 0.12 * (reactive + autonomous) * shimmer
                            if enhanced and bool(enhancements.get("atmospheric_effects_enabled", True)) and plan.get("motion_type") == "billow":
                                atmosphere = float(plan.get("shimmer_amount", 0.0)) * float(features["high"][frame_index])
                                if atmosphere > 0.0:
                                    haze = 0.5 + 0.5 * np.sin(plan["columns"] * 0.011 + plan["rows"] * 0.004 - seconds * 0.31 + phase)
                                    changed *= 1.0 + min(0.035, atmosphere * 0.025) * haze
                        _blend(frame, changed, layer)

                        edge_alpha = plan.get("edge_alpha")
                        if enhanced and bool(enhancements.get("edge_glow_effects_enabled", True)) and edge_alpha is not None:
                            edge_amount = min(0.18, float(plan.get("edge_glow_amount", 0.0)) * audio_drive * 0.18)
                            if edge_amount > 0.0:
                                edge = edge_alpha[..., None] * edge_amount
                                edge_source = frame[y0:y1, x0:x1].astype(np.float32)
                                frame[y0:y1, x0:x1] = np.clip(
                                    edge_source + (255.0 - edge_source) * edge, 0, 255,
                                ).astype(np.uint8)

                        glow_layer = plan.get("glow_layer")
                        if glow_layer is not None and glow_layer.bounds is not None and float(plan.get("glow_strength", 0.0)) > 0:
                            gx0, gy0, gx1, gy1 = glow_layer.bounds
                            glow_pixels = frame[gy0:gy1, gx0:gx1].astype(np.float32)
                            glow_amount = _lighting_glow_amount(
                                float(plan.get("glow_strength", 0.0)) * lighting_gain,
                                audio_drive, autonomous, enhanced,
                            )
                            if enhanced:
                                warm = np.asarray((255.0, 208.0, 142.0), dtype=np.float32)
                                glow_pixels = glow_pixels * (1.0 + 0.45 * glow_amount) + warm * (0.42 * glow_amount)
                                glow_opacity = 1.0
                            else:
                                glow_pixels = glow_pixels * (1.0 + glow_amount)
                                glow_opacity = min(1.0, float(plan.get("glow_strength", 0.0)))
                            glow_pixels = _shift_hue_and_saturation(
                                glow_pixels, float(plan.get("hue_variation_degrees", 0.0)) * reactive, 0.0,
                            )
                            _blend(frame, glow_pixels, glow_layer, opacity=glow_opacity)
                    for overlay in overlays:
                        _apply_overlay(frame, overlay)
                    title_alpha = 0.0
                    if title_card is not None:
                        title_alpha = _title_card_alpha(
                            seconds, title_card_start_seconds, title_card_duration_seconds, title_card_fade_seconds,
                        )
                        if title_alpha > 0.0:
                            frame = np.clip(
                                frame.astype(np.float32) * (1.0 - title_alpha)
                                + title_card.astype(np.float32) * title_alpha,
                                0, 255,
                            ).astype(np.uint8)
                    if eq_bands is not None:
                        if enhanced and bool(enhancements.get("high_resolution_eq_enabled", True)) and str(eq_mode) != "spectrum_bars":
                            _apply_high_resolution_eq(
                                frame, eq_bands[frame_index], eq_peaks[frame_index] if eq_peaks is not None else None,
                                str(eq_mode), float(eq_height_percent), float(eq_opacity), eq_color_rgb,
                                _parse_overlay_color(str(enhancements.get("eq_peak_color", "#D9B5A2"))),
                                float(enhancements.get("eq_margin_percent", 2.0)),
                                str(enhancements.get("eq_density_render_mode", "auto")),
                            )
                        elif enhanced and bool(enhancements.get("high_resolution_eq_enabled", True)) and len(eq_bands[frame_index]) > 56:
                            _apply_high_resolution_eq(
                                frame, eq_bands[frame_index], eq_peaks[frame_index] if eq_peaks is not None else None,
                                "fine_spectrum_bars", float(eq_height_percent), float(eq_opacity), eq_color_rgb,
                                _parse_overlay_color(str(enhancements.get("eq_peak_color", "#D9B5A2"))),
                                float(enhancements.get("eq_margin_percent", 2.0)),
                                str(enhancements.get("eq_density_render_mode", "auto")),
                            )
                        else:
                            _apply_eq_overlay(
                                frame, eq_bands[frame_index], str(eq_mode), float(eq_height_percent),
                                float(eq_opacity), eq_color_rgb,
                            )
                    if bool(title_sparkle_enabled) and title_outline_mask is not None and title_alpha > 0.0:
                        sparkle_response = (
                            (1.0 - float(title_sparkle_audio_response))
                            + float(title_sparkle_audio_response) * float(features["high"][frame_index])
                        )
                        _apply_title_outline_sparkle(
                            frame, title_outline_mask, seconds, float(title_sparkle_strength),
                            sparkle_response, int(pattern_key), title_alpha,
                        )
                    if bool(title_sparkle_enabled) and wordmark_outline_mask is not None and title_alpha < 1.0:
                        sparkle_response = (
                            (1.0 - float(title_sparkle_audio_response))
                            + float(title_sparkle_audio_response) * float(features["high"][frame_index])
                        )
                        _apply_title_outline_sparkle(
                            frame, wordmark_outline_mask, seconds, float(title_sparkle_strength),
                            sparkle_response, int(pattern_key) + 17, 1.0 - title_alpha,
                        )
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

        partial_path.replace(output_path)
        qa_report = "\n".join(diagnostics + [
            f"rendered {frame_count} frames at {width}x{height}/{int(fps)} fps",
            f"audio analysis {analysis_seconds:.3f}s; end-to-end renderer {time.perf_counter() - render_started:.3f}s",
            "static-base invariant: environmental motion remains confined to verified masks plus bounded organic expansion; wordmark/title/EQ are stationary overlays",
            "audio preserved via AAC mux; completed output promoted atomically from .part.mp4",
            "enhancement switches are independent; renderer retained frame-at-a-time streaming" if enhanced else "baseline production controls retained",
        ])
        preview = {"filename": output_file, "subfolder": subfolder, "type": "output"}
        return {"ui": {"images": [preview], "animated": (True,)}, "result": (str(output_path), qa_report)}


class InfraChoirVisualizerEnhanced(InfraChoirVisualizer):
    """Production renderer with one cached high-resolution analysis pass."""

    @classmethod
    def INPUT_TYPES(cls):
        inputs = InfraChoirVisualizer.INPUT_TYPES()
        required = dict(inputs["required"])
        required["eq_mode"] = (
            ["spectrum_bars", "fine_spectrum_bars", "spectrum_line", "filled_spectrum", "mirrored_spectrum"],
            {"default": "fine_spectrum_bars"},
        )
        required.update({
            "enhancements_enabled": ("BOOLEAN", {"default": True}),
            "target_envelopes_enabled": ("BOOLEAN", {"default": True}),
            "high_resolution_eq_enabled": ("BOOLEAN", {"default": True}),
            "eq_band_count": ([32, 64, 128, 256, 512], {"default": 256}),
            "eq_fft_size": ([4096, 8192, 16384], {"default": 8192}),
            "eq_hop_size": ([512, 1024, 2048, 4096], {"default": 2048}),
            "eq_frequency_scale": (["log", "linear"], {"default": "log"}),
            "eq_min_frequency": ("FLOAT", {"default": 20.0, "min": 1.0, "max": 2000.0, "step": 1.0}),
            "eq_max_frequency": ("FLOAT", {"default": 20000.0, "min": 1000.0, "max": 24000.0, "step": 100.0}),
            "eq_attack_ms": ("FLOAT", {"default": 35.0, "min": 0.0, "max": 1000.0, "step": 5.0}),
            "eq_release_ms": ("FLOAT", {"default": 220.0, "min": 5.0, "max": 3000.0, "step": 5.0}),
            "eq_peak_enabled": ("BOOLEAN", {"default": True}),
            "eq_peak_hold_seconds": ("FLOAT", {"default": 0.16, "min": 0.0, "max": 2.0, "step": 0.02}),
            "eq_peak_decay_per_second": ("FLOAT", {"default": 1.6, "min": 0.05, "max": 10.0, "step": 0.05}),
            "eq_peak_color": ("STRING", {"default": "#D9B5A2"}),
            "eq_gain": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 4.0, "step": 0.05}),
            "eq_dynamic_range_db": ("FLOAT", {"default": 66.0, "min": 18.0, "max": 120.0, "step": 1.0}),
            "eq_noise_floor_db": ("FLOAT", {"default": -72.0, "min": -120.0, "max": -12.0, "step": 1.0}),
            "eq_margin_percent": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 20.0, "step": 0.5}),
            "analysis_sensitivity": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 3.0, "step": 0.05}),
            "transient_emphasis": ("FLOAT", {"default": 0.22, "min": 0.0, "max": 1.0, "step": 0.02}),
            "edge_glow_effects_enabled": ("BOOLEAN", {"default": True}),
            "shimmer_effects_enabled": ("BOOLEAN", {"default": True}),
            "atmospheric_effects_enabled": ("BOOLEAN", {"default": True}),
            "section_dynamics_enabled": ("BOOLEAN", {"default": True}),
            "section_override_json": ("STRING", {"multiline": True, "default": "[]"}),
        })
        return {"required": required, "optional": inputs["optional"]}

    DESCRIPTION = "Render the Infra Choir production compositor with cached high-resolution spectrum and richer target-local audio response."


class InfraChoirVisualizerDualTrack(InfraChoirVisualizerEnhanced):
    """Compatibility-isolated renderer schema for reviewed auto targets and ultra EQ."""

    @classmethod
    def INPUT_TYPES(cls):
        inputs = InfraChoirVisualizerEnhanced.INPUT_TYPES()
        required = dict(inputs["required"])
        required.update({
            "title_text_alignment": (["left", "center", "right"], {"default": "center"}),
            "auto_targets_enabled": ("BOOLEAN", {"default": True}),
            "eq_ultra_band_count": ([0, 1024, 2048], {"default": 0}),
            "eq_density_render_mode": (["auto", "peak", "rms", "mean"], {"default": "auto"}),
            "generated_clip_cache_enabled": ("BOOLEAN", {"default": True}),
            "expansive_atmosphere_enabled": ("BOOLEAN", {"default": False}),
        })
        return {"required": required, "optional": inputs["optional"]}

    DESCRIPTION = "Render merged manual/reviewed-auto targets with fixed-bound title alignment, ultra-band EQ, and offline atmospheric clips."


NODE_CLASS_MAPPINGS = {
    "VisualizerCandidateRegions": VisualizerCandidateRegions,
    "VisualizerRegionMask": VisualizerRegionMask,
    "BeatAwareLocalVisualizer": BeatAwareLocalVisualizer,
    "BeatAwareLocalVisualizerV2": BeatAwareLocalVisualizer,
    "BeatAwareLocalVisualizerV3": BeatAwareLocalVisualizer,
    "VisualizerObjectDetector": VisualizerObjectDetector,
    "VisualizerSemanticObjectDetector": VisualizerSemanticObjectDetector,
    "VisualizerManualTargetDetector": VisualizerManualTargetDetector,
    "VisualizerMaskReview": VisualizerMaskReview,
    "VisualizerAnimationTarget": VisualizerAnimationTarget,
    "VisualizerTargetStack": VisualizerTargetStack,
    "GenericBeatAwareLocalVisualizer": GenericBeatAwareLocalVisualizer,
    "InfraChoirAnimationTarget": InfraChoirAnimationTarget,
    "InfraChoirVisualizer": InfraChoirVisualizer,
    "InfraChoirAnimationTargetEnhanced": InfraChoirAnimationTargetEnhanced,
    "InfraChoirAtmosphericTargetEnhanced": InfraChoirAtmosphericTargetEnhanced,
    "InfraChoirManualAtmosphereTarget": InfraChoirManualAtmosphereTarget,
    "InfraChoirCachedMotionTarget": InfraChoirCachedMotionTarget,
    "InfraChoirManualTargetCompact": InfraChoirManualTargetCompact,
    "InfraChoirVisualizerEnhanced": InfraChoirVisualizerEnhanced,
    "InfraChoirVisualizerDualTrack": InfraChoirVisualizerDualTrack,
    "InfraChoirAutoDiscover": InfraChoirAutoDiscover,
    "InfraChoirApprovedTargets": InfraChoirApprovedTargets,
    "InfraChoirTargetMerge": InfraChoirTargetMerge,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VisualizerCandidateRegions": "Suggest Local Visualizer Regions",
    "VisualizerRegionMask": "Local Visualizer Region Mask",
    "BeatAwareLocalVisualizer": "Render Beat-Aware Local Visualizer",
    "BeatAwareLocalVisualizerV2": "Render Beat-Aware Local Visualizer",
    "BeatAwareLocalVisualizerV3": "Render Beat-Aware Local Visualizer + Badging",
    "VisualizerObjectDetector": "Detect Animation Target",
    "VisualizerSemanticObjectDetector": "Detect Animation Target (Semantic)",
    "VisualizerManualTargetDetector": "Box / Detect Manual Render Target",
    "VisualizerMaskReview": "Verify / Edit Detection Mask",
    "VisualizerAnimationTarget": "Configure Animation Target",
    "VisualizerTargetStack": "Add Animation Target",
    "GenericBeatAwareLocalVisualizer": "Render Generic Target Visualizer",
    "InfraChoirAnimationTarget": "Configure Infra Choir Target",
    "InfraChoirVisualizer": "Render Infra Choir Hybrid Visualizer",
    "InfraChoirAnimationTargetEnhanced": "Configure Infra Choir Target (Enhanced)",
    "InfraChoirAtmosphericTargetEnhanced": "Configure Infra Choir Atmosphere (Enhanced)",
    "InfraChoirManualAtmosphereTarget": "Configure Manual Smoke / Haze",
    "InfraChoirCachedMotionTarget": "Select Cached Full-Scene Motion",
    "InfraChoirManualTargetCompact": "Configure Manual Target (Compact)",
    "InfraChoirVisualizerEnhanced": "Render Infra Choir Visualizer (Enhanced)",
    "InfraChoirVisualizerDualTrack": "Render Infra Choir Visualizer (Dual Track)",
    "InfraChoirAutoDiscover": "Discover Infra Choir Targets (Setup Only)",
    "InfraChoirApprovedTargets": "Load Approved Infra Choir Targets",
    "InfraChoirTargetMerge": "Merge Infra Choir Manual + Auto Targets",
}
