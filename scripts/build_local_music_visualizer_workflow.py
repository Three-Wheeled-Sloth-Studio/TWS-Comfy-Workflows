from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "user/default/workflows/music_visualizer_local_composite.json"


def input_slot(name, data_type, link=None, *, widget=False):
    value = {"name": name, "type": data_type, "link": link}
    if widget:
        value["widget"] = {"name": name}
    return value


def output_slot(name, data_type, links=None, slot_index=0):
    return {"name": name, "type": data_type, "links": links, "slot_index": slot_index}


def load_image():
    return {
        "id": 1, "type": "LoadImage", "pos": [-1050, -140], "size": [360, 314],
        "flags": {}, "order": 0, "mode": 0,
        "inputs": [
            {"localized_name": "image", "name": "image", "type": "COMBO", "widget": {"name": "image"}, "link": None},
            {"localized_name": "choose file to upload", "name": "upload", "type": "IMAGEUPLOAD", "widget": {"name": "upload"}, "link": None},
        ],
        "outputs": [
            {"localized_name": "IMAGE", **output_slot("IMAGE", "IMAGE", [1, 2, 3, 4, 5, 6, 7, 19])},
            {"localized_name": "MASK", **output_slot("MASK", "MASK", None, 1)},
        ],
        "properties": {"Node name for S&R": "LoadImage", "cnr_id": "comfy-core", "ver": "0.3.54"},
        "widgets_values": ["select_reference_image.png", "image"],
        "widgets_values_named": {"image": "select_reference_image.png", "upload": "image"},
        "title": "1. Source artwork (static base)", "color": "#243", "bgcolor": "#354",
    }


def load_audio():
    return {
        "id": 2, "type": "LoadAudio", "pos": [-1050, 230], "size": [360, 140],
        "flags": {}, "order": 1, "mode": 0,
        "inputs": [
            {"localized_name": "audio", "name": "audio", "type": "COMBO", "widget": {"name": "audio"}, "link": None},
            {"localized_name": "audioUI", "name": "audioUI", "type": "AUDIO_UI", "widget": {"name": "audioUI"}, "link": None},
            {"localized_name": "choose file to upload", "name": "upload", "type": "AUDIOUPLOAD", "widget": {"name": "upload"}, "link": None},
        ],
        "outputs": [{"localized_name": "AUDIO", **output_slot("AUDIO", "AUDIO", [8])}],
        "properties": {"Node name for S&R": "LoadAudio", "cnr_id": "comfy-core", "ver": "0.3.54"},
        "widgets_values": ["select_audio.mp3", None],
        "widgets_values_named": {"audio": "select_audio.mp3", "upload": None},
        "title": "2. Finalized audio", "color": "#243", "bgcolor": "#354",
    }


def overlay_image(node_id, title, position, filename, image_link, mask_link):
    return {
        "id": node_id, "type": "LoadImage", "pos": position, "size": [360, 314],
        "flags": {}, "order": node_id - 1, "mode": 0,
        "inputs": [
            {"localized_name": "image", "name": "image", "type": "COMBO", "widget": {"name": "image"}, "link": None},
            {"localized_name": "choose file to upload", "name": "upload", "type": "IMAGEUPLOAD", "widget": {"name": "upload"}, "link": None},
        ],
        "outputs": [
            {"localized_name": "IMAGE", **output_slot("IMAGE", "IMAGE", [image_link])},
            {"localized_name": "MASK", **output_slot("MASK", "MASK", [mask_link], 1)},
        ],
        "properties": {"Node name for S&R": "LoadImage", "cnr_id": "comfy-core", "ver": "0.3.54"},
        "widgets_values": [filename, "image"],
        "widgets_values_named": {"image": filename, "upload": "image"},
        "title": title, "color": "#243", "bgcolor": "#354",
    }


def candidate_tool():
    return {
        "id": 12, "type": "VisualizerCandidateRegions", "pos": [-1050, 470], "size": [420, 250],
        "flags": {}, "order": 11, "mode": 0,
        "inputs": [
            input_slot("image", "IMAGE", 19),
            input_slot("candidate_type", "COMBO", widget=True),
            input_slot("sensitivity", "FLOAT", widget=True),
            input_slot("max_regions", "INT", widget=True),
            input_slot("padding_percent", "FLOAT", widget=True),
        ],
        "outputs": [
            output_slot("suggested_regions", "STRING"),
            output_slot("candidate_mask", "MASK", None, 1),
            output_slot("candidate_preview", "IMAGE", None, 2),
        ],
        "properties": {"Node name for S&R": "VisualizerCandidateRegions"},
        "widgets_values": ["bright highlights", 0.65, 6, 2.0],
        "widgets_values_named": {
            "candidate_type": "bright highlights", "sensitivity": 0.65,
            "max_regions": 6, "padding_percent": 2.0,
        },
        "title": "Optional: suggest candidate regions for a new image",
    }


def mask_node(node_id, title, position, image_link, output_link, regions, color_filter, threshold, feather):
    return {
        "id": node_id, "type": "VisualizerRegionMask", "pos": position, "size": [430, 300],
        "flags": {}, "order": node_id - 1, "mode": 0,
        "inputs": [
            input_slot("image", "IMAGE", image_link),
            input_slot("regions", "STRING", widget=True),
            input_slot("color_filter", "COMBO", widget=True),
            input_slot("threshold", "FLOAT", widget=True),
            input_slot("feather_px", "FLOAT", widget=True),
        ],
        "outputs": [output_slot("mask", "MASK", [output_link]), output_slot("mask_preview", "IMAGE", None, 1)],
        "properties": {"Node name for S&R": "VisualizerRegionMask"},
        "widgets_values": [regions, color_filter, threshold, feather],
        "widgets_values_named": {"regions": regions, "color_filter": color_filter, "threshold": threshold, "feather_px": feather},
        "title": title,
    }


def renderer():
    widgets = [
        16, "1080p", 20261007, 1.15, 1.15, 1.0, 1.0, 0.9, 0.95,
        True, 10.0, 0.68, True, 32.0, 0.95, 24, 0.55, 18.0,
        "local_visualizer/managed_decline",
    ]
    names = [
        "fps", "delivery_resolution", "pattern_key", "cloud_strength", "candle_strength",
        "red_light_strength", "monitor_strength", "rain_strength", "reflection_strength",
        "apply_brand_logo", "brand_logo_width_percent", "brand_logo_opacity",
        "apply_wordmark", "wordmark_width_percent", "wordmark_opacity", "overlay_margin_px",
        "wordmark_halo_opacity", "wordmark_halo_blur_px", "output_prefix",
    ]
    inputs = [
        input_slot("image", "IMAGE", 7), input_slot("audio", "AUDIO", 8),
        input_slot("brand_logo", "IMAGE", 15), input_slot("brand_logo_mask", "MASK", 16),
        input_slot("wordmark", "IMAGE", 17), input_slot("wordmark_mask", "MASK", 18),
        input_slot("cloud_mask", "MASK", 9), input_slot("candle_mask", "MASK", 10),
        input_slot("red_light_mask", "MASK", 11), input_slot("monitor_mask", "MASK", 12),
        input_slot("rain_mask", "MASK", 13), input_slot("reflection_mask", "MASK", 14),
    ]
    types = [
        "INT", "COMBO", "INT", "FLOAT", "FLOAT", "FLOAT", "FLOAT", "FLOAT", "FLOAT",
        "BOOLEAN", "FLOAT", "FLOAT", "BOOLEAN", "FLOAT", "FLOAT", "INT", "FLOAT", "FLOAT", "STRING",
    ]
    inputs.extend(input_slot(name, kind, widget=True) for name, kind in zip(names, types))
    return {
        "id": 9, "type": "BeatAwareLocalVisualizerV3", "pos": [480, -260], "size": [560, 900],
        "flags": {}, "order": 8, "mode": 0, "inputs": inputs,
        "outputs": [output_slot("output_path", "STRING")],
        "properties": {"Node name for S&R": "BeatAwareLocalVisualizerV3"},
        "widgets_values": widgets,
        "widgets_values_named": {
            "fps": 16,
            "delivery_resolution": "1080p",
            "pattern_key": 20261007,
            "cloud_strength": 1.15,
            "candle_strength": 1.15,
            "red_light_strength": 1.0,
            "monitor_strength": 1.0,
            "rain_strength": 0.9,
            "reflection_strength": 0.95,
            "apply_brand_logo": True,
            "brand_logo_width_percent": 10.0,
            "brand_logo_opacity": 0.68,
            "apply_wordmark": True,
            "wordmark_width_percent": 32.0,
            "wordmark_opacity": 0.95,
            "overlay_margin_px": 24,
            "wordmark_halo_opacity": 0.55,
            "wordmark_halo_blur_px": 18.0,
            "output_prefix": "local_visualizer/managed_decline",
        },
        "title": "4. Render full-song local composite + badging", "color": "#243", "bgcolor": "#354",
    }


def main() -> int:
    cloud_regions = """# Upper window sky only; architecture and furniture stay static.
box 0.005 0.005 0.195 0.30
box 0.225 0.005 0.405 0.30
box 0.425 0.005 0.635 0.28"""
    candle_regions = """# Flame cores; warm-pixel filter tightens each ellipse.
ellipse 0.027 0.485 0.052 0.595
ellipse 0.073 0.475 0.102 0.595
ellipse 0.104 0.575 0.139 0.690
ellipse 0.165 0.485 0.194 0.595
ellipse 0.005 0.590 0.033 0.700"""
    red_regions = """# Warning lamps and skyline indicators; red filter rejects neutral objects.
box 0.320 0.180 0.700 0.505
box 0.020 0.250 0.205 0.520"""
    monitor_regions = """# Left monitor face.
polygon 0.218 0.305 0.296 0.330 0.304 0.497 0.220 0.470"""
    rain_regions = """# Glass only; separate panes avoid the wall and foreground.
box 0.005 0.005 0.195 0.500
box 0.225 0.005 0.635 0.485"""
    reflection_regions = """# Existing red reflections on table and floor.
polygon 0.170 0.490 0.560 0.485 0.515 0.825 0.205 0.835
polygon 0.570 0.690 0.830 0.690 0.790 0.990 0.610 0.980"""
    nodes = [
        load_image(), load_audio(),
        mask_node(3, "3a. Clouds — slow energy drift", [-600, -650], 1, 9, cloud_regions, "neutral_bright", 0.12, 14.0),
        mask_node(4, "3b. Candles — high band + onset flicker", [-140, -650], 2, 10, candle_regions, "warm", 0.30, 5.0),
        mask_node(5, "3c. Red lights — low beat pulse", [-600, -310], 3, 11, red_regions, "red", 0.18, 4.0),
        mask_node(6, "3d. Monitor — onset + energy glow", [-140, -310], 4, 12, monitor_regions, "none", 0.0, 4.0),
        mask_node(7, "3e. Rain — slow continuous motion", [-600, 30], 5, 13, rain_regions, "none", 0.0, 2.0),
        mask_node(8, "3f. Reflections — beat + slow shimmer", [-140, 30], 6, 14, reflection_regions, "red", 0.12, 10.0),
        renderer(),
        overlay_image(10, "Track title / wordmark — upper left", [1090, -260], "Managed Decline wordmark.png", 17, 18),
        overlay_image(11, "Studio badge — lower right", [1090, 100], "TWS Studio Logo nt - underlay.png", 15, 16),
        candidate_tool(),
    ]
    links = [
        [1, 1, 0, 3, 0, "IMAGE"], [2, 1, 0, 4, 0, "IMAGE"],
        [3, 1, 0, 5, 0, "IMAGE"], [4, 1, 0, 6, 0, "IMAGE"],
        [5, 1, 0, 7, 0, "IMAGE"], [6, 1, 0, 8, 0, "IMAGE"],
        [7, 1, 0, 9, 0, "IMAGE"], [8, 2, 0, 9, 1, "AUDIO"],
        [9, 3, 0, 9, 6, "MASK"], [10, 4, 0, 9, 7, "MASK"],
        [11, 5, 0, 9, 8, "MASK"], [12, 6, 0, 9, 9, "MASK"],
        [13, 7, 0, 9, 10, "MASK"], [14, 8, 0, 9, 11, "MASK"],
        [15, 11, 0, 9, 2, "IMAGE"], [16, 11, 1, 9, 3, "MASK"],
        [17, 10, 0, 9, 4, "IMAGE"], [18, 10, 1, 9, 5, "MASK"],
        [19, 1, 0, 12, 0, "IMAGE"],
    ]
    workflow = {
        "id": "6ef80884-acde-4a30-a808-10ca1a150001", "revision": 0,
        "last_node_id": 12, "last_link_id": 19, "nodes": nodes, "links": links,
        "groups": [
            {"id": 1, "title": "Inputs and candidate-region helper", "bounding": [-1080, -180, 470, 950], "color": "#3f789e", "font_size": 24, "flags": {}},
            {"id": 2, "title": "Independent editable region masks", "bounding": [-630, -700, 950, 1080], "color": "#8a6d3b", "font_size": 24, "flags": {}},
            {"id": 3, "title": "Streaming procedural render — no generative model", "bounding": [440, -310, 620, 1030], "color": "#487a52", "font_size": 24, "flags": {}},
            {"id": 4, "title": "Post-process track title and studio badge", "bounding": [1060, -310, 420, 800], "color": "#725a8f", "font_size": 24, "flags": {}},
        ],
        "definitions": {"subgraphs": []}, "config": {},
        "extra": {"ds": {"scale": 0.72, "offset": [990, 620]}, "frontendVersion": "1.24.4"},
        "version": 0.4, "state": {"lastNodeId": 12, "lastLinkId": 19, "lastGroupId": 4},
    }
    node_ids = {node["id"] for node in nodes}
    if any(link[1] not in node_ids or link[3] not in node_ids for link in links):
        raise RuntimeError("Workflow contains a link to a missing node.")
    if len({link[0] for link in links}) != len(links):
        raise RuntimeError("Workflow link identifiers are not unique.")
    if [node["type"] for node in nodes].count("BeatAwareLocalVisualizerV3") != 1:
        raise RuntimeError("Workflow must contain exactly one renderer.")
    render_node = next(node for node in nodes if node["type"] == "BeatAwareLocalVisualizerV3")
    if render_node["inputs"][14]["name"] != "pattern_key":
        raise RuntimeError("Renderer pattern key input is positionally misaligned.")
    if render_node["widgets_values"][-2:] != [18.0, "local_visualizer/managed_decline"]:
        raise RuntimeError("Renderer widgets are positionally misaligned.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
