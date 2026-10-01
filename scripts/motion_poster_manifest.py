from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ManifestError(ValueError):
    """Raised when a motion-poster manifest is incomplete or invalid."""


@dataclass(frozen=True)
class GenerationSettings:
    width: int
    height: int
    fps: int
    loop_count: int
    positive_prompt: str
    negative_prompt: str


@dataclass(frozen=True)
class LoopSettings:
    path: Path
    reversal_crossfade_seconds: float


@dataclass(frozen=True)
class AssemblySettings:
    variant_crossfade_seconds: float
    aspect_ratio_tolerance: float


@dataclass(frozen=True)
class CameraSettings:
    zoom: float
    x_amplitude_px: float
    y_amplitude_px: float
    x_period_seconds: float
    y_period_seconds: float


@dataclass(frozen=True)
class OutputSettings:
    path: Path
    width: int
    height: int
    fps: int
    video_codec: str
    preset: str
    crf: int
    audio_codec: str
    audio_bitrate: str


@dataclass(frozen=True)
class MotionPosterManifest:
    source_path: Path
    audio_path: Path
    reference_image_paths: tuple[Path, ...]
    lyrics_path: Path | None
    generation: GenerationSettings
    loops: tuple[LoopSettings, ...]
    assembly: AssemblySettings
    camera: CameraSettings
    output: OutputSettings


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"{name} must be an object")
    return value


def _string(mapping: dict[str, Any], key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{context}.{key} must be a non-empty string")
    return value


def _number(
    mapping: dict[str, Any], key: str, context: str, *, minimum: float
) -> float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ManifestError(f"{context}.{key} must be a number")
    number = float(value)
    if number < minimum:
        raise ManifestError(f"{context}.{key} must be at least {minimum}")
    return number


def _integer(
    mapping: dict[str, Any], key: str, context: str, *, minimum: int
) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ManifestError(f"{context}.{key} must be an integer")
    if value < minimum:
        raise ManifestError(f"{context}.{key} must be at least {minimum}")
    return value


def _resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _path_list(base: Path, value: Any, context: str) -> tuple[Path, ...]:
    if not isinstance(value, list) or not value:
        raise ManifestError(f"{context} must be a non-empty array")
    paths: list[Path] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ManifestError(f"{context}[{index}] must be a non-empty string")
        paths.append(_resolve(base, item))
    return tuple(paths)


def load_manifest(path: Path) -> MotionPosterManifest:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"could not read {path}: {exc}") from exc

    root = _mapping(raw, "manifest")
    if root.get("version") != 2:
        raise ManifestError("version must be 2")

    inputs = _mapping(root.get("inputs"), "inputs")
    generation = _mapping(root.get("generation"), "generation")
    assembly = _mapping(root.get("assembly"), "assembly")
    camera = _mapping(root.get("camera"), "camera")
    output = _mapping(root.get("output"), "output")
    base = path.resolve().parent

    loops_value = root.get("loops")
    if not isinstance(loops_value, list) or not loops_value:
        raise ManifestError("loops must be a non-empty array")
    loops: list[LoopSettings] = []
    for index, item in enumerate(loops_value):
        loop = _mapping(item, f"loops[{index}]")
        loops.append(
            LoopSettings(
                path=_resolve(base, _string(loop, "path", f"loops[{index}]")),
                reversal_crossfade_seconds=_number(
                    loop,
                    "reversal_crossfade_seconds",
                    f"loops[{index}]",
                    minimum=0.0,
                ),
            )
        )

    lyrics_value = inputs.get("lyrics")
    if lyrics_value is not None and not isinstance(lyrics_value, str):
        raise ManifestError("inputs.lyrics must be a string or null")

    output_fps = _integer(output, "fps", "output", minimum=1)
    output_width = _integer(output, "width", "output", minimum=2)
    output_height = _integer(output, "height", "output", minimum=2)
    if output_width % 2 or output_height % 2:
        raise ManifestError("output.width and output.height must be even")

    generation_width = _integer(generation, "width", "generation", minimum=2)
    generation_height = _integer(generation, "height", "generation", minimum=2)
    generation_fps = _integer(generation, "fps", "generation", minimum=1)
    if (generation_width, generation_height, generation_fps) != (
        output_width,
        output_height,
        output_fps,
    ):
        raise ManifestError(
            "generation width, height, and fps must match output for native "
            "assembly without reframing"
        )

    loop_count = _integer(generation, "loop_count", "generation", minimum=1)
    if loop_count != len(loops):
        raise ManifestError("generation.loop_count must match the number of loops")

    return MotionPosterManifest(
        source_path=path.resolve(),
        audio_path=_resolve(base, _string(inputs, "audio", "inputs")),
        reference_image_paths=_path_list(
            base, inputs.get("reference_images"), "inputs.reference_images"
        ),
        lyrics_path=_resolve(base, lyrics_value) if lyrics_value else None,
        generation=GenerationSettings(
            width=generation_width,
            height=generation_height,
            fps=generation_fps,
            loop_count=loop_count,
            positive_prompt=_string(
                generation, "positive_prompt", "generation"
            ),
            negative_prompt=_string(
                generation, "negative_prompt", "generation"
            ),
        ),
        loops=tuple(loops),
        assembly=AssemblySettings(
            variant_crossfade_seconds=_number(
                assembly,
                "variant_crossfade_seconds",
                "assembly",
                minimum=0.0,
            ),
            aspect_ratio_tolerance=_number(
                assembly,
                "aspect_ratio_tolerance",
                "assembly",
                minimum=0.0,
            ),
        ),
        camera=CameraSettings(
            zoom=_number(camera, "zoom", "camera", minimum=1.0),
            x_amplitude_px=_number(
                camera, "x_amplitude_px", "camera", minimum=0.0
            ),
            y_amplitude_px=_number(
                camera, "y_amplitude_px", "camera", minimum=0.0
            ),
            x_period_seconds=_number(
                camera, "x_period_seconds", "camera", minimum=0.1
            ),
            y_period_seconds=_number(
                camera, "y_period_seconds", "camera", minimum=0.1
            ),
        ),
        output=OutputSettings(
            path=_resolve(base, _string(output, "path", "output")),
            width=output_width,
            height=output_height,
            fps=output_fps,
            video_codec=_string(output, "video_codec", "output"),
            preset=_string(output, "preset", "output"),
            crf=_integer(output, "crf", "output", minimum=0),
            audio_codec=_string(output, "audio_codec", "output"),
            audio_bitrate=_string(output, "audio_bitrate", "output"),
        ),
    )


def validate_input_paths(manifest: MotionPosterManifest) -> None:
    required = [("inputs.audio", manifest.audio_path)]
    required.extend(
        (f"inputs.reference_images[{index}]", path)
        for index, path in enumerate(manifest.reference_image_paths)
    )
    required.extend(
        (f"loops[{index}].path", loop.path)
        for index, loop in enumerate(manifest.loops)
    )
    if manifest.lyrics_path is not None:
        required.append(("inputs.lyrics", manifest.lyrics_path))
    for label, required_path in required:
        if not required_path.is_file():
            raise ManifestError(f"{label} does not exist: {required_path}")
