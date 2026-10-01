from __future__ import annotations

import subprocess
import sys
from pathlib import PurePosixPath


ALLOWED_ROOT_FILES = {
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "LICENSE",
    "README.md",
    "build_auto_s2v_windowed_workflow.py",
    "build_auto_s2v_workflow.py",
    "diagnose-comfyui-model-paths.bat",
    "diagnose-comfyui-model-paths.ps1",
    "install-models.bat",
    "install-models.ps1",
    "install-music-video-models.bat",
    "install-music-video-models.ps1",
    "setup-music-video-workflow.bat",
    "setup-music-video-workflow.ps1",
}
ALLOWED_PREFIXES = (".github/", "assets/", "refs/", "scripts/", "custom_nodes/comfyui_audio_duration_plan/")
ALLOWED_WORKFLOWS = {
    "user/default/workflows/video_wan2_2_14B_s2v.json",
    "user/default/workflows/video_wan2_2_14B_s2v_auto_duration.json",
    "user/default/workflows/video_wan2_2_14B_s2v_auto_duration_windowed.json",
    "user/default/workflows/video_wan2_2_14B_s2v_motion_loop.json",
}
FORBIDDEN_SUFFIXES = {
    ".bin", ".ckpt", ".flac", ".gif", ".jpeg", ".jpg", ".mkv", ".mov",
    ".mp3", ".mp4", ".onnx", ".png", ".pt", ".pth", ".safetensors",
    ".wav", ".webm", ".webp",
}


def tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], check=True, capture_output=True
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def main() -> int:
    failures: list[str] = []
    folded: dict[str, str] = {}
    for path in tracked_paths():
        normalized = path.replace("\\", "/")
        lower = normalized.casefold()
        previous = folded.setdefault(lower, normalized)
        if previous != normalized:
            failures.append(f"case collision: {previous} <> {normalized}")

        allowed = (
            normalized in ALLOWED_ROOT_FILES
            or normalized in ALLOWED_WORKFLOWS
            or normalized.startswith(ALLOWED_PREFIXES)
        )
        if not allowed:
            failures.append(f"path outside repository allowlist: {normalized}")

        suffix = PurePosixPath(normalized).suffix.casefold()
        if suffix in FORBIDDEN_SUFFIXES:
            failures.append(f"binary/model/media file is forbidden: {normalized}")

    if failures:
        print("Repository scope validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"Repository scope validation passed for {len(tracked_paths())} tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
