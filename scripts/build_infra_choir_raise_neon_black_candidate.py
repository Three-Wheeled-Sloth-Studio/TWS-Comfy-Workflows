from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "user/default/workflows/video_wan2_2_14B_s2v_motion_loop.json"
TARGET = ROOT / "user/default/workflows/video_wan2_2_14B_s2v_raise_the_neon_black_candidate_v1.json"

SOURCE_IMAGE = "infra_choir/raise_the_neon_black/Banner.png"
# The supplied production master is 192 kHz. Comfy's SaveVideo selects AAC,
# which cannot mux 192 kHz audio, so the workflow uses a lossless 48 kHz
# working copy while the original master remains untouched.
SOURCE_AUDIO = "infra_choir/raise_the_neon_black/Raise the Neon Black_48k.flac"
OUTPUT_PREFIX = "infra_choir/motion_assets/raise_the_neon_black_environment_candidate_v1"

POSITIVE = (
    "Locked camera, unchanged composition, stable character identity, restrained cinematic environmental animation. "
    "Animate the existing heavy smoke, sea fog, storm mist, and low clouds with ample visible volume: broad banks "
    "billow, curl, roll, and evolve continuously around the moon, cranes, harbor structures, and waterline. "
    "The lead woman's existing red hair and braid stream and flutter naturally in a strong sea breeze while her face, "
    "head, raised arm, hands, torso, and pose remain fixed. The large torn black flag and the smaller existing harbor "
    "flags ripple and snap in the same wind without changing shape or attachment points. Existing ocean waves travel, "
    "ripple, crest, and produce subtle foam; reflections follow the water surface. The existing tentacles visible below "
    "the water wriggle slowly and independently beneath the surface without growing or emerging. Rain streaks fall and "
    "distant atmosphere shifts subtly. Other secondary environmental motion may be gentle and coherent, never dominant. "
    "Keep practical lights and exposure stable for later music-synchronized procedural glow. Seamless-loop-friendly pacing."
)

NEGATIVE = (
    "camera movement, camera shake, pan, tilt, zoom, dolly, perspective shift, scene cut, composition change, global "
    "warping, rubber sheet distortion, whole-image pulsing, global brightness flicker, exposure pumping, face movement, "
    "head movement, body movement, arm movement, hand movement, pose change, lip sync, mouth movement, talking, singing, "
    "blinking, expression change, face deformation, identity drift, new face, extra person, duplicate person, crowd "
    "movement, moving cranes, bending buildings, moving dock, moving chains, geometry drift, new flag, disappearing flag, "
    "new tentacle, tentacles above water, giant creature emerging, altered costume, new object, disappearing object, text, "
    "caption, logo, watermark, overwhelming motion, frantic motion"
)


def _set_widget(node: dict, index: int, name: str, value) -> None:
    node.setdefault("widgets_values", [])[index] = value
    node.setdefault("widgets_values_named", {})[name] = value


def build() -> Path:
    source_bytes = SOURCE.read_bytes()
    workflow = json.loads(source_bytes.decode("utf-8"))
    nodes = {int(node["id"]): node for node in workflow["nodes"]}

    _set_widget(nodes[52], 0, "image", SOURCE_IMAGE)
    _set_widget(nodes[58], 0, "audio", SOURCE_AUDIO)
    _set_widget(nodes[6], 0, "text", POSITIVE)
    _set_widget(nodes[7], 0, "text", NEGATIVE)
    _set_widget(nodes[3], 0, "seed", 20261021)
    _set_widget(nodes[3], 1, "control_after_generate", "fixed")
    _set_widget(nodes[79], 0, "seed", 20261022)
    _set_widget(nodes[93], 0, "width", 1024)
    _set_widget(nodes[93], 1, "height", 576)
    _set_widget(nodes[113], 0, "filename_prefix", OUTPUT_PREFIX)

    instruction = (
        "RAISE THE NEON BLACK — ENVIRONMENT CANDIDATE V1\n\n"
        "Queue once to create one reproducible short Wan motion asset from the explicitly supplied Banner.png and FLAC. "
        "Review smoke/fog volume, lead hair, flags, waves, underwater tentacles, camera/identity stability, and whether "
        "secondary motion stays restrained. Lighting is deliberately stable so procedural music-synced glow and the title "
        "card can be layered later. This workflow does not modify the dual-track scaffold."
    )
    nodes[182]["title"] = "Review gate — Raise the Neon Black environment candidate"
    _set_widget(nodes[182], 0, "text", instruction)

    workflow["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "tws:infra-choir:raise-the-neon-black:environment-candidate:v1"))
    workflow["revision"] = 0
    workflow.setdefault("extra", {})["infra_choir_motion_candidate"] = {
        "version": 1,
        "source_workflow": SOURCE.name,
        "source_workflow_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_image": SOURCE_IMAGE,
        "source_audio": SOURCE_AUDIO,
        "purpose": "One Wan full-scene environmental-motion candidate for later hybrid compositing.",
        "requested_motion": ["smoke_fog", "lead_hair", "waves", "flags", "underwater_tentacles"],
        "deferred_layers": ["music_synced_lighting_glow", "title_card"],
        "review_required": True,
        "expected_output_prefix": OUTPUT_PREFIX,
    }

    assert nodes[93]["widgets_values_named"] == {"width": 1024, "height": 576, "length": 77, "batch_size": 1}
    assert nodes[103]["widgets_values_named"]["value"] == 4
    assert nodes[105]["widgets_values_named"]["value"] == 1
    assert nodes[113]["mode"] == 0
    assert all(nodes[node_id]["mode"] == 4 for node_id in (147, 148, 149, 150, 151, 152, 153))

    TARGET.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return TARGET


if __name__ == "__main__":
    print(build())
