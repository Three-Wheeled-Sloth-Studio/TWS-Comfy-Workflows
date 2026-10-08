from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "user/default/workflows/video_wan2_2_14B_s2v_motion_poster_guided.json"
TARGET = ROOT / "user/default/workflows/video_wan2_2_14B_s2v_motion_poster_visualizer.json"

VISUALIZER_DEFAULTS = {
    "animate_brand_logo": True,
    "visualizer_color_strength": 0.70,
    "visualizer_min_brightness": 0.65,
    "visualizer_max_brightness": 1.20,
    "visualizer_response_seconds": 0.20,
    "visualizer_halo_extent_percent": 35.0,
}


def _widget_input(name: str, data_type: str) -> dict:
    return {
        "name": name,
        "type": data_type,
        "link": None,
        "widget": {"name": name},
    }


def main() -> int:
    workflow = json.loads(SOURCE.read_text(encoding="utf-8"))
    nodes = {node["id"]: node for node in workflow["nodes"]}
    assembler = nodes[110]
    note = nodes[111]

    assembler["type"] = "MotionPosterVisualizerAssemble"
    assembler["title"] = "3. Assemble with audio-reactive logo"
    assembler["size"] = [560, 930]
    assembler["properties"]["Node name for S&R"] = (
        "MotionPosterVisualizerAssemble"
    )
    assembler["inputs"].extend(
        [
            _widget_input("animate_brand_logo", "BOOLEAN"),
            _widget_input("visualizer_color_strength", "FLOAT"),
            _widget_input("visualizer_min_brightness", "FLOAT"),
            _widget_input("visualizer_max_brightness", "FLOAT"),
            _widget_input("visualizer_response_seconds", "FLOAT"),
            _widget_input("visualizer_halo_extent_percent", "FLOAT"),
        ]
    )
    assembler["widgets_values"][0] = True
    assembler["widgets_values"][19] = (
        "motion_poster/guided_motion_poster_visualizer"
    )
    assembler["widgets_values"].extend(VISUALIZER_DEFAULTS.values())
    assembler["widgets_values_named"]["apply_brand_logo"] = True
    assembler["widgets_values_named"]["output_prefix"] = (
        "motion_poster/guided_motion_poster_visualizer"
    )
    assembler["widgets_values_named"].update(VISUALIZER_DEFAULTS)

    instructions = (
        "# Guided motion poster — logo visualizer experiment\n\n"
        "This is a separate copy of the production 1024×576 workflow. "
        "Generation, prompting, title halo, and delivery behave the same.\n\n"
        "The lower-right brand logo is enabled and animated after generation. "
        "Twelve note-colored frequency bands per channel form a radial spectrum: "
        "left/right channels occupy their respective sides, low bands start at "
        "the bottom, and high bands finish at the top. Band energy controls bar "
        "length and brightness. The logo stays clean inside the halo.\n\n"
        "Start with color strength `0.70`, brightness `0.65–1.20`, response "
        "`0.20` seconds, and halo extent `35%`. Increase response time if the "
        "bars change too quickly. "
        "Disable `animate_brand_logo` to fall back to the normal static logo."
    )
    note["title"] = "Start here — visualizer experiment"
    note["widgets_values"] = [instructions]
    note["widgets_values_named"] = {"text": instructions}

    if assembler["inputs"][-6]["name"] != "animate_brand_logo":
        raise RuntimeError("visualizer controls are not serialized correctly")
    if nodes[93]["widgets_values"][0:2] != [1024, 576]:
        raise RuntimeError("visualizer workflow must preserve 1024x576 generation")
    workflow["revision"] = int(workflow.get("revision", 0)) + 1
    TARGET.write_text(
        json.dumps(workflow, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
        newline="\n",
    )
    print(TARGET)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
