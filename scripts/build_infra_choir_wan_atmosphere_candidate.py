from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "user/default/workflows/video_wan2_2_14B_s2v_motion_loop.json"
TARGET = ROOT / "user/default/workflows/video_wan2_2_14B_s2v_infra_choir_atmosphere_candidate_v1.json"

POSITIVE = (
    "Locked camera and unchanged composition. Animate the existing smoke as thick, voluminous, "
    "slowly rising turbulent plumes with evolving curls, folds, density, and soft translucent edges. "
    "The cigarette smoke and the larger smoke cloud near the piano billow independently and naturally. "
    "Allow subtle atmospheric depth in the room, but keep every person, face, head, body, hand, piano, "
    "lamp, chandelier, building, furniture edge, and reflection in its original position and identity. "
    "No character performance. Restrained cinematic environmental motion, stable exposure, seamless-loop-friendly pacing."
)

NEGATIVE = (
    "camera movement, camera shake, pan, tilt, zoom, dolly, perspective shift, scene change, global warping, "
    "rubber sheet distortion, whole-image pulsing, global brightness flicker, person movement, head movement, "
    "body movement, hand movement, lip sync, lips moving, mouth movement, talking, singing, blinking, changing expression, "
    "face deformation, identity drift, new face, extra person, duplicate person, new object, disappearing object, "
    "moving chandelier, moving lamp, moving piano, moving buildings, geometry drift, text, watermark"
)


def _set_widget(node: dict, index: int, name: str, value) -> None:
    node.setdefault("widgets_values", [])[index] = value
    node.setdefault("widgets_values_named", {})[name] = value


def build() -> Path:
    source_bytes = SOURCE.read_bytes()
    workflow = json.loads(source_bytes.decode("utf-8"))
    nodes = {int(node["id"]): node for node in workflow["nodes"]}

    _set_widget(nodes[52], 0, "image", "Photo.png")
    _set_widget(nodes[58], 0, "audio", "Static in the Champagne Room.mp3")
    _set_widget(nodes[6], 0, "text", POSITIVE)
    _set_widget(nodes[7], 0, "text", NEGATIVE)
    _set_widget(nodes[3], 0, "seed", 20261019)
    _set_widget(nodes[3], 1, "control_after_generate", "fixed")
    _set_widget(nodes[79], 0, "seed", 20261020)
    _set_widget(nodes[113], 0, "filename_prefix", "infra_choir/motion_assets/jazz_atmosphere_candidate_v1")

    instruction = (
        "INFRA CHOIR ATMOSPHERE CANDIDATE V1\n\n"
        "Queue once to create one reproducible short Wan motion asset from Photo.png. "
        "This workflow does not modify or render the dual-track scaffold. Review the saved clip for smoke quality, "
        "face/geometry stability, and camera drift before connecting it to a hybrid compositor workflow."
    )
    nodes[182]["title"] = "Review gate — generate only one candidate"
    _set_widget(nodes[182], 0, "text", instruction)

    workflow["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "tws:infra-choir:wan-atmosphere-candidate:v1"))
    workflow["revision"] = 0
    workflow.setdefault("extra", {})["infra_choir_motion_candidate"] = {
        "version": 1,
        "source_workflow": SOURCE.name,
        "source_workflow_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_image": "Photo.png",
        "source_audio": "Static in the Champagne Room.mp3",
        "purpose": "One Wan-quality full-scene atmosphere candidate for mask-confined hybrid compositing.",
        "review_required": True,
        "expected_output_prefix": "infra_choir/motion_assets/jazz_atmosphere_candidate_v1",
    }

    assert nodes[93]["widgets_values_named"] == {"width": 832, "height": 480, "length": 77, "batch_size": 1}
    assert nodes[103]["widgets_values_named"]["value"] == 4
    assert nodes[105]["widgets_values_named"]["value"] == 1
    assert nodes[113]["mode"] == 0
    assert all(nodes[node_id]["mode"] == 4 for node_id in (147, 148, 149, 150, 151, 152, 153))

    TARGET.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return TARGET


if __name__ == "__main__":
    print(build())
