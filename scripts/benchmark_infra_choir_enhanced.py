from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMFY_SOURCE = Path(r"C:\Users\sloth\ComfyUI-Installs\ComfyUI\ComfyUI")
BASE_WORKFLOW = ROOT / "user/default/workflows/music_visualizer_infra_choir_production.json"
ENHANCED_WORKFLOW = ROOT / "user/default/workflows/music_visualizer_infra_choir_enhanced.json"
INPUT_IMAGE = ROOT / "input/Bella Ciao.png"
INPUT_AUDIO = ROOT / "input/Bella Ciao.mp3"
OUTPUT_ROOT = Path(r"D:\comfyDesktop\output\infra_choir_enhanced_validation")


def _load_runtime():
    sys.path.insert(0, str(COMFY_SOURCE))
    sys.path.insert(0, str(ROOT))
    import folder_paths

    folder_paths.models_dir = r"D:\comfyDesktop\models\local"
    folder_paths.set_input_directory(r"D:\comfyDesktop\input")
    folder_paths.set_output_directory(str(OUTPUT_ROOT))
    folder_paths.set_temp_directory(r"D:\comfyDesktop\temp")
    from custom_nodes.comfyui_audio_duration_plan.local_visualizer_nodes import (
        InfraChoirAnimationTarget,
        InfraChoirAnimationTargetEnhanced,
        InfraChoirVisualizer,
        InfraChoirVisualizerEnhanced,
        VisualizerSemanticObjectDetector,
    )
    return (
        InfraChoirAnimationTarget,
        InfraChoirAnimationTargetEnhanced,
        InfraChoirVisualizer,
        InfraChoirVisualizerEnhanced,
        VisualizerSemanticObjectDetector,
    )


def _load_image(path: Path):
    import numpy as np
    import torch
    from PIL import Image, ImageOps

    with Image.open(path) as opened:
        pixels = np.asarray(ImageOps.exif_transpose(opened).convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(pixels)[None, ...]


def _load_audio(path: Path, limit_seconds: float | None):
    import numpy as np
    import torch

    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path)]
    if limit_seconds is not None:
        command.extend(["-t", f"{limit_seconds:.6f}"])
    command.extend(["-f", "f32le", "-acodec", "pcm_f32le", "-ac", "2", "-ar", "48000", "-"])
    result = subprocess.run(command, check=True, capture_output=True)
    samples = np.frombuffer(result.stdout, dtype="<f4").copy().reshape(-1, 2).T
    return {"waveform": torch.from_numpy(samples)[None, ...], "sample_rate": 48000}


def _widget_kwargs(node: dict) -> dict:
    names = [value["name"] for value in node.get("inputs", []) if value.get("widget")]
    values = node.get("widgets_values", [])
    if len(names) != len(values):
        raise ValueError(f"Node {node['id']} has {len(names)} widget inputs but {len(values)} serialized values.")
    return dict(zip(names, values))


def _monitor(stop: threading.Event, result: dict) -> None:
    import psutil

    process = psutil.Process(os.getpid())
    while not stop.wait(0.5):
        rss = process.memory_info().rss
        for child in process.children(recursive=True):
            try:
                rss += child.memory_info().rss
            except psutil.Error:
                pass
        result["peak_rss_bytes"] = max(result.get("peak_rss_bytes", 0), rss)
        try:
            query = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2, check=True,
            ).stdout.splitlines()[0]
            memory, utilization = (int(part.strip()) for part in query.split(",")[:2])
            result["peak_gpu_mib"] = max(result.get("peak_gpu_mib", 0), memory)
            result["peak_gpu_utilization"] = max(result.get("peak_gpu_utilization", 0), utilization)
        except (OSError, ValueError, subprocess.SubprocessError, IndexError):
            pass


def _detect_masks(image, workflow: dict, detector_class) -> dict[int, object]:
    detector = detector_class()
    masks = {}
    for node_id in range(10, 80, 10):
        node = next(item for item in workflow["nodes"] if item["id"] == node_id)
        settings = _widget_kwargs(node)
        mask, _, _, report = detector.detect(image=image, **settings)
        masks[node_id + 2] = mask
        print(f"MASK {node_id + 2}: {report}", flush=True)
    detector_class._semantic_model = None
    detector_class._semantic_processor = None
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
    return masks


def _targets(workflow: dict, masks: dict, target_class) -> tuple:
    outputs = []
    for node in workflow["nodes"]:
        if not node["type"].startswith("InfraChoirAnimationTarget"):
            continue
        settings = _widget_kwargs(node)
        settings["mask_verified"] = True
        target, diagnostic, _ = target_class().configure(mask=masks[node["id"]], **settings)
        if diagnostic.endswith("ready"):
            outputs.append(target)
        else:
            raise RuntimeError(diagnostic)
    return tuple(outputs)


def _render(label: str, workflow: dict, image, audio, masks: dict, target_class, renderer_class, smoke: bool, disable_enhancements: bool = False) -> dict:
    renderer_node = next(node for node in workflow["nodes"] if node["type"].startswith("InfraChoirVisualizer"))
    settings = _widget_kwargs(renderer_node)
    settings["output_prefix"] = f"infra_choir_enhanced_validation/{label}"
    if smoke:
        settings["fps"] = 8
        settings["delivery_resolution"] = "720p"
    if disable_enhancements and "enhancements_enabled" in settings:
        settings["enhancements_enabled"] = False
    targets = _targets(workflow, masks, target_class)
    monitor_result = {}
    stop = threading.Event()
    thread = threading.Thread(target=_monitor, args=(stop, monitor_result), daemon=True)
    started = time.perf_counter()
    thread.start()
    try:
        result = renderer_class().render(image=image, audio=audio, targets=targets, **settings)
    finally:
        stop.set()
        thread.join(timeout=3)
    elapsed = time.perf_counter() - started
    output_path, qa_report = result["result"]
    return {"label": label, "output_path": output_path, "wall_seconds": elapsed, "qa_report": qa_report, **monitor_result}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="Render four seconds at 720p/8 fps instead of the complete song.")
    parser.add_argument("--enhanced-only", action="store_true")
    parser.add_argument("--enhancements-disabled", action="store_true", help="Run the enhanced node with its master switch off for regression comparison.")
    parser.add_argument("--report", type=Path, default=OUTPUT_ROOT / "benchmark.json")
    args = parser.parse_args()
    classes = _load_runtime()
    base_target, enhanced_target, base_renderer, enhanced_renderer, detector = classes
    base_workflow = json.loads(BASE_WORKFLOW.read_text(encoding="utf-8"))
    enhanced_workflow = json.loads(ENHANCED_WORKFLOW.read_text(encoding="utf-8"))
    image = _load_image(INPUT_IMAGE)
    audio = _load_audio(INPUT_AUDIO, 4.0 if args.smoke else None)
    masks = _detect_masks(image, enhanced_workflow, detector)
    results = []
    if not args.enhanced_only:
        results.append(_render("baseline_full" if not args.smoke else "baseline_smoke", base_workflow, image, audio, masks, base_target, base_renderer, args.smoke))
    enhanced_label = "enhanced_full" if not args.smoke else "enhanced_smoke"
    if args.enhancements_disabled:
        enhanced_label += "_disabled"
    results.append(_render(enhanced_label, enhanced_workflow, image, audio, masks, enhanced_target, enhanced_renderer, args.smoke, args.enhancements_disabled))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
