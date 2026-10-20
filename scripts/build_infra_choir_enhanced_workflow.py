from __future__ import annotations

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "user" / "default" / "workflows" / "music_visualizer_infra_choir_production.json"
OUTPUT = ROOT / "user" / "default" / "workflows" / "music_visualizer_infra_choir_enhanced.json"

TARGET_FIELDS = [
    ("secondary_audio_driver", "COMBO"),
    ("secondary_driver_mix", "FLOAT"),
    ("response_attack_ms", "FLOAT"),
    ("response_decay_ms", "FLOAT"),
    ("response_hold_ms", "FLOAT"),
    ("response_sustain", "FLOAT"),
    ("response_release_ms", "FLOAT"),
    ("response_smoothing", "FLOAT"),
    ("response_min", "FLOAT"),
    ("response_max", "FLOAT"),
    ("response_sensitivity", "FLOAT"),
    ("response_curve", "FLOAT"),
    ("rhythmic_subdivision", "COMBO"),
    ("accent_weight", "FLOAT"),
    ("group_gain", "FLOAT"),
    ("group_delay_ms", "FLOAT"),
    ("lighting_gain", "FLOAT"),
    ("edge_glow_enabled", "BOOLEAN"),
    ("edge_glow_amount", "FLOAT"),
    ("shimmer_enabled", "BOOLEAN"),
    ("shimmer_amount", "FLOAT"),
    ("section_response", "FLOAT"),
]

RENDERER_FIELDS = [
    ("enhancements_enabled", "BOOLEAN"),
    ("target_envelopes_enabled", "BOOLEAN"),
    ("high_resolution_eq_enabled", "BOOLEAN"),
    ("eq_band_count", "COMBO"),
    ("eq_fft_size", "COMBO"),
    ("eq_hop_size", "COMBO"),
    ("eq_frequency_scale", "COMBO"),
    ("eq_min_frequency", "FLOAT"),
    ("eq_max_frequency", "FLOAT"),
    ("eq_attack_ms", "FLOAT"),
    ("eq_release_ms", "FLOAT"),
    ("eq_peak_enabled", "BOOLEAN"),
    ("eq_peak_hold_seconds", "FLOAT"),
    ("eq_peak_decay_per_second", "FLOAT"),
    ("eq_peak_color", "STRING"),
    ("eq_gain", "FLOAT"),
    ("eq_dynamic_range_db", "FLOAT"),
    ("eq_noise_floor_db", "FLOAT"),
    ("eq_margin_percent", "FLOAT"),
    ("analysis_sensitivity", "FLOAT"),
    ("transient_emphasis", "FLOAT"),
    ("edge_glow_effects_enabled", "BOOLEAN"),
    ("shimmer_effects_enabled", "BOOLEAN"),
    ("atmospheric_effects_enabled", "BOOLEAN"),
    ("section_dynamics_enabled", "BOOLEAN"),
    ("section_override_json", "STRING"),
]

TARGET_PRESETS = {
    "red_hair": ["none", 0.0, 350.0, 900.0, 120.0, 0.45, 1600.0, 0.55, 0.12, 0.58, 0.75, 1.35, 1, 0.0, 0.75, 0.0, 1.0, False, 0.0, False, 0.0, 0.18],
    "red_fabric": ["energy", 0.16, 280.0, 720.0, 100.0, 0.35, 1300.0, 0.48, 0.10, 0.65, 0.82, 1.25, 1, 0.0, 0.82, 40.0, 1.0, False, 0.0, False, 0.0, 0.28],
    "industrial_smoke": ["onset", 0.18, 220.0, 620.0, 80.0, 0.30, 1150.0, 0.42, 0.12, 0.78, 0.90, 1.15, 1, 0.0, 0.92, 0.0, 1.0, False, 0.0, True, 0.12, 0.52],
    "clouds": ["high", 0.08, 480.0, 1200.0, 180.0, 0.55, 2200.0, 0.62, 0.10, 0.52, 0.70, 1.45, 1, 0.0, 0.68, 80.0, 1.0, False, 0.0, True, 0.05, 0.32],
    "sun_source": ["kick", 0.42, 25.0, 230.0, 55.0, 0.16, 420.0, 0.18, 0.05, 1.0, 1.08, 0.82, 1, 0.12, 1.0, 0.0, 1.85, True, 0.52, False, 0.0, 0.36],
    "sun_illumination": ["phrase", 0.20, 180.0, 520.0, 100.0, 0.28, 850.0, 0.34, 0.12, 0.92, 1.0, 1.0, 1, 0.0, 1.0, 130.0, 3.0, False, 0.0, False, 0.0, 0.48],
    "river_reflection": ["hihat", 0.34, 80.0, 330.0, 50.0, 0.12, 620.0, 0.26, 0.03, 0.88, 0.94, 0.92, 2, 0.12, 0.92, 180.0, 1.8, True, 0.18, True, 0.42, 0.42],
}

DRIVER_OVERRIDES = {
    "red_hair": "slow",
    "red_fabric": "slow",
    "industrial_smoke": "slow",
    "clouds": "slow",
    "sun_source": "beat",
    "sun_illumination": "beat",
    "river_reflection": "beat",
}

RENDERER_VALUES = [
    True, True, True,
    256, 8192, 2048, "log", 20.0, 20000.0, 35.0, 220.0, True, 0.16,
    1.6, "#D9B5A2", 1.0, 66.0, -72.0, 2.0, 1.0, 0.22, True, True, True, True, "[]",
]


def widget_input(name: str, kind: str) -> dict:
    return {"localized_name": name, "name": name, "type": kind, "widget": {"name": name}, "link": None}


def main() -> int:
    workflow = json.loads(SOURCE.read_text(encoding="utf-8"))
    workflow = copy.deepcopy(workflow)
    workflow["id"] = "f4f20d8f-acde-4aa6-a168-202610130001"
    workflow["revision"] = 0
    nodes = {node["id"]: node for node in workflow["nodes"]}
    shift = len(TARGET_FIELDS)
    target_ids = set()
    for node in workflow["nodes"]:
        if node["type"] != "InfraChoirAnimationTarget":
            continue
        target_ids.add(node["id"])
        node["type"] = "InfraChoirAnimationTargetEnhanced"
        node["properties"]["Node name for S&R"] = node["type"]
        target_id = str(node["widgets_values"][1])
        node["widgets_values"][7] = DRIVER_OVERRIDES[target_id]
        values = TARGET_PRESETS[target_id]
        node["inputs"][21:21] = [widget_input(name, kind) for name, kind in TARGET_FIELDS]
        node["widgets_values"].extend(values)
        named = node.setdefault("widgets_values_named", {})
        named["audio_driver"] = DRIVER_OVERRIDES[target_id]
        named.update(dict(zip((name for name, _ in TARGET_FIELDS), values)))
        node["size"][1] = 1160
        node["title"] = f"Enhanced driver + verified mask: {target_id}"
    for link in workflow["links"]:
        if link[3] in target_ids and link[4] >= 21:
            link[4] += shift
    for target_id in target_ids:
        target = nodes[target_id]
        for slot, input_value in enumerate(target["inputs"]):
            if input_value.get("link") is not None:
                link = next(item for item in workflow["links"] if item[0] == input_value["link"])
                if link[3] != target_id or link[4] != slot:
                    raise RuntimeError(f"Target {target_id} input {slot} has inconsistent link metadata.")

    renderer = nodes[90]
    renderer["type"] = "InfraChoirVisualizerEnhanced"
    renderer["properties"]["Node name for S&R"] = renderer["type"]
    renderer["title"] = "ENHANCED PRODUCTION: cached 256-band EQ + target-local musical drivers"
    renderer["inputs"].extend(widget_input(name, kind) for name, kind in RENDERER_FIELDS)
    renderer["widgets_values"][23] = "fine_spectrum_bars"
    renderer["widgets_values"][24] = 10.5
    renderer["widgets_values"][25] = 0.40
    renderer["widgets_values"][-1] = "infra_choir/enhanced_bella_ciao"
    renderer["widgets_values"].extend(RENDERER_VALUES)
    named = renderer.setdefault("widgets_values_named", {})
    named.update({"eq_mode": "fine_spectrum_bars", "eq_height_percent": 10.5, "eq_opacity": 0.40, "output_prefix": "infra_choir/enhanced_bella_ciao"})
    named.update(dict(zip((name for name, _ in RENDERER_FIELDS), RENDERER_VALUES)))
    renderer["size"][1] = 1640

    for group in workflow.get("groups", []):
        if group.get("id") == 4:
            group["title"] = "Enhanced production renderer — cached high-resolution analysis, selective effects, and 256-band EQ"
            group["bounding"][3] = 1740
    workflow.setdefault("extra", {})["infra_choir_enhancement"] = {
        "version": 2,
        "base_workflow": SOURCE.name,
        "fill_nodes_license": "Apache-2.0",
        "integration": "Adapted transient-band and ADSR concepts; batch image/VFX/sequencer nodes intentionally excluded.",
    }
    OUTPUT.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
