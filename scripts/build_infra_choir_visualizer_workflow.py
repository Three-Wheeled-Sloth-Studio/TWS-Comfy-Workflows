from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "user/default/workflows/music_visualizer_infra_choir_production.json"


def input_slot(name, data_type, link=None, *, widget=False):
    value = {"name": name, "type": data_type, "link": link}
    if widget:
        value["widget"] = {"name": name}
    return value


def output_slot(name, data_type, links=None, slot_index=0):
    return {"name": name, "type": data_type, "links": links, "slot_index": slot_index}


def loader(node_id, kind, title, position, filename, output_links):
    if kind == "LoadAudio":
        return {
            "id": node_id, "type": kind, "pos": position, "size": [360, 140], "flags": {}, "order": node_id - 1, "mode": 0,
            "inputs": [
                {"localized_name": "audio", "name": "audio", "type": "COMBO", "widget": {"name": "audio"}, "link": None},
                {"localized_name": "audioUI", "name": "audioUI", "type": "AUDIO_UI", "widget": {"name": "audioUI"}, "link": None},
                {"localized_name": "choose file to upload", "name": "upload", "type": "AUDIOUPLOAD", "widget": {"name": "upload"}, "link": None},
            ],
            "outputs": [{"localized_name": "AUDIO", **output_slot("AUDIO", "AUDIO", output_links)}],
            "properties": {"Node name for S&R": kind, "cnr_id": "comfy-core", "ver": "0.3.54"},
            "widgets_values": [filename, None], "widgets_values_named": {"audio": filename, "upload": None},
            "title": title, "color": "#243", "bgcolor": "#354",
        }
    return {
        "id": node_id, "type": kind, "pos": position, "size": [360, 314], "flags": {}, "order": node_id - 1, "mode": 0,
        "inputs": [
            {"localized_name": "image", "name": "image", "type": "COMBO", "widget": {"name": "image"}, "link": None},
            {"localized_name": "choose file to upload", "name": "upload", "type": "IMAGEUPLOAD", "widget": {"name": "upload"}, "link": None},
        ],
        "outputs": [
            {"localized_name": "IMAGE", **output_slot("IMAGE", "IMAGE", output_links)},
            {"localized_name": "MASK", **output_slot("MASK", "MASK", None, 1)},
        ],
        "properties": {"Node name for S&R": kind, "cnr_id": "comfy-core", "ver": "0.3.54"},
        "widgets_values": [filename, "image"], "widgets_values_named": {"image": filename, "upload": "image"},
        "title": title, "color": "#243", "bgcolor": "#354",
    }


def detector(node_id, position, source_link, mask_link, preview_link, find, area, sensitivity):
    names = ["find", "search_area", "sensitivity", "max_regions", "padding_percent", "detection_provider"]
    kinds = ["STRING", "STRING", "FLOAT", "INT", "FLOAT", "COMBO"]
    widgets = [find, area, sensitivity, 6, 2.0, "semantic_or_heuristic"]
    return {
        "id": node_id, "type": "VisualizerSemanticObjectDetector", "pos": position, "size": [430, 360], "flags": {}, "order": node_id - 1, "mode": 0,
        "inputs": [input_slot("image", "IMAGE", source_link)] + [input_slot(name, kind, widget=True) for name, kind in zip(names, kinds)],
        "outputs": [
            output_slot("detected_mask", "MASK", [mask_link]),
            output_slot("verification_preview", "IMAGE", [preview_link], 1),
            output_slot("suggested_regions", "STRING", None, 2),
            output_slot("detector_report", "STRING", None, 3),
        ],
        "properties": {"Node name for S&R": "VisualizerSemanticObjectDetector"},
        "widgets_values": widgets, "widgets_values_named": dict(zip(names, widgets)),
        "title": f"Detect candidate: {find}", "color": "#55431d", "bgcolor": "#6d5728",
    }


def review(node_id, position, preview_link, detected_mask_link, source_link, output_link, title):
    return {
        "id": node_id, "type": "VisualizerMaskReview", "pos": position, "size": [360, 360], "flags": {}, "order": node_id - 1, "mode": 0,
        "inputs": [
            input_slot("verification_preview", "IMAGE", preview_link), input_slot("detected_mask", "MASK", detected_mask_link),
            input_slot("source_image", "IMAGE", source_link), input_slot("image", "STRING", widget=True),
            input_slot("source_fingerprint", "STRING", widget=True),
        ],
        "outputs": [output_slot("reviewed_mask", "MASK", [output_link]), output_slot("mask_source", "STRING", None, 1)],
        "properties": {"Node name for S&R": "VisualizerMaskReview"},
        "widgets_values": ["", ""], "widgets_values_named": {"image": "", "source_fingerprint": ""},
        "title": title,
    }


TARGET_FIELDS = [
    ("enabled", "BOOLEAN"), ("target_id", "STRING"), ("object_name", "STRING"),
    ("animation_prompt", "STRING"), ("mask_verified", "BOOLEAN"), ("target_role", "COMBO"),
    ("envelope_group", "STRING"), ("audio_driver", "COMBO"), ("motion_source", "COMBO"),
    ("motion_type", "COMBO"), ("on_beat_flicker", "FLOAT"), ("off_beat_flicker", "FLOAT"),
    ("on_beat_motion", "FLOAT"), ("off_beat_motion", "FLOAT"), ("generated_motion_strength", "FLOAT"),
    ("max_luminance_change", "FLOAT"), ("glow_strength", "FLOAT"), ("glow_radius_px", "FLOAT"),
    ("saturation_variation", "FLOAT"), ("hue_variation_degrees", "FLOAT"), ("approved_mask_mode", "COMBO"),
]


def target(node_id, position, mask_link, output_link, spec):
    values = [
        spec["enabled"], spec["id"], spec["find"], spec["prompt"], False, spec["role"], spec["group"],
        spec["driver"], "procedural", spec["motion"], spec["beat_flicker"], spec["ambient_flicker"],
        spec["beat_motion"], spec["ambient_motion"], 0.85, spec["max_luminance"], spec["glow"],
        spec["glow_radius"], spec["saturation"], spec["hue"], "add",
    ]
    inputs = [input_slot(name, kind, widget=True) for name, kind in TARGET_FIELDS]
    inputs.append(input_slot("mask", "MASK", mask_link))
    return {
        "id": node_id, "type": "InfraChoirAnimationTarget", "pos": position, "size": [500, 620], "flags": {}, "order": node_id - 1, "mode": 0,
        "inputs": inputs,
        "outputs": [
            output_slot("animation_target", "LOCAL_VISUALIZER_TARGET", [output_link]),
            output_slot("diagnostic", "STRING", None, 1), output_slot("configuration_json", "STRING", None, 2),
        ],
        "properties": {"Node name for S&R": "InfraChoirAnimationTarget"},
        "widgets_values": values, "widgets_values_named": dict(zip((name for name, _ in TARGET_FIELDS), values)),
        "title": f"Enable + verify: {spec['id']}", "color": "#31506b", "bgcolor": "#3d6484",
    }


def stack(node_id, position, target_link, output_link, previous_link=None):
    inputs = [input_slot("target", "LOCAL_VISUALIZER_TARGET", target_link)]
    if previous_link is not None:
        inputs.append(input_slot("previous_targets", "LOCAL_VISUALIZER_TARGETS", previous_link))
    return {
        "id": node_id, "type": "VisualizerTargetStack", "pos": position, "size": [300, 110], "flags": {}, "order": node_id - 1, "mode": 0,
        "inputs": inputs, "outputs": [output_slot("targets", "LOCAL_VISUALIZER_TARGETS", [output_link])],
        "properties": {"Node name for S&R": "VisualizerTargetStack"}, "widgets_values": [], "title": "Append target",
    }


def renderer(targets_link):
    fields = [
        ("fps", "INT"), ("delivery_resolution", "COMBO"), ("pattern_key", "INT"),
        ("maximum_stabilization_percent", "FLOAT"), ("apply_brand_logo", "BOOLEAN"),
        ("brand_logo_width_percent", "FLOAT"), ("brand_logo_opacity", "FLOAT"),
        ("apply_wordmark", "BOOLEAN"), ("wordmark_width_percent", "FLOAT"),
        ("wordmark_opacity", "FLOAT"), ("overlay_margin_px", "INT"),
        ("title_card_enabled", "BOOLEAN"), ("band_name", "STRING"), ("song_title", "STRING"),
        ("title_card_image", "COMBO"), ("title_card_placement", "COMBO"),
        ("title_card_start_seconds", "FLOAT"), ("title_card_duration_seconds", "FLOAT"),
        ("title_card_fade_seconds", "FLOAT"), ("title_sparkle_enabled", "BOOLEAN"),
        ("title_sparkle_strength", "FLOAT"), ("title_sparkle_audio_response", "FLOAT"),
        ("eq_enabled", "BOOLEAN"), ("eq_mode", "COMBO"), ("eq_height_percent", "FLOAT"),
        ("eq_opacity", "FLOAT"), ("eq_color", "STRING"), ("eq_smoothing", "FLOAT"),
        ("organic_motion_expansion_percent", "FLOAT"), ("title_card_source_visibility", "FLOAT"),
        ("brand_logo_image", "COMBO"),
        ("output_prefix", "STRING"),
    ]
    values = [
        16, "1080p", 20261009, 4.0, False, 10.0, 0.68, False, 32.0, 0.95, 24,
        True, "Infra Choir", "Bella Ciao", "(generate from text)", "center", 0.0, 4.5, 0.55,
        True, 0.55, 0.30, True, "spectrum_bars", 11.0, 0.46, "#8E1325", 0.72,
        2.5, 0.20, "(none)",
        "infra_choir/production_bella_ciao",
    ]
    return {
        "id": 90, "type": "InfraChoirVisualizer", "pos": [1730, -100], "size": [620, 1060], "flags": {}, "order": 89, "mode": 0,
        "inputs": [input_slot("image", "IMAGE", 1), input_slot("audio", "AUDIO", 2), input_slot("targets", "LOCAL_VISUALIZER_TARGETS", targets_link)]
        + [input_slot(name, kind, widget=True) for name, kind in fields],
        "outputs": [output_slot("output_path", "STRING"), output_slot("qa_report", "STRING", None, 1)],
        "properties": {"Node name for S&R": "InfraChoirVisualizer"},
        "widgets_values": values, "widgets_values_named": dict(zip((name for name, _ in fields), values)),
        "title": "PRODUCTION: title card + EQ + fixed-frame hybrid", "color": "#243", "bgcolor": "#354",
    }


SPECS = [
    {"id": "red_hair", "find": "red hair", "area": "box .31 .08 .54 .43", "sensitivity": .58, "prompt": "red hair rustling gently in a light breeze", "role": "organic", "group": "wind", "driver": "slow", "motion": "sway", "enabled": True, "beat_flicker": .0, "ambient_flicker": .08, "beat_motion": .0, "ambient_motion": .40, "max_luminance": .03, "glow": .0, "glow_radius": 0., "saturation": .02, "hue": 0.},
    {"id": "red_fabric", "find": "red scarf and hanging red fabric", "area": "box .04 .02 .58 .76", "sensitivity": .60, "prompt": "scarf and hanging fabric moving softly in the breeze", "role": "organic", "group": "wind", "driver": "slow", "motion": "sway", "enabled": True, "beat_flicker": .0, "ambient_flicker": .08, "beat_motion": .0, "ambient_motion": .45, "max_luminance": .03, "glow": .0, "glow_radius": 0., "saturation": .02, "hue": 0.},
    {"id": "industrial_smoke", "find": "smoke", "area": "box .40 .18 .72 .62", "sensitivity": .65, "prompt": "industrial smoke billowing organically upward", "role": "organic", "group": "atmosphere", "driver": "slow", "motion": "billow", "enabled": True, "beat_flicker": .0, "ambient_flicker": .14, "beat_motion": .0, "ambient_motion": .62, "max_luminance": .04, "glow": .0, "glow_radius": 0., "saturation": -.02, "hue": 0.},
    {"id": "clouds", "find": "clouds in the sky", "area": "box .42 .00 1.00 .36", "sensitivity": .60, "prompt": "clouds drifting lazily with restrained billowing", "role": "organic", "group": "atmosphere", "driver": "slow", "motion": "billow", "enabled": True, "beat_flicker": .0, "ambient_flicker": .12, "beat_motion": .0, "ambient_motion": .35, "max_luminance": .04, "glow": .0, "glow_radius": 0., "saturation": -.02, "hue": 0.},
    {"id": "sun_source", "find": "sun disk", "area": "box .72 .08 .96 .42", "sensitivity": .58, "prompt": "setting sun emitting a subtle bounded musical pulse", "role": "light_source", "group": "sunlight", "driver": "beat", "motion": "still", "enabled": True, "beat_flicker": .52, "ambient_flicker": .12, "beat_motion": .0, "ambient_motion": .0, "max_luminance": .12, "glow": .30, "glow_radius": 28., "saturation": .08, "hue": -3.},
    {"id": "sun_illumination", "find": "sunlit atmospheric haze", "area": "box .53 .08 1.00 .62", "sensitivity": .56, "prompt": "warm atmospheric illumination linked to the setting sun", "role": "illumination", "group": "sunlight", "driver": "beat", "motion": "still", "enabled": True, "beat_flicker": .34, "ambient_flicker": .10, "beat_motion": .0, "ambient_motion": .0, "max_luminance": .08, "glow": .0, "glow_radius": 0., "saturation": .05, "hue": -2.},
    {"id": "river_reflection", "find": "sunlight reflection on river", "area": "box .55 .33 .96 .70", "sensitivity": .40, "prompt": "river reflections shimmering in response to sunlight", "role": "reflection", "group": "sunlight", "driver": "beat", "motion": "still", "enabled": True, "beat_flicker": .42, "ambient_flicker": .18, "beat_motion": .0, "ambient_motion": .0, "max_luminance": .10, "glow": .0, "glow_radius": 0., "saturation": .05, "hue": -2.},
]


def main() -> int:
    nodes = [
        loader(
            1, "LoadImage", "1. Source artwork — immutable frame base", [-1480, -80], "Bella Ciao.png",
            [1] + [link_id for i in range(len(SPECS)) for link_id in (3 + i * 7, 4 + i * 7)],
        ),
        loader(2, "LoadAudio", "2. Final song audio", [-1480, 280], "Bella Ciao.mp3", [2]),
    ]
    links = [[1, 1, 0, 90, 0, "IMAGE"], [2, 2, 0, 90, 1, "AUDIO"]]
    previous_stack_link = None
    next_link = 3
    for index, spec in enumerate(SPECS):
        detector_id = 10 + index * 10
        review_id = detector_id + 1
        target_id = detector_id + 2
        stack_id = detector_id + 3
        y = -860 + index * 520
        source_detector_link, source_review_link, detector_mask_link, detector_preview_link, review_mask_link, target_link, stack_link = range(next_link, next_link + 7)
        next_link += 7
        nodes.extend([
            detector(detector_id, [-1030, y], source_detector_link, detector_mask_link, detector_preview_link, spec["find"], spec["area"], spec["sensitivity"]),
            review(review_id, [-550, y], detector_preview_link, detector_mask_link, source_review_link, review_mask_link, f"VERIFY / EDIT: {spec['id']}"),
            target(target_id, [-140, y], review_mask_link, target_link, spec),
            stack(stack_id, [430 + (index % 2) * 330, y + 180], target_link, stack_link, previous_stack_link),
        ])
        links.extend([
            [source_detector_link, 1, 0, detector_id, 0, "IMAGE"],
            [source_review_link, 1, 0, review_id, 2, "IMAGE"],
            [detector_mask_link, detector_id, 0, review_id, 1, "MASK"],
            [detector_preview_link, detector_id, 1, review_id, 0, "IMAGE"],
            [review_mask_link, review_id, 0, target_id, len(TARGET_FIELDS), "MASK"],
            [target_link, target_id, 0, stack_id, 0, "LOCAL_VISUALIZER_TARGET"],
        ])
        if previous_stack_link is not None:
            links.append([previous_stack_link, stack_id - 10, 0, stack_id, 1, "LOCAL_VISUALIZER_TARGETS"])
        previous_stack_link = stack_link
    nodes.append(renderer(previous_stack_link))
    links.append([previous_stack_link, 10 + (len(SPECS) - 1) * 10 + 3, 0, 90, 2, "LOCAL_VISUALIZER_TARGETS"])

    workflow = {
        "id": "a8f2a31b-acde-4fcb-b9e0-10ca1a150004", "revision": 0,
        "last_node_id": 90, "last_link_id": next_link - 1, "nodes": nodes, "links": links,
        "groups": [
            {"id": 1, "title": "Inputs — changing audio does not invalidate masks or generated motion", "bounding": [-1510, -130, 430, 650], "color": "#3f789e", "font_size": 24, "flags": {}},
            {"id": 2, "title": "Seven independent detect → review → configure lanes", "bounding": [-1060, -910, 940, 3860], "color": "#8a6d3b", "font_size": 24, "flags": {}},
            {"id": 3, "title": "Target stack — disabled or incomplete lanes are skipped", "bounding": [390, -730, 730, 3740], "color": "#486d8a", "font_size": 24, "flags": {}},
            {"id": 4, "title": "Production renderer — generated/selected title card + restrained EQ + optional branding", "bounding": [1690, -150, 700, 1160], "color": "#487a52", "font_size": 24, "flags": {}},
        ],
        "definitions": {"subgraphs": []}, "config": {},
        "extra": {"ds": {"scale": 0.48, "offset": [1080, 650]}, "frontendVersion": "1.24.4"},
        "version": 0.4, "state": {"lastNodeId": 90, "lastLinkId": next_link - 1, "lastGroupId": 4},
    }
    node_ids = {node["id"] for node in nodes}
    if any(link[1] not in node_ids or link[3] not in node_ids for link in links):
        raise RuntimeError("Workflow contains a link to a missing node.")
    if len({link[0] for link in links}) != len(links):
        raise RuntimeError("Workflow link identifiers are not unique.")
    node_by_id = {node["id"]: node for node in nodes}
    for link_id, source_id, source_slot, destination_id, destination_slot, _ in links:
        source_links = node_by_id[source_id]["outputs"][source_slot].get("links") or []
        if link_id not in source_links:
            raise RuntimeError(f"Link {link_id} is missing from source node {source_id} output {source_slot}.")
        if node_by_id[destination_id]["inputs"][destination_slot].get("link") != link_id:
            raise RuntimeError(f"Link {link_id} is missing from destination node {destination_id} input {destination_slot}.")
    if len([node for node in nodes if node["type"] == "InfraChoirAnimationTarget"]) != 7:
        raise RuntimeError("Infra Choir starter workflow must contain seven independent targets.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
