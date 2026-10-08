from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "user/default/workflows/music_visualizer_target_builder.json"


def input_slot(name, data_type, link=None, *, widget=False):
    value = {"name": name, "type": data_type, "link": link}
    if widget:
        value["widget"] = {"name": name}
    return value


def output_slot(name, data_type, links=None, slot_index=0):
    return {"name": name, "type": data_type, "links": links, "slot_index": slot_index}


def loader(node_id, kind, title, position, filename, output_links):
    is_audio = kind == "LoadAudio"
    if is_audio:
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
            {"localized_name": "IMAGE", **output_slot("IMAGE", "IMAGE", output_links[0])},
            {"localized_name": "MASK", **output_slot("MASK", "MASK", output_links[1], 1)},
        ],
        "properties": {"Node name for S&R": kind, "cnr_id": "comfy-core", "ver": "0.3.54"},
        "widgets_values": [filename, "image"], "widgets_values_named": {"image": filename, "upload": "image"},
        "title": title, "color": "#243", "bgcolor": "#354",
    }


def detector(node_id, position, image_link, mask_link, preview_link, find, sensitivity=0.65):
    widgets = [find, "box 0 0 1 1", sensitivity, 6, 2.0]
    names = ["find", "search_area", "sensitivity", "max_regions", "padding_percent"]
    kinds = ["STRING", "STRING", "FLOAT", "INT", "FLOAT"]
    return {
        "id": node_id, "type": "VisualizerObjectDetector", "pos": position, "size": [430, 330], "flags": {}, "order": node_id - 1, "mode": 0,
        "inputs": [input_slot("image", "IMAGE", image_link)] + [input_slot(name, kind, widget=True) for name, kind in zip(names, kinds)],
        "outputs": [
            output_slot("detected_mask", "MASK", [mask_link]),
            output_slot("verification_preview", "IMAGE", [preview_link], 1),
            output_slot("suggested_regions", "STRING", None, 2),
            output_slot("detector_report", "STRING", None, 3),
        ],
        "properties": {"Node name for S&R": "VisualizerObjectDetector"},
        "widgets_values": widgets,
        "widgets_values_named": dict(zip(names, widgets)),
        "title": f"Detect: {find}", "color": "#55431d", "bgcolor": "#6d5728",
    }


def review(node_id, position, image_link, detected_mask_link, source_image_link, mask_link, title):
    return {
        "id": node_id, "type": "VisualizerMaskReview", "pos": position, "size": [360, 360], "flags": {}, "order": node_id - 1, "mode": 0,
        "inputs": [
            input_slot("verification_preview", "IMAGE", image_link),
            input_slot("detected_mask", "MASK", detected_mask_link),
            input_slot("source_image", "IMAGE", source_image_link),
            input_slot("image", "STRING", widget=True),
            input_slot("source_fingerprint", "STRING", widget=True),
        ],
        "outputs": [output_slot("reviewed_mask", "MASK", [mask_link]), output_slot("mask_source", "STRING", None, 1)],
        "properties": {"Node name for S&R": "VisualizerMaskReview"},
        "widgets_values": ["", ""], "widgets_values_named": {"image": "", "source_fingerprint": ""}, "title": title,
    }


def target(node_id, position, mask_link, output_link, name, prompt, motion_type, beat_flicker, ambient_flicker, beat_motion, ambient_motion):
    widgets = [name, prompt, False, "add", motion_type, beat_flicker, ambient_flicker, beat_motion, ambient_motion]
    names = [
        "object_name", "animation_prompt", "mask_verified", "approved_mask_mode", "motion_type",
        "on_beat_flicker", "off_beat_flicker", "on_beat_motion", "off_beat_motion",
    ]
    kinds = ["STRING", "STRING", "BOOLEAN", "COMBO", "COMBO", "FLOAT", "FLOAT", "FLOAT", "FLOAT"]
    return {
        "id": node_id, "type": "VisualizerAnimationTarget", "pos": position, "size": [460, 430], "flags": {}, "order": node_id - 1, "mode": 0,
        "inputs": [input_slot("mask", "MASK", mask_link)] + [input_slot(field, kind, widget=True) for field, kind in zip(names, kinds)],
        "outputs": [output_slot("animation_target", "LOCAL_VISUALIZER_TARGET", [output_link]), output_slot("resolved_effects", "STRING", None, 1)],
        "properties": {"Node name for S&R": "VisualizerAnimationTarget"},
        "widgets_values": widgets, "widgets_values_named": dict(zip(names, widgets)),
        "title": f"Verify + animate: {name}", "color": "#31506b", "bgcolor": "#3d6484",
    }


def stack(node_id, position, target_link, output_link, previous_link=None):
    inputs = [input_slot("target", "LOCAL_VISUALIZER_TARGET", target_link)]
    if previous_link is not None:
        inputs.append(input_slot("previous_targets", "LOCAL_VISUALIZER_TARGETS", previous_link))
    return {
        "id": node_id, "type": "VisualizerTargetStack", "pos": position, "size": [310, 110], "flags": {}, "order": node_id - 1, "mode": 0,
        "inputs": inputs, "outputs": [output_slot("targets", "LOCAL_VISUALIZER_TARGETS", [output_link])],
        "properties": {"Node name for S&R": "VisualizerTargetStack"}, "widgets_values": [],
        "title": "Add animation target", "color": "#31506b", "bgcolor": "#3d6484",
    }


def renderer():
    widgets = [16, "1080p", 20261007, True, 10.0, 0.68, True, 32.0, 0.95, 24, 0.55, 18.0, "generic_visualizer/render"]
    names = [
        "fps", "delivery_resolution", "pattern_key", "apply_brand_logo", "brand_logo_width_percent",
        "brand_logo_opacity", "apply_wordmark", "wordmark_width_percent", "wordmark_opacity",
        "overlay_margin_px", "wordmark_halo_opacity", "wordmark_halo_blur_px", "output_prefix",
    ]
    kinds = ["INT", "COMBO", "INT", "BOOLEAN", "FLOAT", "FLOAT", "BOOLEAN", "FLOAT", "FLOAT", "INT", "FLOAT", "FLOAT", "STRING"]
    inputs = [
        input_slot("image", "IMAGE", 4), input_slot("audio", "AUDIO", 5), input_slot("targets", "LOCAL_VISUALIZER_TARGETS", 21),
        input_slot("brand_logo", "IMAGE", 8), input_slot("brand_logo_mask", "MASK", 9),
        input_slot("wordmark", "IMAGE", 6), input_slot("wordmark_mask", "MASK", 7),
    ] + [input_slot(name, kind, widget=True) for name, kind in zip(names, kinds)]
    return {
        "id": 40, "type": "GenericBeatAwareLocalVisualizer", "pos": [1600, -50], "size": [570, 760], "flags": {}, "order": 39, "mode": 0,
        "inputs": inputs, "outputs": [output_slot("output_path", "STRING")],
        "properties": {"Node name for S&R": "GenericBeatAwareLocalVisualizer"},
        "widgets_values": widgets, "widgets_values_named": dict(zip(names, widgets)),
        "title": "Render verified target stack + badging", "color": "#243", "bgcolor": "#354",
    }


def main() -> int:
    nodes = [
        loader(1, "LoadImage", "1. Source artwork (static base)", [-1280, -100], "select_reference_image.png", ([1, 2, 3, 4, 25, 26, 27], None)),
        loader(2, "LoadAudio", "2. Finalized audio", [-1280, 260], "select_audio.mp3", [5]),
        loader(3, "LoadImage", "Track wordmark", [1600, 760], "Managed Decline wordmark.png", ([6], [7])),
        loader(4, "LoadImage", "Studio badge", [1990, 760], "TWS Studio Logo nt - underlay.png", ([8], [9])),
        detector(10, [-820, -620], 1, 10, 11, "candles", 0.72),
        review(11, [-350, -620], 11, 10, 25, 22, "VERIFY / EDIT DETECTION: candles"),
        target(12, [50, -620], 22, 12, "candles", "candles flickering naturally", "sway", 0.55, 0.90, 0.0, 0.55),
        stack(13, [560, -500], 12, 13),
        detector(20, [-820, -170], 2, 14, 15, "clouds", 0.62),
        review(21, [-350, -170], 15, 14, 26, 23, "VERIFY / EDIT DETECTION: clouds"),
        target(22, [50, -170], 23, 16, "clouds", "clouds flowing slowly and flashing heat lightning on strong beats", "billow", 0.90, 0.45, 0.0, 0.65),
        stack(23, [920, -320], 16, 17, 13),
        detector(30, [-820, 280], 3, 18, 19, "monitor", 0.72),
        review(31, [-350, 280], 19, 18, 27, 24, "VERIFY / EDIT DETECTION: monitor"),
        target(32, [50, 280], 24, 20, "monitor", "monitor scan and glow with occasional beat pulses", "still", 0.70, 0.35, 0.0, 0.0),
        stack(33, [1280, -140], 20, 21, 17),
        renderer(),
    ]
    links = [
        [1, 1, 0, 10, 0, "IMAGE"], [2, 1, 0, 20, 0, "IMAGE"], [3, 1, 0, 30, 0, "IMAGE"], [4, 1, 0, 40, 0, "IMAGE"],
        [5, 2, 0, 40, 1, "AUDIO"], [6, 3, 0, 40, 5, "IMAGE"], [7, 3, 1, 40, 6, "MASK"],
        [8, 4, 0, 40, 3, "IMAGE"], [9, 4, 1, 40, 4, "MASK"],
        [10, 10, 0, 11, 1, "MASK"], [11, 10, 1, 11, 0, "IMAGE"], [12, 12, 0, 13, 0, "LOCAL_VISUALIZER_TARGET"],
        [13, 13, 0, 23, 1, "LOCAL_VISUALIZER_TARGETS"],
        [14, 20, 0, 21, 1, "MASK"], [15, 20, 1, 21, 0, "IMAGE"], [16, 22, 0, 23, 0, "LOCAL_VISUALIZER_TARGET"],
        [17, 23, 0, 33, 1, "LOCAL_VISUALIZER_TARGETS"],
        [18, 30, 0, 31, 1, "MASK"], [19, 30, 1, 31, 0, "IMAGE"], [20, 32, 0, 33, 0, "LOCAL_VISUALIZER_TARGET"],
        [21, 33, 0, 40, 2, "LOCAL_VISUALIZER_TARGETS"],
        [22, 11, 0, 12, 0, "MASK"], [23, 21, 0, 22, 0, "MASK"], [24, 31, 0, 32, 0, "MASK"],
        [25, 1, 0, 11, 2, "IMAGE"], [26, 1, 0, 21, 2, "IMAGE"], [27, 1, 0, 31, 2, "IMAGE"],
    ]
    workflow = {
        "id": "e6a21a19-acde-4fcb-b9e0-10ca1a150002", "revision": 0,
        "last_node_id": 40, "last_link_id": 27, "nodes": nodes, "links": links,
        "groups": [
            {"id": 1, "title": "Inputs", "bounding": [-1310, -150, 430, 820], "color": "#3f789e", "font_size": 24, "flags": {}},
            {"id": 2, "title": "Animation target lanes — detection is usable immediately; edit only when needed", "bounding": [-850, -670, 1490, 1370], "color": "#8a6d3b", "font_size": 24, "flags": {}},
            {"id": 3, "title": "Chain target stack in order", "bounding": [530, -550, 1080, 560], "color": "#486d8a", "font_size": 24, "flags": {}},
            {"id": 4, "title": "Streaming renderer — masked flicker + motion", "bounding": [1570, -100, 630, 850], "color": "#487a52", "font_size": 24, "flags": {}},
            {"id": 5, "title": "Optional post-process badging", "bounding": [1570, 710, 820, 420], "color": "#725a8f", "font_size": 24, "flags": {}},
        ],
        "definitions": {"subgraphs": []}, "config": {},
        "extra": {"ds": {"scale": 0.62, "offset": [920, 560]}, "frontendVersion": "1.24.4"},
        "version": 0.4, "state": {"lastNodeId": 40, "lastLinkId": 27, "lastGroupId": 5},
    }
    node_ids = {node["id"] for node in nodes}
    if any(link[1] not in node_ids or link[3] not in node_ids for link in links):
        raise RuntimeError("Workflow contains a link to a missing node.")
    if len({link[0] for link in links}) != len(links):
        raise RuntimeError("Workflow link identifiers are not unique.")
    render_node = next(node for node in nodes if node["type"] == "GenericBeatAwareLocalVisualizer")
    if render_node["inputs"][2]["name"] != "targets" or render_node["widgets_values"][-1] != "generic_visualizer/render":
        raise RuntimeError("Generic renderer inputs or widgets are positionally misaligned.")
    if len([node for node in nodes if node["type"] == "VisualizerObjectDetector"]) != 3:
        raise RuntimeError("Starter workflow must contain three example target lanes.")
    reviewers = [node for node in nodes if node["type"] == "VisualizerMaskReview"]
    if len(reviewers) != 3 or any(node["inputs"][2]["name"] != "source_image" or node["inputs"][2]["link"] is None for node in reviewers):
        raise RuntimeError("Every starter target lane must route its optional Mask Editor correction into configuration.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
