from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "user/default/workflows/music_visualizer_ti2v5b_full.json"
WORKFLOW = ROOT / "user/default/workflows/music_visualizer_ti2v5b_long_loop.json"
FRAME_COUNT = 121


def _node(workflow, node_id):
    return next(node for node in workflow["nodes"] if node["id"] == node_id)


def build():
    source_bytes = SOURCE.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    workflow = json.loads(source_bytes)

    latent = _node(workflow, 406)
    latent["title"] = f"SOURCE ARTWORK → {FRAME_COUNT}-FRAME LONG-LOOP EXPERIMENT"
    latent["widgets_values"][2] = FRAME_COUNT
    latent.setdefault("widgets_values_named", {})["length"] = FRAME_COUNT

    persist = _node(workflow, 409)
    persist["title"] = "RUN THIS OUTPUT — generate and save 121-frame experiment"
    prefix = "music_visualizer/motion_assets/generated_motion_121f_experiment"
    persist["widgets_values"][1] = prefix
    persist.setdefault("widgets_values_named", {})["output_prefix"] = prefix

    renderer = _node(workflow, 11)
    renderer["title"] = "EXPERIMENT — 121-frame motion + lights + title + EQ"
    output_prefix = "music_visualizer/experiments/ti2v5b_121f/final"
    output_index = next(
        index for index, item in enumerate(renderer["inputs"])
        if item.get("widget", {}).get("name") == "output_prefix"
    )
    widget_index = sum(
        1 for item in renderer["inputs"][:output_index]
        if "widget" in item and item["widget"]["name"] != "upload"
    )
    renderer["widgets_values"][widget_index] = output_prefix
    renderer.setdefault("widgets_values_named", {})["output_prefix"] = output_prefix

    sampler = _node(workflow, 407)
    sampler["title"] = "GENERATE LONGER MOTION — same accepted 20-step quality"

    for group in workflow.get("groups", []):
        if "TI2V 5B" in group.get("title", ""):
            group["title"] = "WAN 2.2 TI2V 5B — 121-FRAME LONG-LOOP EXPERIMENT"

    workflow["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "tws:music-visualizer:ti2v5b:121-frame-experiment"))
    if not WORKFLOW.exists():
        WORKFLOW.write_text(json.dumps(workflow, separators=(",", ":")) + "\n", encoding="utf-8")
        action = "Wrote"
    else:
        # The user-promoted long-loop workflow is authoritative once saved.
        # Validate its contract without reverting its output prefix, prompts,
        # media, layout, or ComfyUI serialization.
        action = "Validated candidate; preserved existing"

    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash
    rebuilt = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    assert _node(rebuilt, 406)["widgets_values_named"]["length"] == FRAME_COUNT
    assert _node(rebuilt, 407)["widgets_values"][2] == 20
    assert _node(rebuilt, 5)["widgets_values_named"]["loop_overlap_seconds"] == 0.8
    assert _node(rebuilt, 11)["widgets_values_named"]["maximum_stabilization_percent"] == 0
    assert isinstance(_node(rebuilt, 11)["widgets_values_named"]["output_prefix"], str)
    assert _node(rebuilt, 11)["widgets_values_named"]["output_prefix"]
    print(f"{action} {WORKFLOW}")
    print(f"Preserved accepted source SHA256 {source_hash.upper()}")
    return WORKFLOW


if __name__ == "__main__":
    build()
