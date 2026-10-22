from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD = ROOT / "user/default/workflows/music_visualizer_infra_choir_dual_track_scaffold.json"
GUIDED_WAN = ROOT / "user/default/workflows/video_wan2_2_14B_s2v_motion_poster_guided.json"
WORKFLOW = ROOT / "user/default/workflows/music_visualizer_cached_motion_full_song.json"
USER_WORKFLOW = ROOT / "user/default/workflows/music_visualizer_cached_motion_full.json"


def _link(link_id: int, origin: int, origin_slot: int, target: int, target_slot: int, kind: str) -> list:
    return [link_id, origin, origin_slot, target, target_slot, kind]


def _named(node: dict, values: dict) -> None:
    names = [item["widget"]["name"] for item in node["inputs"] if "widget" in item]
    node["widgets_values"] = [values[name] for name in names]
    node["widgets_values_named"] = dict(values)


def _upgrade_cached_motion_ui(workflow: dict) -> dict:
    """Upgrade only the cached-motion card and preview branch; preserve saved layout and media."""
    nodes = {int(node["id"]): node for node in workflow["nodes"]}
    old = nodes[5]
    old.update({
        "type": "InfraChoirGeneratedMotionTarget",
        "size": [500, 180],
        "title": "GENERATED MOTION — connected from Wan animation",
        "inputs": [
            {"localized_name": "mask", "name": "mask", "type": "MASK", "link": 1},
            {"localized_name": "generated_motion", "name": "generated_motion", "type": "IMAGE", "link": 2000},
            {"localized_name": "use_in_render", "name": "use_in_render", "type": "BOOLEAN", "link": 2},
            {"localized_name": "generated_motion_strength", "name": "generated_motion_strength", "type": "FLOAT", "widget": {"name": "generated_motion_strength"}, "link": None},
            {"localized_name": "loop_overlap_seconds", "name": "loop_overlap_seconds", "type": "FLOAT", "widget": {"name": "loop_overlap_seconds"}, "link": None},
        ],
        "outputs": [
            {"localized_name": "animation_target", "name": "animation_target", "type": "LOCAL_VISUALIZER_TARGET", "links": [3]},
            {"localized_name": "diagnostic", "name": "diagnostic", "type": "STRING", "links": None},
            {"localized_name": "configuration_json", "name": "configuration_json", "type": "STRING", "links": None},
        ],
        "properties": {"Node name for S&R": "InfraChoirGeneratedMotionTarget"},
        "widgets_values": [1.0, 0.8],
        "widgets_values_named": {
            "generated_motion_strength": 1.0,
            "loop_overlap_seconds": 0.8,
        },
    })
    nodes[4]["title"] = "INCLUDE generated Wan animation"
    nodes[4]["widgets_values"] = [True]
    nodes[4]["widgets_values_named"] = {"value": True}
    nodes[11]["title"] = "FULL SONG — generated motion + source lights + title + EQ"

    detector = nodes[7]
    detector.update({
        "type": "InfraChoirMultiLightDetector",
        "size": [440, 250],
        "title": "DETECT UP TO 7 LIGHT CANDIDATES ON CURRENT SOURCE",
        "inputs": [
            {"localized_name": "image", "name": "image", "type": "IMAGE", "link": 4},
            {"localized_name": "sensitivity", "name": "sensitivity", "type": "FLOAT", "widget": {"name": "sensitivity"}, "link": None},
            {"localized_name": "max_candidates", "name": "max_candidates", "type": "INT", "widget": {"name": "max_candidates"}, "link": None},
            {"localized_name": "padding_percent", "name": "padding_percent", "type": "FLOAT", "widget": {"name": "padding_percent"}, "link": None},
            {"localized_name": "use_in_render", "name": "use_in_render", "type": "BOOLEAN", "widget": {"name": "use_in_render"}, "link": None},
        ],
        "properties": {"Node name for S&R": "InfraChoirMultiLightDetector"},
        "widgets_values": [0.48, 7, 2.0, True],
        "widgets_values_named": {"sensitivity": 0.48, "max_candidates": 7, "padding_percent": 2.0, "use_in_render": True},
    })
    preview = next((node for node in workflow["nodes"] if node.get("type") == "PreviewImage" and node.get("title") == "RUN THIS OUTPUT — preview detected lights"), None)
    if preview is None:
        review = nodes[8]
        preview = {
            "id": 12, "type": "PreviewImage",
            "pos": [review["pos"][0], review["pos"][1] + float(review.get("size", [390, 360])[1]) + 70],
            "size": [392, 300], "flags": {}, "order": 8, "mode": 0,
            "inputs": [{"name": "images", "type": "IMAGE", "link": 15}], "outputs": [],
            "properties": {"cnr_id": "comfy-core", "ver": "0.9.2", "Node name for S&R": "PreviewImage"},
            "widgets_values": [], "title": "RUN THIS OUTPUT — preview detected lights",
        }
        workflow["nodes"].append(preview)
    detector["outputs"][1]["links"] = list(dict.fromkeys([*(detector["outputs"][1].get("links") or []), 15]))
    workflow["links"] = [link for link in workflow["links"] if link[0] != 15]
    workflow["links"].append(_link(15, 7, 1, int(preview["id"]), 0, "IMAGE"))
    workflow["last_node_id"] = max(int(workflow.get("last_node_id", 0)), int(preview["id"]))
    workflow["last_link_id"] = max(int(workflow.get("last_link_id", 0)), 15)
    return workflow


def _attach_wan_generation(workflow: dict) -> dict:
    """Attach the proven guided Wan generator without moving the user's compositor nodes."""
    workflow["nodes"] = [node for node in workflow["nodes"] if node.get("properties", {}).get("tws_stage") != "wan_generation"]
    workflow["links"] = [link for link in workflow["links"] if int(link[0]) < 1000]
    for node in workflow["nodes"]:
        for output in node.get("outputs", []):
            if output.get("links"):
                output["links"] = [link for link in output["links"] if int(link) < 1000]

    guided = json.loads(GUIDED_WAN.read_text(encoding="utf-8"))
    dependencies = {3, 6, 7, 37, 38, 39, 52, 54, 56, 57, 58, 79, 80, 93, 94, 95, 96, 100, 103, 104, 105, 107, 108, 109}
    substitutions = {52: 1, 58: 2}
    copied_ids = dependencies - substitutions.keys()
    node_map = {old: old + 200 for old in copied_ids} | substitutions
    copied_types = {str(node["type"]) for node in guided["nodes"] if node["id"] in copied_ids}
    existing_definitions = copy.deepcopy(workflow.get("definitions", {}).get("subgraphs", []))
    definitions_by_id = {str(item["id"]): item for item in existing_definitions}
    for definition in guided.get("definitions", {}).get("subgraphs", []):
        if str(definition.get("id")) in copied_types:
            definitions_by_id[str(definition["id"])] = copy.deepcopy(definition)
    if definitions_by_id:
        workflow["definitions"] = {"subgraphs": list(definitions_by_id.values())}
    selected_links = [link for link in guided["links"] if link[1] in dependencies and link[3] in dependencies]
    link_map = {link[0]: 1000 + index for index, link in enumerate(selected_links)}

    copied = []
    for original in guided["nodes"]:
        if original["id"] not in copied_ids:
            continue
        node = copy.deepcopy(original)
        node["id"] = node_map[original["id"]]
        node["pos"] = [float(node["pos"][0]) - 3800.0, float(node["pos"][1])]
        node["order"] = int(node.get("order", 0)) + 100
        node.setdefault("properties", {})["tws_stage"] = "wan_generation"
        for item in node.get("inputs", []):
            if item.get("link") is not None:
                item["link"] = link_map.get(item["link"])
        for item in node.get("outputs", []):
            if item.get("links"):
                mapped = [link_map[value] for value in item["links"] if value in link_map]
                item["links"] = mapped or None
        copied.append(node)
    workflow["nodes"].extend(copied)

    remapped_links = [
        _link(link_map[link[0]], node_map[link[1]], link[2], node_map[link[3]], link[4], link[5])
        for link in selected_links
    ]
    workflow["links"].extend(remapped_links)
    nodes = {int(node["id"]): node for node in workflow["nodes"]}
    for original_id, replacement_id in substitutions.items():
        original = next(node for node in guided["nodes"] if node["id"] == original_id)
        replacement = nodes[replacement_id]
        for slot, output in enumerate(original.get("outputs", [])):
            mapped = [link_map[value] for value in (output.get("links") or []) if value in link_map]
            if mapped:
                current = replacement["outputs"][slot].get("links") or []
                replacement["outputs"][slot]["links"] = list(dict.fromkeys([*current, *mapped]))

    workflow["links"] = [link for link in workflow["links"] if link[0] != 2]
    workflow["links"].append(_link(2, 4, 0, 5, 2, "BOOLEAN"))
    nodes[4]["outputs"][0]["links"] = [2]
    generated_id = node_map[96]
    generated_output = nodes[generated_id]["outputs"][0]
    generated_output["links"] = list(dict.fromkeys([*(generated_output.get("links") or []), 2000]))
    workflow["links"].append(_link(2000, generated_id, 0, 5, 1, "IMAGE"))
    nodes[5]["inputs"][1]["link"] = 2000
    nodes[5]["inputs"][2]["link"] = 2
    guidance = nodes[node_map[108]]
    positive = (
        "Locked camera and composition. Generate ample, clearly visible, voluminous smoke, fog, mist, and cloud "
        "billowing where those elements exist. Hair and loose fabric flow naturally in a steady breeze. Flags wave, "
        "water waves ripple, and underwater tentacles wriggle where present. Preserve faces, bodies, architecture, "
        "objects, framing, and identity. Other environmental movement may be subtle and physically plausible. "
        "Do not animate light sources spatially; lighting flicker is added later by the compositor."
    )
    targets = (
        "smoke fog mist clouds: strong voluminous billowing; hair and loose fabric: natural breeze; "
        "flags: visible waving; water: rippling waves; underwater tentacles: organic wriggling"
    )
    guidance["widgets_values"][0] = positive
    guidance["widgets_values"][2] = False
    guidance["widgets_values"][3] = targets
    if guidance.get("widgets_values_named"):
        guidance["widgets_values_named"].update({
            "positive_prompt": positive, "allow_lip_motion": False, "motion_targets": targets,
        })
    workflow["last_node_id"] = max(int(node["id"]) for node in workflow["nodes"])
    workflow["last_link_id"] = max(int(link[0]) for link in workflow["links"])
    state = workflow.setdefault("state", {})
    state["lastNodeId"] = workflow["last_node_id"]
    state["lastLinkId"] = workflow["last_link_id"]
    state["lastGroupId"] = max((int(group.get("id", 0)) for group in workflow.get("groups", [])), default=0)
    return workflow


def build() -> Path:
    source = json.loads(SCAFFOLD.read_text(encoding="utf-8"))
    nodes = {int(node["id"]): node for node in source["nodes"]}

    image = copy.deepcopy(nodes[1])
    audio = copy.deepcopy(nodes[2])
    motion_target = copy.deepcopy(nodes[12])
    stack_one = copy.deepcopy(nodes[13])
    light_detector = copy.deepcopy(nodes[50])
    light_review = copy.deepcopy(nodes[51])
    light_target = copy.deepcopy(nodes[52])
    stack_two = copy.deepcopy(nodes[53])
    renderer = copy.deepcopy(nodes[90])

    image.update({"id": 1, "pos": [40, 80], "title": "1. SELECT SOURCE ARTWORK", "order": 0})
    image["widgets_values"] = ["", "image"]
    image["widgets_values_named"] = {"image": "", "upload": "image"}
    image["outputs"][0]["links"] = [4, 7, 12]
    audio.update({"id": 2, "pos": [40, 430], "title": "2. SELECT FINAL SONG AUDIO", "order": 1})
    audio["widgets_values"] = ["", None]
    audio["widgets_values_named"] = {"audio": "", "upload": None}
    audio["outputs"][0]["links"] = [13]

    solid = {
        "id": 3, "type": "SolidMask", "pos": [430, 80], "size": [270, 106], "flags": {}, "order": 2, "mode": 0,
        "inputs": [], "outputs": [{"name": "MASK", "type": "MASK", "links": [1]}],
        "properties": {"cnr_id": "comfy-core", "ver": "0.9.2", "Node name for S&R": "SolidMask"},
        "widgets_values": [1.0, 1920, 1080], "widgets_values_named": {"value": 1.0, "width": 1920, "height": 1080},
        "title": "Full-frame mask (automatically fitted to source)",
    }
    motion_bool = {
        "id": 4, "type": "PrimitiveBoolean", "pos": [430, 220], "size": [270, 58], "flags": {}, "order": 3, "mode": 0,
        "inputs": [], "outputs": [{"name": "BOOLEAN", "type": "BOOLEAN", "links": [2]}],
        "properties": {"Node name for S&R": "PrimitiveBoolean"}, "widgets_values": [False],
        "widgets_values_named": {"value": False}, "title": "ENABLE after selecting cached motion clip",
    }
    motion_advanced = {
        "motion_source": "generated_clip", "generated_motion_strength": 1.0,
        "atmospheric_motion_mode": "cached_clip", "generated_clip_path": "",
        "generated_clip_max_seconds": 10.0, "generated_clip_overlap_seconds": 0.8,
        "audio_driver": "slow", "secondary_audio_driver": "none", "secondary_driver_mix": 0.0,
        "on_beat_motion": 0.0, "response_min": 0.0, "response_max": 1.0,
        "foreground_protection": False, "target_id": "cached_full_scene_motion",
    }
    motion_values = {
        "target_id": "cached_full_scene_motion", "object_name": "cached full-scene motion",
        "animation_prompt": "Loop the reviewed motion clip without adding procedural geometry motion.",
        "target_role": "organic", "linked_group": "environment", "motion_type": "still",
        "beat_flicker": 0.0, "ambient_flicker": 0.0, "motion_amount": 0.0,
        "max_luminance_change": 0.0, "glow_strength": 0.0, "glow_radius_px": 0.0,
        "saturation_variation": 0.0, "hue_variation_degrees": 0.0,
        "advanced_settings_json": json.dumps(motion_advanced, separators=(",", ":")),
        "advanced_settings": None,
    }
    motion_target.update({"id": 5, "pos": [740, 60], "title": "CACHED MOTION — set clip path in Advanced Settings", "order": 4})
    motion_target["inputs"][0]["link"] = 1
    motion_target["inputs"][1]["link"] = 2
    motion_target["outputs"][0]["links"] = [3]
    motion_target["widgets_values_named"] = motion_values
    motion_target["widgets_values"] = [False] + [motion_values[item["name"]] for item in motion_target["inputs"] if item.get("link") is None] + [None]

    stack_one.update({"id": 6, "pos": [1110, 110], "order": 5})
    stack_one["inputs"] = [{"localized_name": "target", "name": "target", "type": "LOCAL_VISUALIZER_TARGET", "link": 3}]
    stack_one["outputs"][0]["links"] = [11]

    light_detector.update({"id": 7, "pos": [430, 470], "title": "DETECT LIGHTS ON CURRENT SOURCE — include in render", "order": 6})
    light_detector["inputs"][0]["link"] = 4
    detector_values = {
        "find": "lights, lamps, flames, emissive signs, bright reflections",
        "search_area": "box 0 0 1 1", "sensitivity": 0.65, "max_regions": 12,
        "padding_percent": 2.0, "detection_provider": "semantic_or_heuristic", "use_in_render": True,
    }
    light_detector["widgets_values_named"] = detector_values
    light_detector["widgets_values"] = [detector_values[item["name"]] for item in light_detector["inputs"] if item.get("link") is None]
    for output in light_detector["outputs"]:
        output["links"] = None
    light_detector["outputs"][0]["links"] = [5]
    light_detector["outputs"][1]["links"] = [6]
    light_detector["outputs"][4]["links"] = [9]

    light_review.update({"id": 8, "pos": [800, 470], "title": "REVIEW / EDIT LIGHT MASK FOR CURRENT SOURCE", "order": 7})
    light_review["inputs"][0]["link"] = 6
    light_review["inputs"][1]["link"] = 5
    light_review["inputs"][2]["link"] = 7
    light_review["outputs"][0]["links"] = [8]
    light_review["widgets_values"] = ["", "", None]
    light_review["widgets_values_named"] = {"image": "", "source_fingerprint": "", "upload": None}

    light_advanced = {
        "motion_source": "procedural", "generated_motion_strength": 0.0, "audio_driver": "beat",
        "secondary_audio_driver": "high", "secondary_driver_mix": 0.22, "on_beat_motion": 0.0,
        "response_attack_ms": 32.0, "response_decay_ms": 150.0, "response_release_ms": 240.0,
        "response_smoothing": 0.10, "response_min": 0.0, "response_max": 1.0,
        "response_sensitivity": 1.15, "lighting_gain": 1.1, "target_id": "source_lights",
    }
    light_values = {
        "target_id": "source_lights", "object_name": "lights and emissive reflections",
        "animation_prompt": "Pulse and glow in place with the music.", "target_role": "light_source",
        "linked_group": "lighting", "motion_type": "still", "beat_flicker": 1.2,
        "ambient_flicker": 0.14, "motion_amount": 0.0, "max_luminance_change": 0.11,
        "glow_strength": 0.38, "glow_radius_px": 24.0, "saturation_variation": 0.06,
        "hue_variation_degrees": 0.0,
        "advanced_settings_json": json.dumps(light_advanced, separators=(",", ":")),
        "advanced_settings": None,
    }
    light_target.update({"id": 9, "pos": [1170, 470], "title": "LIGHT EFFECT — mask comes from current source", "order": 8})
    light_target["inputs"][0]["link"] = 8
    light_target["inputs"][1]["link"] = 9
    light_target["outputs"][0]["links"] = [10]
    light_target["widgets_values_named"] = light_values
    light_target["widgets_values"] = [True] + [light_values[item["name"]] for item in light_target["inputs"] if item.get("link") is None] + [None]

    stack_two.update({"id": 10, "pos": [1540, 520], "order": 9})
    stack_two["inputs"] = [
        {"localized_name": "target", "name": "target", "type": "LOCAL_VISUALIZER_TARGET", "link": 10},
        {"localized_name": "previous_targets", "name": "previous_targets", "shape": 7, "type": "LOCAL_VISUALIZER_TARGETS", "link": 11},
    ]
    stack_two["outputs"][0]["links"] = [14]

    renderer.update({"id": 11, "pos": [1880, 40], "order": 10, "title": "FULL SONG — generated motion + source lights + title + EQ"})
    renderer["inputs"][0]["link"] = 12
    renderer["inputs"][1]["link"] = 13
    renderer["inputs"][2]["link"] = 14
    settings = dict(renderer.get("widgets_values_named", {}))
    settings.update({
        "maximum_stabilization_percent": 0.0, "band_name": "Artist Name", "song_title": "Song Title",
        "output_prefix": "music_visualizer/final/render", "auto_targets_enabled": False,
        "eq_ultra_band_count": 2048, "generated_clip_cache_enabled": True,
    })
    widget_names = [item["widget"]["name"] for item in renderer["inputs"] if "widget" in item and item["widget"]["name"] != "upload"]
    renderer["widgets_values"] = [settings[name] for name in widget_names] + ["image"]
    renderer["widgets_values_named"] = {**settings, "upload": "image"}

    links = [
        _link(1, 3, 0, 5, 0, "MASK"), _link(2, 4, 0, 5, 1, "BOOLEAN"),
        _link(3, 5, 0, 6, 0, "LOCAL_VISUALIZER_TARGET"),
        _link(4, 1, 0, 7, 0, "IMAGE"), _link(5, 7, 0, 8, 1, "MASK"),
        _link(6, 7, 1, 8, 0, "IMAGE"), _link(7, 1, 0, 8, 2, "IMAGE"),
        _link(8, 8, 0, 9, 0, "MASK"), _link(9, 7, 4, 9, 1, "BOOLEAN"),
        _link(10, 9, 0, 10, 0, "LOCAL_VISUALIZER_TARGET"),
        _link(11, 6, 0, 10, 1, "LOCAL_VISUALIZER_TARGETS"),
        _link(12, 1, 0, 11, 0, "IMAGE"), _link(13, 2, 0, 11, 1, "AUDIO"),
        _link(14, 10, 0, 11, 2, "LOCAL_VISUALIZER_TARGETS"),
    ]
    workflow = {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "tws:music-visualizer:cached-motion:generic")),
        "revision": 0, "last_node_id": 11, "last_link_id": 14,
        "nodes": [image, audio, solid, motion_bool, motion_target, stack_one, light_detector, light_review, light_target, stack_two, renderer],
        "links": links, "groups": [], "config": {},
        "extra": {"ds": {"scale": 0.72, "offset": [20, 20]}}, "version": 0.4,
    }
    _upgrade_cached_motion_ui(workflow)
    _attach_wan_generation(workflow)
    WORKFLOW.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if USER_WORKFLOW.is_file():
        # The live copy is user-owned. Exercise migrations against an in-memory
        # copy for compatibility, but never rewrite its media, settings, layout,
        # timestamp, or formatting as a side effect of repository validation.
        user_workflow = json.loads(USER_WORKFLOW.read_text(encoding="utf-8"))
        _upgrade_cached_motion_ui(user_workflow)
        _attach_wan_generation(user_workflow)
    return WORKFLOW


if __name__ == "__main__":
    print(build())
