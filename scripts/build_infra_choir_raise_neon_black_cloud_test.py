from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "user/default/workflows/video_wan2_2_14B_s2v_raise_the_neon_black_candidate_v1.json"
TARGET = ROOT / "user/default/workflows/video_wan2_2_14B_s2v_raise_the_neon_black_cloud_smoke_cheap_v1.json"
OUTPUT_PREFIX = "infra_choir/motion_assets/raise_the_neon_black_cloud_smoke_cheap_v1"

POSITIVE = (
    "Locked camera and unchanged composition. Make the existing storm atmosphere unmistakably active. Huge dark cloud "
    "banks around the moon roll, churn, fold, and boil continuously with large slow vortices and visible depth. Thick "
    "volumetric sea fog and smoke surge across the harbor waterline and between the cranes in broad independently moving "
    "plumes, with dense cores, soft translucent edges, curls, and billowing volume. This cloud, smoke, and fog motion is "
    "the primary action and must be clearly visible throughout the shot. Preserve the lead woman's face, head, raised arm, "
    "hands, body, and identity. Her existing red hair may stream naturally in the wind; existing flags may wave and existing "
    "water may ripple, but those are secondary. Keep underwater tentacles subtle. Keep cranes, buildings, docks, crowd, and "
    "camera fixed. Stable practical lights and exposure for later music-synchronized procedural glow. Restrained cinematic "
    "motion outside the atmosphere, no scene transformation."
)

NEGATIVE = (
    "weak fog, static clouds, barely moving haze, flat haze overlay, glowing translucent veil, camera movement, camera shake, "
    "pan, tilt, zoom, dolly, perspective shift, scene cut, global warping, rubber sheet distortion, whole-image pulsing, "
    "global brightness flicker, exposure pumping, face movement, head movement, body movement, arm movement, hand movement, "
    "pose change, lip sync, mouth movement, blinking, expression change, face deformation, identity drift, new face, extra "
    "person, crowd movement, moving cranes, bending buildings, moving dock, geometry drift, new object, disappearing object, "
    "tentacles above water, giant creature emerging, text, caption, logo, watermark, frantic non-atmospheric motion"
)


def _set_widget(node: dict, index: int, name: str, value) -> None:
    node.setdefault("widgets_values", [])[index] = value
    node.setdefault("widgets_values_named", {})[name] = value


def _disconnect(workflow: dict, removed_link_ids: set[int]) -> None:
    workflow["links"] = [link for link in workflow["links"] if int(link[0]) not in removed_link_ids]
    for node in workflow["nodes"]:
        for item in node.get("inputs", []):
            if item.get("link") in removed_link_ids:
                item["link"] = None
        for item in node.get("outputs", []):
            links = item.get("links")
            if links is not None:
                item["links"] = [link for link in links if link not in removed_link_ids] or None


def build() -> Path:
    source_bytes = SOURCE.read_bytes()
    workflow = json.loads(source_bytes.decode("utf-8"))
    nodes = {int(node["id"]): node for node in workflow["nodes"]}

    _set_widget(nodes[6], 0, "text", POSITIVE)
    _set_widget(nodes[7], 0, "text", NEGATIVE)
    _set_widget(nodes[3], 0, "seed", 20261024)
    _set_widget(nodes[3], 1, "control_after_generate", "fixed")
    _set_widget(nodes[93], 0, "width", 640)
    _set_widget(nodes[93], 1, "height", 360)
    _set_widget(nodes[93], 2, "length", 49)
    _set_widget(nodes[104], 0, "value", 49)
    _set_widget(nodes[113], 0, "filename_prefix", OUTPUT_PREFIX)

    # Cheap gate: generate and decode only the initial segment. The extension,
    # cut, and concatenation nodes remain visible for provenance but are muted.
    removed = {int(link[0]) for link in workflow["links"] if int(link[1]) in {79, 94, 95} or int(link[3]) in {79, 94, 95}}
    _disconnect(workflow, removed)
    for node_id in (79, 94, 95):
        nodes[node_id]["mode"] = 4
    direct_link_id = max(int(link[0]) for link in workflow["links"]) + 1
    workflow["links"].append([direct_link_id, 3, 0, 80, 0, "LATENT"])
    nodes[3]["outputs"][0]["links"] = [direct_link_id]
    nodes[80]["inputs"][0]["link"] = direct_link_id
    nodes[104]["outputs"][0]["links"] = [335]
    workflow["last_link_id"] = direct_link_id
    workflow.setdefault("state", {})["lastLinkId"] = direct_link_id

    instruction = (
        "RAISE THE NEON BLACK — CHEAP CLOUD/SMOKE GATE V1\n\n"
        "One 640x360, 49-frame, fixed-seed segment only. Cloud, smoke, and fog are the primary action. Review atmospheric "
        "volume and motion plus face/camera/geometry stability. Do not judge final detail or title/EQ/lighting from this proof."
    )
    nodes[182]["title"] = "Cheap gate — stronger cloud, smoke, and fog"
    _set_widget(nodes[182], 0, "text", instruction)

    workflow["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "tws:infra-choir:raise-the-neon-black:cloud-smoke-cheap:v1"))
    workflow["revision"] = 0
    workflow.setdefault("extra", {})["infra_choir_motion_candidate"] = {
        "version": 1,
        "source_workflow": SOURCE.name,
        "source_workflow_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_image": "infra_choir/raise_the_neon_black/Banner.png",
        "source_audio": "infra_choir/raise_the_neon_black/Raise the Neon Black_48k.flac",
        "purpose": "Cheap single-segment gate for stronger cloud, smoke, and fog motion.",
        "resolution": [640, 360],
        "length": 49,
        "extension_enabled": False,
        "review_required": True,
        "expected_output_prefix": OUTPUT_PREFIX,
    }

    assert nodes[93]["widgets_values_named"] == {"width": 640, "height": 360, "length": 49, "batch_size": 1}
    assert nodes[58]["widgets_values_named"]["audio"].endswith("Raise the Neon Black_48k.flac")
    assert nodes[79]["mode"] == nodes[94]["mode"] == nodes[95]["mode"] == 4
    assert nodes[80]["inputs"][0]["link"] == direct_link_id
    assert nodes[113]["mode"] == 0

    TARGET.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return TARGET


if __name__ == "__main__":
    print(build())
