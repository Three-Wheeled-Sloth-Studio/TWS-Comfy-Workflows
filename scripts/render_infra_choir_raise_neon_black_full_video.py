from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMFY_SOURCE = Path(r"C:\Users\sloth\ComfyUI-Installs\ComfyUI\ComfyUI")
INPUT_ROOT = Path(r"D:\comfyDesktop\input")
OUTPUT_ROOT = Path(r"D:\comfyDesktop\output")
TEMP_ROOT = Path(r"D:\comfyDesktop\temp")
PROMPT = ROOT / "refs/evaluations/2026-10-20-raise-neon-black-full-api-prompt.json"
NODE_MODULE = ROOT / "custom_nodes/comfyui_audio_duration_plan/local_visualizer_nodes.py"


def _load_runtime():
    sys.path[:0] = [str(COMFY_SOURCE), str(ROOT)]
    import folder_paths

    folder_paths.set_input_directory(str(INPUT_ROOT))
    folder_paths.set_output_directory(str(OUTPUT_ROOT))
    folder_paths.set_temp_directory(str(TEMP_ROOT))
    specification = importlib.util.spec_from_file_location("infra_choir_raise_neon_black_renderer", NODE_MODULE)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module.InfraChoirManualTargetCompact, module.InfraChoirVisualizerDualTrack


def _image_tensor(path: Path):
    import numpy as np
    import torch
    from PIL import Image, ImageOps

    with Image.open(path) as opened:
        pixels = np.asarray(ImageOps.exif_transpose(opened).convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(pixels)[None, ...]


def _mask_tensor(path: Path):
    import numpy as np
    import torch
    from PIL import Image

    with Image.open(path) as opened:
        pixels = np.asarray(opened.convert("L"), dtype=np.float32) / 255.0
    return torch.from_numpy(pixels)[None, ...]


def _audio_tensor(path: Path, seconds: float | None):
    import numpy as np
    import torch

    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path)]
    if seconds is not None:
        command.extend(["-t", f"{seconds:.6f}"])
    command.extend(["-f", "f32le", "-acodec", "pcm_f32le", "-ac", "2", "-ar", "48000", "-"])
    decoded = subprocess.run(command, check=True, capture_output=True).stdout
    samples = np.frombuffer(decoded, dtype="<f4").copy().reshape(-1, 2).T
    return {"waveform": torch.from_numpy(samples)[None, ...], "sample_rate": 48000}


def _target(node: dict, mask, target_class):
    values = {key: value for key, value in node["inputs"].items() if key not in {"mask", "use_in_render"}}
    target, diagnostic, _ = target_class().configure(mask=mask, use_in_render=True, **values)
    if not diagnostic.endswith(": ready"):
        raise RuntimeError(diagnostic)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the wired Raise the Neon Black hybrid workflow directly.")
    parser.add_argument("--seconds", type=float, help="Render only the first N seconds for a validation probe.")
    parser.add_argument("--output-prefix", help="Override the saved workflow output prefix.")
    args = parser.parse_args()

    target_class, renderer_class = _load_runtime()
    prompt = json.loads(PROMPT.read_text(encoding="utf-8"))
    image_name = prompt["1"]["inputs"]["image"]
    audio_name = prompt["2"]["inputs"]["audio"]
    light_mask_name = prompt["7"]["inputs"]["image"]
    image = _image_tensor(INPUT_ROOT / image_name)
    audio = _audio_tensor(INPUT_ROOT / audio_name, args.seconds)

    import torch

    height, width = image.shape[1:3]
    motion_mask = torch.ones((1, height, width), dtype=torch.float32)
    light_mask = _mask_tensor(INPUT_ROOT / light_mask_name)
    targets = (
        _target(prompt["5"], motion_mask, target_class),
        _target(prompt["9"], light_mask, target_class),
    )
    motion = targets[0]
    print(
        "MOTION TARGET: "
        f"mode={motion['atmospheric_motion_mode']} "
        f"clip={motion['generated_clip_path']} "
        f"strength={motion['generated_motion_strength']}",
        flush=True,
    )

    settings = {
        key: value for key, value in prompt["11"]["inputs"].items()
        if key not in {"image", "audio", "targets"}
    }
    if args.output_prefix:
        settings["output_prefix"] = args.output_prefix
    result = renderer_class().render(image=image, audio=audio, targets=targets, **settings)
    output_path, qa_report = result["result"]
    print(f"OUTPUT: {output_path}", flush=True)
    print(f"QA: {qa_report}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
