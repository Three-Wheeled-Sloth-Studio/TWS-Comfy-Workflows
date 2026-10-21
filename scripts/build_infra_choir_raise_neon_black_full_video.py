from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD = ROOT / "user/default/workflows/music_visualizer_infra_choir_dual_track_scaffold.json"
WORKFLOW = ROOT / "user/default/workflows/video_raise_the_neon_black_full_visualizer_v2.json"
API_PROMPT = ROOT / "refs/evaluations/2026-10-20-raise-neon-black-full-api-prompt.json"
INPUT_ROOT = Path(r"D:\comfyDesktop\input")
IMAGE_NAME = "infra_choir/raise_the_neon_black/Banner.png"
AUDIO_NAME = "infra_choir/raise_the_neon_black/Raise the Neon Black_48k.flac"
LIGHT_MASK_NAME = "infra_choir/raise_the_neon_black/lighting_mask_v1.png"
MOTION_CLIP = "infra_choir/motion_assets/raise_the_neon_black_atmosphere_boost_preview_v3.mp4"
OUTPUT_PREFIX = "infra_choir/final/raise_the_neon_black_full_v2"


def _lighting_mask() -> Path:
    source = np.asarray(Image.open(INPUT_ROOT / IMAGE_NAME).convert("RGB"), dtype=np.uint8)
    hsv = cv2.cvtColor(source, cv2.COLOR_RGB2HSV).astype(np.float32)
    value = hsv[..., 2] / 255.0
    saturation = hsv[..., 1] / 255.0
    local = value - cv2.GaussianBlur(value, (0, 0), 11.0)
    emissive = ((value > 0.82) & (local > 0.16)) | ((value > 0.70) & (saturation > 0.80) & (local > 0.09))
    yy, xx = np.mgrid[0:source.shape[0], 0:source.shape[1]]
    allowed = (
        (xx > source.shape[1] * 0.47)
        | (yy < source.shape[0] * 0.22)
        | ((xx < source.shape[1] * 0.20) & (yy < source.shape[0] * 0.50))
    )
    emissive &= allowed
    mask = emissive.astype(np.uint8) * 255
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    mask = cv2.GaussianBlur(mask, (0, 0), 3.5)
    path = INPUT_ROOT / LIGHT_MASK_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mask, "L").save(path)
    return path


def _link(link_id: int, origin: int, origin_slot: int, target: int, target_slot: int, kind: str) -> list:
    return [link_id, origin, origin_slot, target, target_slot, kind]


def build() -> tuple[Path, Path, Path]:
    light_mask = _lighting_mask()
    source = json.loads(SCAFFOLD.read_text(encoding="utf-8"))
    source_nodes = {int(node["id"]): node for node in source["nodes"]}

    image = copy.deepcopy(source_nodes[1])
    audio = copy.deepcopy(source_nodes[2])
    motion_target = copy.deepcopy(source_nodes[12])
    stack_one = copy.deepcopy(source_nodes[13])
    light_target = copy.deepcopy(source_nodes[22])
    stack_two = copy.deepcopy(source_nodes[23])
    renderer = copy.deepcopy(source_nodes[90])

    image.update({"id": 1, "pos": [40, 80], "title": "Raise the Neon Black — source artwork", "order": 0})
    image["widgets_values"] = [IMAGE_NAME, "image"]
    image["widgets_values_named"] = {"image": IMAGE_NAME, "upload": "image"}
    audio.update({"id": 2, "pos": [40, 430], "title": "Raise the Neon Black — 48 kHz working audio", "order": 1})
    audio["widgets_values"] = [AUDIO_NAME, None]
    audio["widgets_values_named"] = {"audio": AUDIO_NAME, "upload": None}

    solid = {
        "id": 3, "type": "SolidMask", "pos": [430, 80], "size": [270, 106], "flags": {}, "order": 2, "mode": 0,
        "inputs": [], "outputs": [{"name": "MASK", "type": "MASK", "links": [1]}],
        "properties": {"cnr_id": "comfy-core", "ver": "0.9.2", "Node name for S&R": "SolidMask"},
        "widgets_values": [1.0, 1672, 941], "widgets_values_named": {"value": 1.0, "width": 1672, "height": 941},
        "title": "Full-frame mask for approved Wan motion",
    }
    motion_bool = {
        "id": 4, "type": "PrimitiveBoolean", "pos": [430, 220], "size": [210, 58], "flags": {}, "order": 3, "mode": 0,
        "inputs": [], "outputs": [{"name": "BOOLEAN", "type": "BOOLEAN", "links": [2]}],
        "properties": {"Node name for S&R": "PrimitiveBoolean"}, "widgets_values": [True],
        "widgets_values_named": {"value": True}, "title": "Include approved motion",
    }
    motion_advanced = {
        "motion_source": "generated_clip", "generated_motion_strength": 1.0,
        "atmospheric_motion_mode": "cached_clip", "generated_clip_path": MOTION_CLIP,
        "generated_clip_max_seconds": 10.0, "generated_clip_overlap_seconds": 0.8,
        "audio_driver": "slow", "secondary_audio_driver": "none", "secondary_driver_mix": 0.0,
        "on_beat_motion": 0.0, "response_min": 0.0, "response_max": 1.0,
        "foreground_protection": False, "target_id": "approved_full_scene_motion",
    }
    motion_target.update({"id": 5, "pos": [740, 60], "title": "Approved full-scene motion clip", "order": 5})
    motion_target["inputs"][0]["link"] = 1
    motion_target["inputs"][1]["link"] = 2
    motion_target["widgets_values"] = [
        "approved_full_scene_motion", "approved full-scene Wan motion",
        "Loop the reviewed motion clip; do not add procedural geometry motion.",
        "organic", "environment", "still", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        json.dumps(motion_advanced, separators=(",", ":")), None,
    ]
    motion_target["widgets_values_named"] = dict(zip(
        ["target_id", "object_name", "animation_prompt", "target_role", "linked_group", "motion_type",
         "beat_flicker", "ambient_flicker", "motion_amount", "max_luminance_change", "glow_strength",
         "glow_radius_px", "saturation_variation", "hue_variation_degrees", "advanced_settings_json", "advanced_settings"],
        motion_target["widgets_values"],
    ))
    motion_target["outputs"][0]["links"] = [3]
    stack_one.update({"id": 6, "pos": [1110, 110], "order": 7})
    stack_one["inputs"] = [{"localized_name": "target", "name": "target", "type": "LOCAL_VISUALIZER_TARGET", "link": 3}]
    stack_one["outputs"][0]["links"] = [7]

    light_load = {
        "id": 7, "type": "LoadImageMask", "pos": [430, 480], "size": [300, 310], "flags": {}, "order": 4, "mode": 0,
        "inputs": [], "outputs": [{"name": "MASK", "type": "MASK", "links": [4]}],
        "properties": {"Node name for S&R": "LoadImageMask"},
        "widgets_values": [LIGHT_MASK_NAME, "red"], "widgets_values_named": {"image": LIGHT_MASK_NAME, "channel": "red"},
        "title": "Source-derived practical-light mask",
    }
    light_bool = {
        "id": 8, "type": "PrimitiveBoolean", "pos": [430, 820], "size": [210, 58], "flags": {}, "order": 6, "mode": 0,
        "inputs": [], "outputs": [{"name": "BOOLEAN", "type": "BOOLEAN", "links": [5]}],
        "properties": {"Node name for S&R": "PrimitiveBoolean"}, "widgets_values": [True],
        "widgets_values_named": {"value": True}, "title": "Include music-synced lighting",
    }
    light_advanced = {
        "motion_source": "procedural", "generated_motion_strength": 0.0, "audio_driver": "beat",
        "secondary_audio_driver": "high", "secondary_driver_mix": 0.22, "on_beat_motion": 0.0,
        "response_attack_ms": 32.0, "response_decay_ms": 150.0, "response_release_ms": 240.0,
        "response_smoothing": 0.10, "response_min": 0.0, "response_max": 1.0,
        "response_sensitivity": 1.15, "lighting_gain": 1.1, "target_id": "practical_lights",
    }
    light_target.update({"id": 9, "pos": [740, 470], "title": "Music-synced practical lights — no movement", "order": 8})
    light_target["inputs"][0]["link"] = 4
    light_target["inputs"][1]["link"] = 5
    light_target["widgets_values"] = [
        "practical_lights", "practical lights and emissive reflections", "Pulse and glow in place with the music.",
        "light_source", "lighting", "still", 1.20, 0.14, 0.0, 0.11, 0.38, 24.0, 0.06, 0.0,
        json.dumps(light_advanced, separators=(",", ":")), None,
    ]
    light_target["widgets_values_named"] = dict(zip(
        ["target_id", "object_name", "animation_prompt", "target_role", "linked_group", "motion_type",
         "beat_flicker", "ambient_flicker", "motion_amount", "max_luminance_change", "glow_strength",
         "glow_radius_px", "saturation_variation", "hue_variation_degrees", "advanced_settings_json", "advanced_settings"],
        light_target["widgets_values"],
    ))
    light_target["outputs"][0]["links"] = [6]
    stack_two.update({"id": 10, "pos": [1110, 520], "order": 9})
    stack_two["inputs"] = [
        {"localized_name": "target", "name": "target", "type": "LOCAL_VISUALIZER_TARGET", "link": 6},
        {"localized_name": "previous_targets", "name": "previous_targets", "shape": 7, "type": "LOCAL_VISUALIZER_TARGETS", "link": 7},
    ]
    stack_two["outputs"][0]["links"] = [10]

    renderer.update({"id": 11, "pos": [1430, 40], "order": 10, "title": "FULL SONG — motion + lighting + title + 2048-band EQ"})
    renderer["inputs"][0]["link"] = 8
    renderer["inputs"][1]["link"] = 9
    renderer["inputs"][2]["link"] = 10
    settings = {
        "fps": 16, "delivery_resolution": "1080p", "pattern_key": 20261020,
        "maximum_stabilization_percent": 0.0, "apply_brand_logo": False,
        "brand_logo_width_percent": 10.0, "brand_logo_opacity": 0.68,
        "apply_wordmark": True, "wordmark_width_percent": 30.0, "wordmark_opacity": 0.92,
        "overlay_margin_px": 24, "title_card_enabled": True, "band_name": "Infra Choir",
        "song_title": "Raise the Neon Black", "title_card_image": "(generate from text)",
        "title_card_placement": "center", "title_card_start_seconds": 0.0,
        "title_card_duration_seconds": 5.0, "title_card_fade_seconds": 0.65,
        "title_sparkle_enabled": True, "title_sparkle_strength": 0.45,
        "title_sparkle_audio_response": 0.30, "eq_enabled": True,
        "eq_mode": "fine_spectrum_bars", "eq_height_percent": 10.5, "eq_opacity": 0.42,
        "eq_color": "#35D8D2", "eq_smoothing": 0.72, "organic_motion_expansion_percent": 0.0,
        "title_card_source_visibility": 0.20, "brand_logo_image": "(none)", "output_prefix": OUTPUT_PREFIX,
        "enhancements_enabled": True, "target_envelopes_enabled": True,
        "high_resolution_eq_enabled": True, "eq_band_count": 512, "eq_fft_size": 8192,
        "eq_hop_size": 2048, "eq_frequency_scale": "log", "eq_min_frequency": 20.0,
        "eq_max_frequency": 20000.0, "eq_attack_ms": 35.0, "eq_release_ms": 220.0,
        "eq_peak_enabled": True, "eq_peak_hold_seconds": 0.16, "eq_peak_decay_per_second": 1.6,
        "eq_peak_color": "#F4D7C3", "eq_gain": 1.0, "eq_dynamic_range_db": 66.0,
        "eq_noise_floor_db": -72.0, "eq_margin_percent": 2.0, "analysis_sensitivity": 1.0,
        "transient_emphasis": 0.22, "edge_glow_effects_enabled": True,
        "shimmer_effects_enabled": True, "atmospheric_effects_enabled": True,
        "section_dynamics_enabled": True, "section_override_json": "[]",
        "title_text_alignment": "center", "auto_targets_enabled": False,
        "eq_ultra_band_count": 2048, "eq_density_render_mode": "auto",
        "generated_clip_cache_enabled": True, "expansive_atmosphere_enabled": False,
    }
    widget_names = [item["widget"]["name"] for item in renderer["inputs"] if "widget" in item and item["widget"]["name"] != "upload"]
    renderer["widgets_values"] = [settings[name] for name in widget_names] + ["image"]
    renderer["widgets_values_named"] = {**settings, "upload": "image"}

    image["outputs"][0]["links"] = [8]
    audio["outputs"][0]["links"] = [9]
    links = [
        _link(1, 3, 0, 5, 0, "MASK"), _link(2, 4, 0, 5, 1, "BOOLEAN"),
        _link(3, 5, 0, 6, 0, "LOCAL_VISUALIZER_TARGET"),
        _link(4, 7, 0, 9, 0, "MASK"), _link(5, 8, 0, 9, 1, "BOOLEAN"),
        _link(6, 9, 0, 10, 0, "LOCAL_VISUALIZER_TARGET"),
        _link(7, 6, 0, 10, 1, "LOCAL_VISUALIZER_TARGETS"),
        _link(8, 1, 0, 11, 0, "IMAGE"), _link(9, 2, 0, 11, 1, "AUDIO"),
        _link(10, 10, 0, 11, 2, "LOCAL_VISUALIZER_TARGETS"),
    ]
    workflow = {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "tws:infra-choir:raise-the-neon-black:full-visualizer:v2")),
        "revision": 0, "last_node_id": 11, "last_link_id": 10,
        "nodes": [image, audio, solid, motion_bool, motion_target, stack_one, light_load, light_bool, light_target, stack_two, renderer],
        "links": links, "groups": [], "config": {}, "extra": {"ds": {"scale": 0.75, "offset": [40, 40]}},
        "version": 0.4,
    }
    WORKFLOW.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    prompt = {
        "1": {"class_type": "LoadImage", "inputs": {"image": IMAGE_NAME}},
        "2": {"class_type": "LoadAudio", "inputs": {"audio": AUDIO_NAME}},
        "3": {"class_type": "SolidMask", "inputs": {"value": 1.0, "width": 1672, "height": 941}},
        "4": {"class_type": "PrimitiveBoolean", "inputs": {"value": True}},
        "5": {"class_type": "InfraChoirManualTargetCompact", "inputs": {
            "mask": ["3", 0], "use_in_render": ["4", 0], **dict(zip(
                ["target_id", "object_name", "animation_prompt", "target_role", "linked_group", "motion_type",
                 "beat_flicker", "ambient_flicker", "motion_amount", "max_luminance_change", "glow_strength",
                 "glow_radius_px", "saturation_variation", "hue_variation_degrees", "advanced_settings_json"],
                motion_target["widgets_values"][:15],
            ))}},
        "6": {"class_type": "VisualizerTargetStack", "inputs": {"target": ["5", 0]}},
        "7": {"class_type": "LoadImageMask", "inputs": {"image": LIGHT_MASK_NAME, "channel": "red"}},
        "8": {"class_type": "PrimitiveBoolean", "inputs": {"value": True}},
        "9": {"class_type": "InfraChoirManualTargetCompact", "inputs": {
            "mask": ["7", 0], "use_in_render": ["8", 0], **dict(zip(
                ["target_id", "object_name", "animation_prompt", "target_role", "linked_group", "motion_type",
                 "beat_flicker", "ambient_flicker", "motion_amount", "max_luminance_change", "glow_strength",
                 "glow_radius_px", "saturation_variation", "hue_variation_degrees", "advanced_settings_json"],
                light_target["widgets_values"][:15],
            ))}},
        "10": {"class_type": "VisualizerTargetStack", "inputs": {"target": ["9", 0], "previous_targets": ["6", 0]}},
        "11": {"class_type": "InfraChoirVisualizerDualTrack", "inputs": {
            "image": ["1", 0], "audio": ["2", 0], "targets": ["10", 0], **settings,
        }},
    }
    API_PROMPT.write_text(json.dumps(prompt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return WORKFLOW, API_PROMPT, light_mask


if __name__ == "__main__":
    for item in build():
        print(item)
