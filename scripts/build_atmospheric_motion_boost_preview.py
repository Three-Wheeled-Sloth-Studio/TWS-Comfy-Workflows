from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import cv2
import numpy as np


def _soft_region_masks(width: int, height: int, reference: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Build broad atmosphere masks while suppressing rigid high-contrast edges."""
    clouds = np.zeros((height, width), np.float32)
    fog = np.zeros_like(clouds)

    cloud_polygon = np.asarray([
        (round(width * 0.30), 0),
        (round(width * 0.86), 0),
        (round(width * 0.89), round(height * 0.43)),
        (round(width * 0.56), round(height * 0.47)),
        (round(width * 0.35), round(height * 0.36)),
    ], np.int32)
    fog_polygon = np.asarray([
        (round(width * 0.43), round(height * 0.43)),
        (width - 1, round(height * 0.38)),
        (width - 1, round(height * 0.70)),
        (round(width * 0.49), round(height * 0.67)),
    ], np.int32)
    cv2.fillPoly(clouds, [cloud_polygon], 1.0)
    cv2.fillPoly(fog, [fog_polygon], 1.0)

    gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    # Keep the lead character and her already-good hair animation completely
    # out of the extra atmospheric treatment.
    character_guard = np.ones_like(clouds)
    cv2.ellipse(
        character_guard,
        (round(width * 0.35), round(height * 0.37)),
        (round(width * 0.17), round(height * 0.38)),
        0, 0, 360, 0.0, -1,
    )
    character_guard = cv2.GaussianBlur(character_guard, (0, 0), max(5.0, height * 0.012))

    clouds = cv2.GaussianBlur(clouds, (0, 0), max(8.0, height * 0.025)) * character_guard
    fog = cv2.GaussianBlur(fog, (0, 0), max(7.0, height * 0.020)) * character_guard
    return clouds[..., None], fog[..., None]


def _advect(frame: np.ndarray, seconds: float, cloud_mask: np.ndarray, fog_mask: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)

    cloud_dx = 4.8 * (
        np.sin(yy * 0.020 + seconds * 0.72)
        + 0.42 * np.sin(xx * 0.011 - seconds * 0.49)
    )
    cloud_dy = 3.5 * (
        np.cos(xx * 0.014 - seconds * 0.58)
        + 0.35 * np.sin(yy * 0.026 + seconds * 0.81)
    )
    fog_dx = 5.5 * (
        np.sin(yy * 0.028 - seconds * 0.88)
        + 0.34 * np.cos(xx * 0.017 + seconds * 0.55)
    )
    fog_dy = 2.6 * np.sin(xx * 0.021 + seconds * 0.63)

    cloud_warp = cv2.remap(
        frame, xx + cloud_dx, yy + cloud_dy, cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REFLECT_101,
    ).astype(np.float32)
    fog_warp = cv2.remap(
        frame, xx + fog_dx, yy + fog_dy, cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REFLECT_101,
    ).astype(np.float32)
    source = frame.astype(np.float32)
    mixed = source * (1.0 - cloud_mask * 0.72) + cloud_warp * (cloud_mask * 0.72)
    mixed = mixed * (1.0 - fog_mask * 0.78) + fog_warp * (fog_mask * 0.78)
    return np.clip(mixed, 0, 255)


def build_preview(source: Path, output: Path) -> None:
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open source video: {source}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 16.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    ok, first = capture.read()
    if not ok:
        raise RuntimeError(f"Source video contains no frames: {source}")
    cloud_mask, fog_mask = _soft_region_masks(width, height, first)

    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(".part.mp4")
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pixel_format", "bgr24", "-video_size", f"{width}x{height}",
        "-framerate", f"{fps:.9f}", "-i", "-", "-i", str(source),
        "-map", "0:v:0", "-map", "1:a?", "-shortest",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart", str(partial),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    frame_index = 0
    temporal = first.astype(np.float32)
    try:
        frame = first
        while True:
            seconds = frame_index / fps
            # Magnify motion the accepted Wan clip already contains instead of
            # inventing new spatial displacement that could bend cranes or faces.
            moved = frame.astype(np.float32)
            temporal = temporal * 0.90 + moved * 0.10
            atmosphere_mask = np.clip(cloud_mask * 0.86 + fog_mask, 0.0, 1.0)
            detail = moved - temporal
            moved = np.clip(moved + detail * atmosphere_mask * 1.65, 0, 255).astype(np.uint8)
            process.stdin.write(np.ascontiguousarray(moved).tobytes())
            frame_index += 1
            ok, frame = capture.read()
            if not ok:
                break
        process.stdin.close()
        error = process.stderr.read().decode("utf-8", errors="replace").strip()
        return_code = process.wait()
        if return_code:
            raise RuntimeError(error or f"ffmpeg exited {return_code}")
    except BaseException:
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        process.kill()
        process.wait()
        raise
    finally:
        capture.release()
    partial.replace(output)
    print(f"wrote {frame_index} frames to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a cheap cloud/fog motion-boost preview from an accepted clip.")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build_preview(args.source.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
