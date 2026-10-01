from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from motion_poster_manifest import (
    LoopSettings,
    ManifestError,
    MotionPosterManifest,
    load_manifest,
    validate_input_paths,
)


class RenderError(RuntimeError):
    """Raised when probing, rendering, or output validation fails."""


def _run(command: list[str]) -> None:
    print("Running:", subprocess.list2cmdline(command))
    completed = subprocess.run(command, check=False)
    if completed.returncode:
        raise RenderError(
            f"command failed with exit code {completed.returncode}: {command[0]}"
        )


def _probe(path: Path, *, count_frames: bool = False) -> dict[str, Any]:
    command = ["ffprobe", "-v", "error"]
    if count_frames:
        command.append("-count_frames")
    command.extend(
        [
            "-show_entries",
            "format=duration:stream=index,codec_type,width,height,"
            "avg_frame_rate,duration,nb_read_frames",
            "-of",
            "json",
            str(path),
        ]
    )
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode:
        detail = completed.stderr.strip() or "unknown ffprobe error"
        raise RenderError(f"could not probe {path}: {detail}")
    return json.loads(completed.stdout)


def _duration(probe: dict[str, Any], path: Path) -> float:
    raw = probe.get("format", {}).get("duration")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise RenderError(f"no usable duration found in {path}") from exc
    if not math.isfinite(value) or value <= 0:
        raise RenderError(f"invalid duration found in {path}: {raw}")
    return value


def _video_stream(probe: dict[str, Any], path: Path) -> dict[str, Any]:
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream
    raise RenderError(f"no video stream found in {path}")


def _audio_stream(probe: dict[str, Any], path: Path) -> dict[str, Any]:
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "audio":
            return stream
    raise RenderError(f"no audio stream found in {path}")


def _build_closed_cycle(
    manifest: MotionPosterManifest,
    loop: LoopSettings,
    clip_duration: float,
    destination: Path,
) -> float:
    fps = manifest.output.fps
    frame_duration = 1.0 / fps
    crossfade = loop.reversal_crossfade_seconds
    if crossfade <= 0 or crossfade >= clip_duration / 2:
        raise RenderError(
            "loop.crossfade_seconds must be greater than zero and shorter "
            "than half of the source clip"
        )

    midpoint = clip_duration / 2
    first_offset = midpoint - crossfade
    second_offset = midpoint + clip_duration - (2 * crossfade)
    cycle_duration = (2 * clip_duration) - (2 * crossfade) - frame_duration
    if cycle_duration <= frame_duration:
        raise RenderError("loop clip is too short for the selected crossfade")

    filter_graph = (
        f"[0:v]scale={manifest.output.width}:{manifest.output.height}:"
        f"flags=lanczos,fps={fps},split=3[forward][backward][closing];"
        f"[forward]trim=start={midpoint:.9f},setpts=PTS-STARTPTS[a];"
        f"[backward]reverse,setpts=PTS-STARTPTS[b];"
        f"[closing]trim=end={midpoint:.9f},setpts=PTS-STARTPTS[c];"
        f"[a][b]xfade=transition=fade:duration={crossfade:.9f}:"
        f"offset={first_offset:.9f}[ab];"
        f"[ab][c]xfade=transition=fade:duration={crossfade:.9f}:"
        f"offset={second_offset:.9f},"
        f"trim=end={cycle_duration:.9f},setpts=PTS-STARTPTS,format=yuv420p[v]"
    )
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-y",
            "-i",
            str(loop.path),
            "-filter_complex",
            filter_graph,
            "-map",
            "[v]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-movflags",
            "+faststart",
            str(destination),
        ]
    )
    return cycle_duration


def _build_variant_reel(
    manifest: MotionPosterManifest,
    cycles: list[tuple[Path, float]],
    destination: Path,
) -> tuple[Path, float]:
    if len(cycles) == 1:
        return cycles[0]

    crossfade = manifest.assembly.variant_crossfade_seconds
    anchor_half = cycles[0][1] / 2
    shortest = min(anchor_half, *(duration for _, duration in cycles[1:]))
    if crossfade <= 0 or crossfade >= shortest:
        raise RenderError(
            "assembly.variant_crossfade_seconds must be greater than zero and "
            "shorter than every reel segment"
        )

    command = ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-y"]
    for cycle_path, _ in cycles:
        command.extend(["-i", str(cycle_path)])

    parts = [
        f"[0:v]split=2[anchor_after][anchor_before]",
        f"[anchor_after]trim=start={anchor_half:.9f},setpts=PTS-STARTPTS[s0]",
    ]
    durations = [anchor_half]
    for index, (_, duration) in enumerate(cycles[1:], start=1):
        parts.append(f"[{index}:v]setpts=PTS-STARTPTS[s{index}]")
        durations.append(duration)
    closing_index = len(cycles)
    parts.append(
        f"[anchor_before]trim=end={anchor_half:.9f},"
        f"setpts=PTS-STARTPTS[s{closing_index}]"
    )
    durations.append(anchor_half)

    cumulative = durations[0]
    previous = "s0"
    for index in range(1, len(durations)):
        output_label = f"mix{index}"
        offset = cumulative - crossfade
        parts.append(
            f"[{previous}][s{index}]xfade=transition=fade:"
            f"duration={crossfade:.9f}:offset={offset:.9f}[{output_label}]"
        )
        cumulative += durations[index] - crossfade
        previous = output_label

    reel_duration = cumulative - (1 / manifest.output.fps)
    parts.append(
        f"[{previous}]trim=end={reel_duration:.9f},"
        "setpts=PTS-STARTPTS,format=yuv420p[v]"
    )
    command.extend(
        [
            "-filter_complex",
            ";".join(parts),
            "-map",
            "[v]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-movflags",
            "+faststart",
            str(destination),
        ]
    )
    _run(command)
    return destination, reel_duration


def _validate_loop_aspect(
    manifest: MotionPosterManifest,
    loop: LoopSettings,
    video_stream: dict[str, Any],
) -> None:
    width = int(video_stream["width"])
    height = int(video_stream["height"])
    source_ratio = width / height
    target_ratio = manifest.output.width / manifest.output.height
    relative_error = abs(source_ratio - target_ratio) / target_ratio
    if relative_error > manifest.assembly.aspect_ratio_tolerance:
        raise RenderError(
            f"loop is {width}x{height}, not native {manifest.output.width}x"
            f"{manifest.output.height}; refusing to crop or stretch {loop.path}"
        )


def _render_song(
    manifest: MotionPosterManifest,
    cycle_path: Path,
    audio_duration: float,
    source_width: int,
    source_height: int,
) -> None:
    output = manifest.output
    camera = manifest.camera
    cover_scale = max(
        output.width / source_width,
        output.height / source_height,
    )
    scaled_width = math.ceil(source_width * cover_scale * camera.zoom / 2) * 2
    scaled_height = math.ceil(source_height * cover_scale * camera.zoom / 2) * 2
    available_x = (scaled_width - output.width) / 2
    available_y = (scaled_height - output.height) / 2
    if camera.x_amplitude_px > available_x:
        raise RenderError(
            "camera.x_amplitude_px exceeds the horizontal overscan supplied by "
            "camera.zoom"
        )
    if camera.y_amplitude_px > available_y:
        raise RenderError(
            "camera.y_amplitude_px exceeds the vertical overscan supplied by "
            "camera.zoom"
        )

    x = (
        f"(iw-ow)/2+{camera.x_amplitude_px:.6f}*"
        f"sin(2*PI*t/{camera.x_period_seconds:.6f})"
    )
    y = (
        f"(ih-oh)/2+{camera.y_amplitude_px:.6f}*"
        f"sin(2*PI*t/{camera.y_period_seconds:.6f}+PI/3)"
    )
    video_filter = (
        f"[0:v]scale={scaled_width}:{scaled_height}:flags=lanczos,"
        f"crop={output.width}:{output.height}:x='{x}':y='{y}',"
        f"fps={output.fps},trim=duration={audio_duration:.9f},"
        "setpts=PTS-STARTPTS,format=yuv420p[v]"
    )
    output.path.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(cycle_path),
            "-i",
            str(manifest.audio_path),
            "-filter_complex",
            video_filter,
            "-map",
            "[v]",
            "-map",
            "1:a:0",
            "-t",
            f"{audio_duration:.9f}",
            "-c:v",
            output.video_codec,
            "-preset",
            output.preset,
            "-crf",
            str(output.crf),
            "-c:a",
            output.audio_codec,
            "-b:a",
            output.audio_bitrate,
            "-movflags",
            "+faststart",
            str(output.path),
        ]
    )


def _validate_output(
    manifest: MotionPosterManifest, audio_duration: float
) -> dict[str, Any]:
    probe = _probe(manifest.output.path, count_frames=True)
    video = _video_stream(probe, manifest.output.path)
    audio = _audio_stream(probe, manifest.output.path)
    output_duration = _duration(probe, manifest.output.path)
    if (video.get("width"), video.get("height")) != (
        manifest.output.width,
        manifest.output.height,
    ):
        raise RenderError(
            "rendered dimensions do not match the manifest: "
            f"{video.get('width')}x{video.get('height')}"
        )
    tolerance = max(0.1, 2 / manifest.output.fps)
    if abs(output_duration - audio_duration) > tolerance:
        raise RenderError(
            f"output duration {output_duration:.6f}s differs from source audio "
            f"{audio_duration:.6f}s by more than {tolerance:.6f}s"
        )
    return {
        "output": str(manifest.output.path),
        "source_audio_duration_seconds": audio_duration,
        "output_duration_seconds": output_duration,
        "duration_delta_seconds": output_duration - audio_duration,
        "video_frames": video.get("nb_read_frames"),
        "dimensions": f"{video.get('width')}x{video.get('height')}",
        "has_audio": audio.get("codec_type") == "audio",
    }


def _require_tools() -> None:
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing:
        raise RenderError(f"required executable(s) not found: {', '.join(missing)}")


def render(manifest: MotionPosterManifest, work_directory: Path) -> dict[str, Any]:
    validate_input_paths(manifest)
    _require_tools()
    audio_probe = _probe(manifest.audio_path)
    _audio_stream(audio_probe, manifest.audio_path)
    audio_duration = _duration(audio_probe, manifest.audio_path)

    cycles: list[tuple[Path, float]] = []
    for index, loop in enumerate(manifest.loops):
        clip_probe = _probe(loop.path)
        clip_video = _video_stream(clip_probe, loop.path)
        _validate_loop_aspect(manifest, loop, clip_video)
        clip_duration = _duration(clip_probe, loop.path)
        cycle_path = work_directory / f"closed-cycle-{index:02d}.mp4"
        cycle_duration = _build_closed_cycle(
            manifest, loop, clip_duration, cycle_path
        )
        print(f"Closed cycle {index + 1} duration: {cycle_duration:.3f}s")
        cycles.append((cycle_path, cycle_duration))

    reel_path, reel_duration = _build_variant_reel(
        manifest, cycles, work_directory / "variant-reel.mp4"
    )
    print(f"Variant reel duration: {reel_duration:.3f}s")
    _render_song(
        manifest,
        reel_path,
        audio_duration,
        manifest.output.width,
        manifest.output.height,
    )
    result = _validate_output(manifest, audio_duration)
    result["loop_variants"] = len(manifest.loops)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a bounded-memory full-song motion poster with FFmpeg."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--check-manifest",
        action="store_true",
        help="validate manifest structure without probing runtime media",
    )
    parser.add_argument(
        "--work-directory",
        type=Path,
        help="keep intermediate files in this directory",
    )
    args = parser.parse_args()

    try:
        manifest = load_manifest(args.manifest)
        if args.check_manifest:
            print(f"Manifest is valid: {args.manifest}")
            return 0

        if args.work_directory:
            args.work_directory.mkdir(parents=True, exist_ok=True)
            result = render(manifest, args.work_directory.resolve())
        else:
            with tempfile.TemporaryDirectory(prefix="motion-poster-") as temporary:
                result = render(manifest, Path(temporary))
        print(json.dumps(result, indent=2))
        return 0
    except (ManifestError, RenderError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
