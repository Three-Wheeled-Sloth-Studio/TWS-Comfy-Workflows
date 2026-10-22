from __future__ import annotations

import importlib.util
import json
import math
import sys
import tempfile
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "custom_nodes/comfyui_audio_duration_plan/local_visualizer_nodes.py"
WORKFLOW_PATH = ROOT / "user/default/workflows/music_visualizer_infra_choir_dual_track_scaffold.json"
GENERIC_CACHED_WORKFLOW_PATH = ROOT / "user/default/workflows/music_visualizer_cached_motion_full_song.json"
USER_GENERIC_CACHED_WORKFLOW_PATH = ROOT / "user/default/workflows/music_visualizer_cached_motion_full.json"
ADVANCED_UI_PATH = ROOT / "custom_nodes/comfyui_audio_duration_plan/web/infra_choir_manual_advanced.js"


def _module():
    specification = importlib.util.spec_from_file_location("infra_choir_dual_track_test_module", MODULE_PATH)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _assert_workflow_schema(module) -> None:
    workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    nodes = {node["id"]: node for node in workflow["nodes"]}
    assert isinstance(nodes[1]["widgets_values"][0], str) and nodes[1]["widgets_values"][0]
    assert isinstance(nodes[2]["widgets_values"][0], str) and nodes[2]["widgets_values"][0]
    expected_types = {
        10: "VisualizerManualTargetDetector",
        12: "InfraChoirManualTargetCompact",
        20: "VisualizerManualTargetDetector",
        22: "InfraChoirManualTargetCompact",
        30: "VisualizerManualTargetDetector",
        32: "InfraChoirManualAtmosphereTarget",
        40: "VisualizerManualTargetDetector",
        42: "InfraChoirManualAtmosphereTarget",
        50: "VisualizerManualTargetDetector",
        52: "InfraChoirManualTargetCompact",
        60: "VisualizerManualTargetDetector",
        62: "InfraChoirManualTargetCompact",
        70: "VisualizerManualTargetDetector",
        72: "InfraChoirManualTargetCompact",
        90: "InfraChoirVisualizerDualTrack",
        91: "InfraChoirAutoDiscover",
        92: "InfraChoirApprovedTargets",
        93: "InfraChoirTargetMerge",
    }
    effect_detector = {12: 10, 22: 20, 32: 30, 42: 40, 52: 50, 62: 60, 72: 70}
    for node_id, node_type in expected_types.items():
        node = nodes[node_id]
        assert node["type"] == node_type, (node_id, node["type"])
        schema = module.NODE_CLASS_MAPPINGS[node_type].INPUT_TYPES()
        expected = list(schema.get("required", {}))
        optional = schema.get("optional", {})
        expected.extend(name for name in optional if any(item["name"] == name for item in node["inputs"]))
        actual = [item["name"] for item in node["inputs"]]
        # ComfyUI may serialize connected optional sockets beside the required
        # sockets instead of after them. Preserve the user's saved ordering and
        # validate the complete schema membership here.
        if node_id in (12, 22, 32, 42, 52, 62, 72):
            assert set(actual) == set(expected) and len(actual) == len(expected), (node_id, actual, expected)
        else:
            # Do not rewrite unrelated saved nodes merely to drop a legacy UI
            # socket that ComfyUI can safely retain.
            assert set(expected).issubset(actual), (node_id, actual, expected)
        if node_id in (12, 22, 32, 42, 52, 62, 72):
            widget_count = sum(item.get("link") is None for item in node["inputs"])
            # The connected forceInput Boolean still consumes a hidden widget
            # slot, and the extension appends one non-serialized button slot.
            assert len(node.get("widgets_values", [])) == widget_count + 2, (
                node_id, len(node.get("widgets_values", [])), widget_count,
            )
            expected_values = [nodes[effect_detector[node_id]]["widgets_values_named"]["use_in_render"]]
            expected_values.extend(
                node["widgets_values_named"][item["name"]]
                for item in node["inputs"] if item.get("link") is None
            )
            expected_values.append(None)
            assert node["widgets_values"] == expected_values, (node_id, node["widgets_values"], expected_values)
        if node_id in (10, 20, 30, 40, 50, 60, 70):
            expected_values = [
                node["widgets_values_named"][item["name"]]
                for item in node["inputs"] if item.get("link") is None
            ]
            assert node["widgets_values"] == expected_values, (node_id, node["widgets_values"], expected_values)
    links = {link[0]: link for link in workflow["links"]}
    assert links[51][1:5] == [73, 0, 93, 0]
    assert links[54][1:5] == [92, 0, 93, 1]
    assert links[55][1:5] == [93, 0, 90, 2]
    assert links[56][1:5] == [30, 4, 32, 1]
    assert links[57][1:5] == [40, 4, 42, 1]
    assert links[58][1:5] == [10, 4, 12, 1]
    assert links[59][1:5] == [20, 4, 22, 1]
    assert links[60][1:5] == [50, 4, 52, 1]
    assert links[61][1:5] == [60, 4, 62, 1]
    assert links[62][1:5] == [70, 4, 72, 1]
    assert nodes[93]["widgets_values"][0] == "manual_only"
    for detector_id in (10, 20, 30, 40, 50, 60, 70):
        assert "use_in_render" in nodes[detector_id]["widgets_values_named"]
    for node_id in (12, 22, 32, 42, 52, 62, 72):
        assert "mask_verified" not in nodes[node_id]["widgets_values_named"]
        target_id = nodes[node_id]["widgets_values_named"]["target_id"]
        assert isinstance(target_id, str) and target_id
        assert nodes[node_id]["widgets_values"][1] == target_id
        assert any(item["name"] == "target_id" for item in nodes[node_id]["inputs"])
        assert "advanced_settings_json" in nodes[node_id]["widgets_values_named"]
        advanced = json.loads(nodes[node_id]["widgets_values_named"]["advanced_settings_json"])
        assert isinstance(advanced, dict)
        assert advanced["target_id"] == target_id
        assert nodes[node_id]["size"][1] <= 500
    for node_id in (12, 22, 52, 62, 72):
        named = nodes[node_id]["widgets_values_named"]
        assert named["target_role"] in {"organic", "light_source", "illumination", "reflection"}
        assert named["motion_type"] in {"auto", "billow", "sway", "drift", "still"}
        assert isinstance(named["hue_variation_degrees"], (int, float))
        assert -30.0 <= named["hue_variation_degrees"] <= 30.0
        assert -0.5 <= named["saturation_variation"] <= 0.5
        assert 0.0 <= named["glow_strength"] <= 1.0
    for node_id in (32, 42):
        named = nodes[node_id]["widgets_values_named"]
        assert 0.0 <= named["smoke_intensity"] <= 3.0
        assert 0.0 <= named["smoke_boundary_expansion_percent"] <= 50.0
        assert 0.0 <= named["billow_amount"] <= 2.0
    advanced_ui = ADVANCED_UI_PATH.read_text(encoding="utf-8")
    assert "Generated motion strength" not in advanced_ui
    assert "Primary smoke behavior is controlled on the card" in advanced_ui
    assert "restoreNamedWidgetValues(this, serializedNode)" in advanced_ui
    assert "serializeNamedWidgetValues(this, serializedNode)" in advanced_ui
    assert 'nodeData.name === "VisualizerManualTargetDetector"' in advanced_ui
    assert 'text("target_id", "Target ID", "manual_target"), source: "widget"' in advanced_ui
    assert '"target_id",' in advanced_ui.split("const baseHiddenNames", 1)[1]
    atmospheric_required = module.InfraChoirAtmosphericTargetEnhanced.INPUT_TYPES()["required"]
    assert atmospheric_required["mask_verified"][1]["default"] is True
    assert "Leave empty for procedural smoke" in atmospheric_required["generated_clip_path"][1]["tooltip"]


def _assert_generic_cached_motion_workflow() -> None:
    workflow = json.loads(GENERIC_CACHED_WORKFLOW_PATH.read_text(encoding="utf-8"))
    nodes = {node["id"]: node for node in workflow["nodes"]}
    assert nodes[1]["type"] == "LoadImage" and nodes[1]["widgets_values_named"]["image"] == ""
    assert nodes[2]["type"] == "LoadAudio" and nodes[2]["widgets_values_named"]["audio"] == ""
    assert nodes[4]["widgets_values_named"]["value"] is True
    assert nodes[5]["type"] == "InfraChoirGeneratedMotionTarget"
    assert nodes[5]["inputs"][1]["link"] == 2000
    assert nodes[7]["type"] == "InfraChoirMultiLightDetector"
    assert nodes[7]["widgets_values_named"]["max_candidates"] == 7
    assert nodes[7]["widgets_values_named"]["use_in_render"] is True
    assert nodes[8]["type"] == "VisualizerMaskReview"
    assert nodes[8]["widgets_values_named"]["source_fingerprint"] == ""
    assert nodes[9]["widgets_values_named"]["target_role"] == "light_source"
    assert nodes[9]["widgets_values_named"]["motion_type"] == "still"
    assert nodes[11]["widgets_values_named"]["maximum_stabilization_percent"] == 0.0
    assert nodes[11]["widgets_values_named"]["output_prefix"] == "music_visualizer/final/render"
    links = {link[0]: link for link in workflow["links"]}
    assert links[4][1:5] == [1, 0, 7, 0]
    assert links[5][1:5] == [7, 0, 8, 1]
    assert links[6][1:5] == [7, 1, 8, 0]
    assert links[7][1:5] == [1, 0, 8, 2]
    assert links[8][1:5] == [8, 0, 9, 0]
    assert links[9][1:5] == [7, 4, 9, 1]
    assert links[15][1:5] == [7, 1, 12, 0]
    assert links[2000][1:5] == [296, 0, 5, 1]
    subgraphs = {item["id"]: item for item in workflow.get("definitions", {}).get("subgraphs", [])}
    extension_type = nodes[279]["type"]
    assert extension_type in subgraphs
    assert subgraphs[extension_type]["name"] == "Video S2V Extend"
    assert workflow["state"]["lastNodeId"] == workflow["last_node_id"]
    assert workflow["state"]["lastLinkId"] == workflow["last_link_id"]
    assert nodes[12]["type"] == "PreviewImage"
    saved = json.loads(USER_GENERIC_CACHED_WORKFLOW_PATH.read_text(encoding="utf-8"))
    saved_nodes = {node["id"]: node for node in saved["nodes"]}
    assert saved_nodes[5]["type"] == "InfraChoirGeneratedMotionTarget"
    assert saved_nodes[5]["pos"] == [835.7916666666666, -339.97222222222206]
    assert saved_nodes[7]["pos"] == [228.33333333333348, 570.8333333333333]
    assert saved_nodes[12]["type"] == "PreviewImage"


def main() -> int:
    import numpy as np
    import torch

    module = _module()
    reference = np.zeros((24, 32, 3), dtype=np.uint8)
    shifted = np.roll(reference, 6, axis=0)
    assert module._phase_correlation_shift(reference, shifted, 0.0) == (0.0, 0.0, False)

    ramp = tuple(np.full((2, 2, 3), value, dtype=np.uint8) for value in range(12))
    looped = [module._looped_motion_frame(ramp, index, 3) for index in range(10)]
    loop_differences = [float(np.abs(a.astype(np.float32) - b.astype(np.float32)).mean()) for a, b in zip(looped, looped[1:])]
    assert len(looped) == 10
    assert np.array_equal(looped[0], ramp[3])
    assert loop_differences[-1] <= max(loop_differences[:-1])
    _assert_workflow_schema(module)
    _assert_generic_cached_motion_workflow()
    choices = module.InfraChoirCachedMotionTarget.INPUT_TYPES()["required"]["generated_clip_path"][0]
    assert choices[0] == "(select a cached motion clip)"
    generated = module.InfraChoirGeneratedMotionTarget.INPUT_TYPES()["required"]
    assert generated["generated_motion"][0] == "IMAGE"

    sample_rate = 48000
    seconds = 0.5
    time = torch.arange(round(sample_rate * seconds), dtype=torch.float32) / sample_rate
    waveform = (
        0.25 * torch.sin(math.tau * 73.0 * time)
        + 0.17 * torch.sin(math.tau * 1400.0 * time)
        + 0.08 * torch.sin(math.tau * 11000.0 * time)
    )
    audio = {"waveform": waveform[None, None, :], "sample_rate": sample_rate}
    for bands in (1024, 2048):
        features = module._enhanced_audio_features(
            audio, 16, seconds, bands, 8192, 2048, "log",
            20.0, 20000.0, 66.0, -72.0, 1.0, 0.22,
        )
        assert features["spectrum_bands"].shape == (8, bands)
        assert np.isfinite(features["spectrum_bands"]).all()

    frame = np.zeros((180, 320, 3), dtype=np.uint8)
    values = np.linspace(0.0, 1.0, 2048, dtype=np.float32)
    module._apply_high_resolution_eq(
        frame, values, values, "fine_spectrum_bars", 12.0, 0.5,
        (142, 19, 37), density_mode="rms",
    )
    assert np.any(frame[-30:] != 0) and not np.any(frame[:-50] != 0)

    dilation_mask = np.zeros((180, 320), dtype=np.float32)
    dilation_mask[80:100, 150:170] = 1.0
    dilation = module._dilated_layer(module._Layer(dilation_mask, (150, 80, 170, 100)), 50, 0.0)
    assert dilation.bounds == (100, 30, 220, 150)
    assert dilation.mask.shape == dilation_mask.shape
    assert float(dilation.mask[30:150, 100:220].min()) == 1.0
    assert float(dilation.mask[:29].max()) == 0.0
    glow = module._emissive_glow_layer(module._Layer(dilation_mask, (150, 80, 170, 100)), 18.0)
    assert float(glow.mask[90, 160]) == 1.0
    assert float(glow.mask[65, 160]) > 0.05
    assert float(glow.mask.sum()) > float(dilation_mask.sum()) * 2.0

    title_base = np.full((360, 640, 3), 96, dtype=np.uint8)
    centered, centered_outline, _ = module._render_generated_title_card(
        title_base, "Infra Choir", "A Long Song Title", "center", 40, 0.2, "center",
    )
    left, left_outline, _ = module._render_generated_title_card(
        title_base, "Infra Choir", "A Long Song Title", "center", 40, 0.2, "left",
    )
    assert centered.shape == left.shape == title_base.shape
    centered_points, left_points = np.argwhere(centered_outline > 0.0), np.argwhere(left_outline > 0.0)
    assert centered_points[:, 0].min() == left_points[:, 0].min()
    assert left_points[:, 1].min() < centered_points[:, 1].min()

    image = torch.zeros((1, 24, 32, 3), dtype=torch.float32)
    image[:, 4:20, 8:24, 0] = 0.8
    mask = torch.zeros((24, 32), dtype=torch.float32)
    mask[5:18, 9:22] = 1.0
    generated_target, generated_diagnostic, _ = module.InfraChoirGeneratedMotionTarget().configure(
        mask, image.repeat(4, 1, 1, 1), True, 1.0, 0.8,
    )
    assert generated_diagnostic.endswith(": ready")
    assert generated_target["generated_motion"].shape[0] == 4
    assert generated_target["motion_source"] == "generated_clip"
    assert generated_target["motion_type"] == "still"
    encoded = module._mask_png_base64(mask)
    assert torch.allclose(module._mask_from_png_base64(encoded), mask)
    atmospheric_inputs = module.InfraChoirAtmosphericTargetEnhanced.INPUT_TYPES()["required"]
    assert "smoke_intensity" in atmospheric_inputs
    assert "smoke_boundary_expansion_percent" in atmospheric_inputs
    assert "clip_loop_blend_seconds" not in atmospheric_inputs
    assert "atmospheric_expansion_percent" not in atmospheric_inputs
    atmospheric_values = {}
    for name, specification in atmospheric_inputs.items():
        choices = specification[0]
        metadata = specification[1] if len(specification) > 1 and isinstance(specification[1], dict) else {}
        atmospheric_values[name] = metadata.get("default", choices[0] if isinstance(choices, list) else None)
    atmospheric_values.update({
        "enabled": True, "target_id": "manual_smoke", "object_name": "smoke",
        "animation_prompt": "strong smoke billow", "mask_verified": True,
        "target_role": "organic", "motion_type": "billow",
        "smoke_intensity": 2.3, "smoke_boundary_expansion_percent": 22.0,
    })
    configured_smoke, _, _ = module.InfraChoirAtmosphericTargetEnhanced().configure(
        **atmospheric_values, mask=mask,
    )
    assert configured_smoke["smoke_effect_strength"] == 2.3
    assert configured_smoke["atmospheric_expansion_percent"] == 22.0
    compact_smoke, compact_diagnostic, _ = module.InfraChoirManualAtmosphereTarget().configure(
        mask, True, "compact_smoke", "smoke", "smoke billowing organically",
        1.8, 30.0, 0.75, True,
        json.dumps({"target_id": "compact_smoke"}),
    )
    assert compact_diagnostic.endswith(": ready")
    assert compact_smoke["mask_verified"] is True
    assert compact_smoke["smoke_effect_strength"] == 1.8
    assert compact_smoke["atmospheric_expansion_percent"] == 30.0
    compact_light, compact_light_diagnostic, _ = module.InfraChoirManualTargetCompact().configure(
        mask, True, "compact_light", "lamp", "lamp flickering locally",
        "light_source", "linked_lights", "still", 0.5, 0.1, 0.0,
        0.12, 0.3, 24.0, 0.04, -2.0,
        json.dumps({"target_id": "compact_light"}),
    )
    assert compact_light_diagnostic.endswith(": ready")
    assert compact_light["mask_verified"] is True
    assert compact_light["motion_type"] == "still"
    assert compact_light["on_beat_flicker"] == 0.5
    advanced_light, _, _ = module.InfraChoirManualTargetCompact().configure(
        mask, True, "advanced_light", "lamp", "lamp flickering locally",
        "light_source", "linked_lights", "still", 0.5, 0.1, 0.0,
        0.12, 0.3, 24.0, 0.04, -2.0,
        json.dumps({"target_id": "advanced_light", "audio_driver": "snare", "response_attack_ms": 15.0, "shimmer_enabled": True}),
    )
    assert advanced_light["audio_driver"] == "snare"
    assert advanced_light["response_attack_ms"] == 15.0
    assert advanced_light["shimmer_enabled"] is True
    cached_motion, _, _ = module.InfraChoirManualTargetCompact().configure(
        mask, True, "cached_motion", "approved motion", "loop the approved clip",
        "organic", "environment", "still", 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0,
        json.dumps({
            "target_id": "cached_motion",
            "motion_source": "generated_clip",
            "generated_motion_strength": 1.0,
            "atmospheric_motion_mode": "cached_clip",
            "generated_clip_path": "infra_choir/motion_assets/approved.mp4",
            "generated_clip_max_seconds": 10.0,
            "generated_clip_overlap_seconds": 0.8,
            "foreground_protection": False,
        }),
    )
    assert cached_motion["motion_source"] == "generated_clip"
    assert cached_motion["atmospheric_motion_mode"] == "cached_clip"
    assert cached_motion["generated_clip_path"] == "infra_choir/motion_assets/approved.mp4"
    assert cached_motion["generated_clip_max_seconds"] == 10.0
    assert cached_motion["generated_clip_overlap_seconds"] == 0.8
    assert cached_motion["foreground_protection"] is False
    advanced_smoke, _, _ = module.InfraChoirManualAtmosphereTarget().configure(
        mask, True, "advanced_smoke", "smoke", "heavy smoke billow",
        2.0, 35.0, 0.9, True,
        json.dumps({"target_id": "advanced_smoke", "generated_clip_path": "cache/smoke.mp4", "atmospheric_motion_mode": "cached_clip"}),
    )
    assert advanced_smoke["generated_clip_path"] == "cache/smoke.mp4"
    assert advanced_smoke["atmospheric_motion_mode"] == "cached_clip"
    dim_light = module._lighting_luminance_amount(0.24, 0.02, 0.02, True)
    bright_light = module._lighting_luminance_amount(0.24, 0.55, 0.1, True)
    assert dim_light < 0.02
    assert bright_light - dim_light > 0.20
    assert module._lighting_glow_amount(0.5, 0.35, 0.1, True) > 0.15

    smoke_rows = np.arange(40, dtype=np.float32)[:, None]
    smoke_columns = np.arange(56, dtype=np.float32)[None, :]
    smoke_texture = 76.0 + 22.0 * np.sin(smoke_columns * 0.23 + smoke_rows * 0.09) + 14.0 * np.cos(smoke_rows * 0.31)
    smoke_pixels = np.repeat(smoke_texture[..., None], 3, axis=2).astype(np.float32)
    soft_alpha = np.full((40, 56, 1), 0.28, dtype=np.float32)
    rows = np.arange(40, dtype=np.float32)[:, None, None]
    columns = np.arange(56, dtype=np.float32)[None, :, None]
    first = module._non_geometric_atmospheric_billow(
        smoke_pixels, soft_alpha, rows, columns, 0.0, 0.4, 12.0, 1.6,
    )
    second = module._non_geometric_atmospheric_billow(
        smoke_pixels, soft_alpha, rows, columns, 1.5, 0.4, 12.0, 1.6,
    )
    # Simulate the renderer's one and only soft-mask composite.
    first_composite = smoke_pixels * (1.0 - soft_alpha) + first * soft_alpha
    second_composite = smoke_pixels * (1.0 - soft_alpha) + second * soft_alpha
    assert float(np.mean(np.abs(second_composite - first_composite))) > 0.45
    # Texture moves, but the fallback must not brighten the whole smoke region
    # into the former glowing white overlay.
    assert abs(float(np.mean(first_composite)) - float(np.mean(smoke_pixels))) < 2.0
    source_frame = np.zeros((54, 96, 3), dtype=np.float32)
    source_frame[:, :48, 0] = 230.0
    source_frame[8:44, 58:88, 1] = 180.0
    matching_frame = np.roll(source_frame, 1, axis=1)
    wrong_frame = np.flip(source_frame, axis=1).copy()
    assert module._motion_source_similarity(source_frame, matching_frame) > 0.90
    assert module._motion_source_similarity(source_frame, wrong_frame) < 0.45
    renderer_source = MODULE_PATH.read_text(encoding="utf-8")
    assert "required cached motion clip is unusable" in renderer_source
    assert "atmospheric motion mode requires a cached clip" in renderer_source

    # Exercise the actual renderer planning path: an explicitly required cached
    # atmosphere clip must fail closed instead of silently becoming procedural.
    renderer_inputs = module.InfraChoirVisualizerDualTrack.INPUT_TYPES()["required"]
    renderer_values = {}
    for name, specification in renderer_inputs.items():
        choices = specification[0]
        metadata = specification[1] if len(specification) > 1 and isinstance(specification[1], dict) else {}
        renderer_values[name] = metadata.get("default", choices[0] if isinstance(choices, list) else None)
    strict_cached_target = dict(configured_smoke)
    strict_cached_target.update({
        "atmospheric_motion_mode": "cached_clip",
        "generated_clip_path": "",
    })
    renderer_values.update({
        "image": image,
        "audio": audio,
        "targets": (strict_cached_target,),
        "delivery_resolution": "source",
        "enhancements_enabled": True,
        "eq_enabled": False,
        "title_card_enabled": False,
        "apply_brand_logo": False,
        "apply_wordmark": False,
    })
    fake_render_paths = types.SimpleNamespace()
    previous_render_paths = sys.modules.get("folder_paths")
    sys.modules["folder_paths"] = fake_render_paths
    try:
        try:
            module.InfraChoirVisualizerDualTrack().render(**renderer_values)
        except ValueError as exc:
            assert "requires a cached clip" in str(exc)
        else:
            raise AssertionError("Explicit cached-clip mode silently fell back instead of failing closed")
    finally:
        if previous_render_paths is None:
            sys.modules.pop("folder_paths", None)
        else:
            sys.modules["folder_paths"] = previous_render_paths

    with tempfile.TemporaryDirectory(prefix="infra-choir-manifest-test-") as temporary:
        fake_paths = types.SimpleNamespace(get_user_directory=lambda: temporary)
        previous = sys.modules.get("folder_paths")
        sys.modules["folder_paths"] = fake_paths
        try:
            identity = module._image_identity(image)
            target = module._auto_target_settings("atmosphere")
            target.update({
                "stable_id": "auto_atmosphere_test", "target_id": "auto_atmosphere_test",
                "object_class": "atmosphere", "review_state": "approved", "enabled": True,
                "mask_png_base64": encoded,
            })
            manifest = json.dumps({"version": 1, "image": identity, "targets": [target]})
            applied = module.InfraChoirAutoDiscover().run(
                image, "Primary: lights + reflections + smoke/fog/flame", 8,
                "apply_reviewed_manifest", "infra_choir/test.json", manifest, True,
            )
            assert "APPLIED" in applied["result"][2]
            assert applied["ui"]["images"] and applied["ui"]["infra_choir_setup"][0]["manifest"]
            smoke_target = module._auto_target_settings("smoke")
            assert smoke_target["motion_type"] == "billow"
            assert smoke_target["envelope_group"] == "smoke"
            assert smoke_target["off_beat_motion"] >= 0.9
            light_contract = module._enforce_auto_target_behavior({
                "provenance": "auto_discovery", "object_class": "light_source",
                "motion_type": "drift", "off_beat_motion": 1.5, "on_beat_motion": 1.0,
            })
            assert light_contract["motion_type"] == "still"
            assert light_contract["off_beat_motion"] == light_contract["on_beat_motion"] == 0.0
            assert light_contract["on_beat_flicker"] >= 1.60
            assert light_contract["max_luminance_change"] >= 0.45
            assert light_contract["audio_driver"] == "beat"
            assert light_contract["response_min"] == 0.0
            assert light_contract["response_attack_ms"] <= 35.0
            flame_contract = module._enforce_auto_target_behavior({
                "provenance": "auto_discovery", "object_class": "flame",
                "motion_type": "sway", "off_beat_motion": 1.0,
            })
            assert flame_contract["motion_type"] == "still"
            assert flame_contract["off_beat_motion"] == 0.0
            assert flame_contract["on_beat_flicker"] >= 1.5
            person_contract = module._enforce_auto_target_behavior({
                "provenance": "auto_discovery", "object_class": "person",
                "motion_type": "sway", "off_beat_motion": 1.0, "on_beat_flicker": 1.0,
            })
            assert person_contract["motion_type"] == "still"
            assert person_contract["off_beat_motion"] == person_contract["on_beat_flicker"] == 0.0
            assert module._enforce_auto_target_behavior({
                "provenance": "auto_discovery", "object_class": "hair", "motion_type": "sway",
            })["motion_type"] == "still"
            protected = torch.zeros_like(mask)
            protected[9:14, 13:18] = 1.0
            guarded = module._subtract_protected_mask(mask, protected, 0.0)
            assert float(guarded[9:14, 13:18].max()) == 0.0
            assert float(guarded[5:7, 9:11].min()) == 1.0
            expanded_motion = module._procedural_motion_pixels("billow", 1080, 300)
            assert 16.0 < expanded_motion <= 30.0
            light_mask = np.zeros((24, 32), dtype=np.float32)
            light_mask[7:12, 12:17] = 1.0
            smoke_mask = np.zeros((24, 32), dtype=np.float32)
            smoke_mask[4:18, 8:24] = 1.0
            plans = [
                {
                    "provenance": "auto_discovery", "object_class": "light_source",
                    "motion_type": "still", "source_layer": module._Layer(light_mask, (12, 7, 17, 12)),
                    "layer": module._Layer(light_mask.copy(), (12, 7, 17, 12)), "motion_mask": light_mask.copy(),
                },
                {
                    "provenance": "auto_discovery", "object_class": "smoke", "target_id": "smoke_test",
                    "motion_type": "billow", "source_layer": module._Layer(smoke_mask, (8, 4, 24, 18)),
                    "layer": module._Layer(smoke_mask.copy(), (8, 4, 24, 18)), "motion_mask": smoke_mask.copy(),
                },
            ]
            overlap_reports = module._protect_auto_motion_overlaps(plans)
            assert overlap_reports and "protected" in overlap_reports[0]
            assert float(plans[1]["motion_mask"][7:12, 12:17].max()) == 0.0
            assert float(plans[1]["layer"].mask[7:12, 12:17].max()) == 0.0
            texture_y = np.arange(24, dtype=np.float32)[:, None]
            texture_x = np.arange(32, dtype=np.float32)[None, :]
            billow_luma = 68.0 + 20.0 * np.sin(texture_x * 0.38 + texture_y * 0.17) + 9.0 * np.cos(texture_y * 0.51)
            billow_source = np.repeat(billow_luma[..., None], 3, axis=2).astype(np.float32)
            billow_alpha = np.zeros((24, 32, 1), dtype=np.float32)
            billow_alpha[5:19, 9:23] = 1.0
            billow_rows = np.arange(24, dtype=np.float32)[:, None, None]
            billow_columns = np.arange(32, dtype=np.float32)[None, :, None]
            billowed = module._non_geometric_atmospheric_billow(
                billow_source, billow_alpha, billow_rows, billow_columns, 1.0, 0.5, 18.0,
            )
            assert np.array_equal(billowed[:5], billow_source[:5])
            assert abs(float(np.mean(billowed[6:18, 10:22])) - float(np.mean(billow_source[6:18, 10:22]))) < 6.0
            assert float(np.std(billowed[6:18, 10:22])) > 5.0
            later_billow = module._non_geometric_atmospheric_billow(
                billow_source, billow_alpha, billow_rows, billow_columns, 3.0, 0.5, 18.0,
            )
            assert float(np.mean(np.abs(billowed[6:18, 10:22] - later_billow[6:18, 10:22]))) > 0.5
            proposed = dict(smoke_target)
            proposed.update({
                "stable_id": "auto_smoke_test", "target_id": "auto_smoke_test",
                "object_class": "smoke", "mask_png_base64": encoded,
            })
            pushed, pushed_text, pushed_path = module.approve_infra_choir_discovery(
                json.dumps({"version": 1, "image": identity, "targets": [proposed]}),
                "infra_choir/one_click.json", False,
            )
            assert pushed_path.is_file() and json.loads(pushed_text)["targets"][0]["enabled"] is True
            assert pushed["targets"][0]["review_state"] == "approved"
            assert pushed["targets"][0]["mask_verified"] is True
            idle = module.InfraChoirAutoDiscover().run(
                image, "Primary: lights + reflections + smoke/fog/flame", 8,
                "idle", "infra_choir/test.json", "", True,
            )
            assert "safety no-op" in idle["result"][2]
            assert "images" not in idle["ui"]
            loaded, status = module.InfraChoirApprovedTargets().load(image, "infra_choir/test.json", True, "empty")
            assert len(loaded) == 1 and "loaded 1" in status
            stale = image.clone()
            stale[:, 0, 0, :] = 1.0
            empty, status = module.InfraChoirApprovedTargets().load(stale, "infra_choir/test.json", True, "empty")
            assert empty == () and "fingerprint mismatch" in status
        finally:
            if previous is None:
                sys.modules.pop("folder_paths", None)
            else:
                sys.modules["folder_paths"] = previous

    manual = {"target_id": "manual_smoke", "object_class": "atmosphere", "mask": mask}
    automatic = dict(loaded[0])
    merged, report = module.InfraChoirTargetMerge().merge((manual,), (automatic,), "manual_wins", 0.45)
    assert merged == (manual,) and "dropped 1" in report
    merged, _ = module.InfraChoirTargetMerge().merge((manual,), (automatic,), "auto_only", 0.45)
    assert merged == (automatic,)

    print("Infra Choir dual-track workflow, manifest, merge, title/EQ schema, and ultra-band tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
