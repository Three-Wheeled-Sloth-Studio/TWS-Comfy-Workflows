from __future__ import annotations

import argparse
import json
from pathlib import Path

from motion_poster_manifest import MotionPosterManifest, load_manifest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "user/default/workflows/video_wan2_2_14B_s2v.json"
TARGET = ROOT / "user/default/workflows/video_wan2_2_14B_s2v_motion_loop.json"
INPUT_ROOT = ROOT / "input"

POSITIVE_PROMPT = (
    "Background motion only. Preserve the subject's identity, face, expression, "
    "mouth position, pose, framing, clothing, and the original composition. "
    "Animate only physically plausible environmental details: hair moves gently "
    "as if blown by a light wind, smoke billows slowly in the background, and "
    "street lights flicker intermittently. Subtle restrained motion, stable "
    "camera, seamless-loop-friendly pacing."
)
NEGATIVE_PROMPT = (
    "lip sync, lips moving, mouth movement, singing, talking, speech, changing "
    "expression, blinking to the beat, face deformation, identity drift, body "
    "movement, dancing, camera shake, rapid zoom, scene change, new objects, "
    "warping, morphing, flicker across the whole image"
)


def rebuild_serialized_links(workflow: dict) -> None:
    by_id = {node["id"]: node for node in workflow["nodes"]}
    for node in workflow["nodes"]:
        for item in node.get("inputs", []):
            item["link"] = None
        for item in node.get("outputs", []):
            item["links"] = None

    for link_id, origin_id, origin_slot, target_id, target_slot, _ in workflow["links"]:
        origin = by_id.get(origin_id)
        target = by_id.get(target_id)
        if origin is None or target is None:
            raise RuntimeError(f"broken link {link_id}: {origin_id} -> {target_id}")
        outputs = origin.get("outputs", [])
        inputs = target.get("inputs", [])
        if origin_slot >= len(outputs) or target_slot >= len(inputs):
            raise RuntimeError(f"invalid slot on link {link_id}")
        outputs[origin_slot].setdefault("links", [])
        if outputs[origin_slot]["links"] is None:
            outputs[origin_slot]["links"] = []
        outputs[origin_slot]["links"].append(link_id)
        inputs[target_slot]["link"] = link_id


def _input_name(path: Path) -> str:
    try:
        return path.resolve().relative_to(INPUT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"ComfyUI input must be under {INPUT_ROOT}: {path}") from exc


def build(target: Path, manifest: MotionPosterManifest | None = None) -> None:
    workflow = json.loads(SOURCE.read_text(encoding="utf-8"))
    removed = {85, 87}
    workflow["nodes"] = [
        node for node in workflow["nodes"] if node["id"] not in removed
    ]
    workflow["links"] = [
        link
        for link in workflow["links"]
        if link[1] not in removed and link[3] not in removed
    ]
    by_id = {node["id"]: node for node in workflow["nodes"]}

    width = manifest.generation.width if manifest else 832
    height = manifest.generation.height if manifest else 480
    positive_prompt = (
        manifest.generation.positive_prompt if manifest else POSITIVE_PROMPT
    )
    negative_prompt = (
        manifest.generation.negative_prompt if manifest else NEGATIVE_PROMPT
    )
    by_id[93]["widgets_values"] = [width, height, 77, 1]
    by_id[93]["widgets_values_named"].update(
        {"width": width, "height": height}
    )
    by_id[6]["widgets_values"] = [positive_prompt]
    by_id[6]["widgets_values_named"] = {"text": positive_prompt}
    by_id[7]["widgets_values"] = [negative_prompt]
    by_id[7]["widgets_values_named"] = {"text": negative_prompt}
    if manifest:
        by_id[52]["widgets_values"][0] = _input_name(
            manifest.reference_image_paths[0]
        )
        by_id[52]["widgets_values_named"]["image"] = by_id[52][
            "widgets_values"
        ][0]
        by_id[58]["widgets_values"][0] = _input_name(manifest.audio_path)
        by_id[58]["widgets_values_named"]["audio"] = by_id[58][
            "widgets_values"
        ][0]
    by_id[100]["widgets_values"] = [2, "fixed"]
    by_id[100]["widgets_values_named"] = {"value": 2, "fixed": "fixed"}
    by_id[113]["widgets_values"][0] = "video/motion_loop_16x9"
    by_id[113]["widgets_values_named"]["filename_prefix"] = (
        "video/motion_loop_16x9"
    )

    next_link = max(link[0] for link in workflow["links"])
    for target_id, target_slot in ((94, 0), (95, 1)):
        next_link += 1
        workflow["links"].append(
            [next_link, 79, 0, target_id, target_slot, "LATENT"]
        )

    note_id = max(by_id) + 1
    workflow["nodes"].append(
        {
            "id": note_id,
            "type": "MarkdownNote",
            "pos": [760, 850],
            "size": [560, 360],
            "flags": {},
            "order": 11,
            "mode": 0,
            "inputs": [],
            "outputs": [],
            "properties": {},
            "widgets_values": [
                "## Native 16:9 motion-loop asset\n\n"
                "This workflow renders about 9.5 seconds at **832×480 / 16 fps**. "
                "It is intentionally short; the deterministic renderer assembles "
                "the full song.\n\nEdit the positive prompt with concrete, "
                "physically plausible motion. Keep the preservation language and "
                "the negative prompt when the subject should not sing. Lyrics or "
                "a short song-theme summary may be appended as atmosphere/context, "
                "but should not override the explicit motion instructions.\n\n"
                "For variety, queue this workflow again with a new initial seed and "
                "keep two or three successful outputs. Do not use variants that "
                "change identity, mouth position, framing, or scene content."
            ],
            "widgets_values_named": {
                "text": "Native 16:9 motion-loop generation guidance."
            },
            "title": "Motion-loop instructions",
            "color": "#223",
            "bgcolor": "#335",
        }
    )

    workflow["last_node_id"] = note_id
    workflow["last_link_id"] = next_link
    workflow["revision"] = int(workflow.get("revision", 0)) + 1
    workflow.setdefault("state", {})["lastNodeId"] = note_id
    workflow["state"]["lastLinkId"] = next_link
    rebuild_serialized_links(workflow)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(workflow, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
        newline="\n",
    )
    print(target)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the native 16:9 Wan motion-loop workflow."
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path, default=TARGET)
    args = parser.parse_args()
    manifest = load_manifest(args.manifest) if args.manifest else None
    build(args.output.resolve(), manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
