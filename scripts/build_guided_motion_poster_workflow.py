from __future__ import annotations

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "user/default/workflows/video_wan2_2_14B_s2v_motion_loop.json"
TARGET = ROOT / "user/default/workflows/video_wan2_2_14B_s2v_motion_poster_guided.json"

DEFAULT_POSITIVE_PROMPT = (
    "Background motion only. Hair moves gently as if blown by a light wind. "
    "Smoke billows slowly in the background. Street and neon lights flicker "
    "intermittently. Preserve the subject's identity, face, expression, lips, "
    "mouth position, pose, framing, clothing, and the original composition. "
    "Restrained, physically plausible motion with seamless-loop-friendly pacing."
)
DEFAULT_NEGATIVE_PROMPT = (
    "lip sync, lips moving, mouth movement, singing, talking, speech, changing "
    "expression, blinking to the beat, face deformation, identity drift, body "
    "movement, dancing, camera shake, rapid zoom, scene change, new objects, "
    "warping, morphing, whole-image pulsing, exaggerated motion"
)


def input_slot(name, data_type, link=None, *, widget=False, shape=None):
    value = {"name": name, "type": data_type, "link": link}
    if widget:
        value["widget"] = {"name": name}
    if shape is not None:
        value["shape"] = shape
    return value


def output_slot(name, data_type, *, slot_index=None):
    value = {"name": name, "type": data_type, "links": None}
    if slot_index is not None:
        value["slot_index"] = slot_index
    return value


def rebuild_links(workflow: dict) -> None:
    nodes = {node["id"]: node for node in workflow["nodes"]}
    for node in workflow["nodes"]:
        for item in node.get("inputs", []):
            item["link"] = None
        for item in node.get("outputs", []):
            item["links"] = None
    for link_id, origin_id, origin_slot, target_id, target_slot, _ in workflow["links"]:
        origin = nodes.get(origin_id)
        target = nodes.get(target_id)
        if origin is None or target is None:
            raise RuntimeError(f"broken link {link_id}: {origin_id} -> {target_id}")
        if origin_slot >= len(origin.get("outputs", [])):
            raise RuntimeError(f"invalid origin slot on link {link_id}")
        if target_slot >= len(target.get("inputs", [])):
            raise RuntimeError(f"invalid target slot on link {link_id}")
        links = origin["outputs"][origin_slot].get("links")
        origin["outputs"][origin_slot]["links"] = (links or []) + [link_id]
        target["inputs"][target_slot]["link"] = link_id


def keep_ancestors(workflow: dict, roots: set[int]) -> None:
    """Drop unrelated example graphs while retaining every dependency of roots."""
    required = set(roots)
    changed = True
    while changed:
        changed = False
        for _, origin_id, _, target_id, _, _ in workflow["links"]:
            if target_id in required and origin_id not in required:
                required.add(origin_id)
                changed = True
    workflow["nodes"] = [node for node in workflow["nodes"] if node["id"] in required]
    workflow["links"] = [
        link
        for link in workflow["links"]
        if link[1] in required and link[3] in required
    ]


def prune_unused_layout(workflow: dict) -> None:
    def group_has_node(group: dict) -> bool:
        left, top, width, height = group["bounding"]
        return any(
            left <= node["pos"][0] <= left + width
            and top <= node["pos"][1] <= top + height
            for node in workflow["nodes"]
        )

    workflow["groups"] = [
        group for group in workflow.get("groups", []) if group_has_node(group)
    ]

    definitions = workflow.get("definitions", {}).get("subgraphs", [])
    definitions_by_id = {definition["id"]: definition for definition in definitions}
    needed = {node["type"] for node in workflow["nodes"]}
    pending = list(needed)
    while pending:
        definition = definitions_by_id.get(pending.pop())
        if definition is None:
            continue
        for node in definition.get("nodes", []):
            if node["type"] not in needed:
                needed.add(node["type"])
                pending.append(node["type"])
    workflow.setdefault("definitions", {})["subgraphs"] = [
        definition for definition in definitions if definition["id"] in needed
    ]


def main() -> int:
    workflow = json.loads(SOURCE.read_text(encoding="utf-8"))
    # Node 96 is the decoded first/continuation sequence from the curated
    # 832x480 graph. The source JSON also contains a disconnected square
    # example; retaining only node 96's ancestors prevents that graph from
    # exposing duplicate media pickers or executing accidentally.
    keep_ancestors(workflow, {96, 58})
    nodes_by_id = {node["id"]: node for node in workflow["nodes"]}
    nodes_by_id[58]["widgets_values"][0] = "Last Call for the Shareholders.mp3"
    nodes_by_id[58]["widgets_values_named"]["audio"] = (
        "Last Call for the Shareholders.mp3"
    )
    nodes_by_id[58]["title"] = "Load Song"
    for node_id, label in (
        (6, "Positive conditioning — edit in green guidance node"),
        (7, "Negative conditioning — edit in green guidance node"),
    ):
        nodes_by_id[node_id]["flags"] = {"collapsed": True}
        nodes_by_id[node_id]["title"] = label

    next_node = max(node["id"] for node in workflow["nodes"])
    guidance_id = next_node + 1
    seeds_id = next_node + 2
    assemble_id = next_node + 3
    note_id = next_node + 4
    logo_id = next_node + 5
    wordmark_id = next_node + 6
    next_link = max(link[0] for link in workflow["links"])

    guidance = {
        "id": guidance_id,
        "type": "MotionPosterGuidance",
        "pos": [330, -650],
        "size": [640, 580],
        "flags": {},
        "order": 31,
        "mode": 0,
        "inputs": [
            input_slot("positive_prompt", "STRING", widget=True),
            input_slot("negative_prompt", "STRING", widget=True),
            input_slot("allow_lip_motion", "BOOLEAN", widget=True),
            input_slot("lyrics_or_theme_context", "STRING", widget=True),
        ],
        "outputs": [
            output_slot("positive_prompt", "STRING", slot_index=0),
            output_slot("negative_prompt", "STRING", slot_index=1),
        ],
        "properties": {"Node name for S&R": "MotionPosterGuidance"},
        "widgets_values": [
            DEFAULT_POSITIVE_PROMPT,
            DEFAULT_NEGATIVE_PROMPT,
            False,
            "",
        ],
        "widgets_values_named": {
            "positive_prompt": DEFAULT_POSITIVE_PROMPT,
            "negative_prompt": DEFAULT_NEGATIVE_PROMPT,
            "allow_lip_motion": False,
            "lyrics_or_theme_context": "",
        },
        "title": "1. Edit positive and negative prompts",
        "color": "#243",
        "bgcolor": "#354",
    }
    seeds = {
        "id": seeds_id,
        "type": "MotionPosterSeedPlan",
        "pos": [1010, -650],
        "size": [300, 130],
        "flags": {},
        "order": 32,
        "mode": 0,
        "inputs": [
            input_slot("variant_count", "INT", widget=True),
            input_slot("base_seed", "INT", widget=True),
        ],
        "outputs": [
            output_slot("initial_seeds", "INT", slot_index=0),
            output_slot("extension_seeds", "INT", slot_index=1),
        ],
        "properties": {"Node name for S&R": "MotionPosterSeedPlan"},
        "widgets_values": [1, 20261001, "randomize"],
        "widgets_values_named": {
            "variant_count": 1,
            "base_seed": 20261001,
            "control_after_generate": "randomize",
        },
        "title": "2. Choose 1–3 variants",
        "color": "#243",
        "bgcolor": "#354",
    }
    assemble = {
        "id": assemble_id,
        "type": "MotionPosterAssemble",
        "pos": [1350, -650],
        "size": [560, 680],
        "flags": {},
        "order": 60,
        "mode": 0,
        "inputs": [
            input_slot("loop_images", "IMAGE"),
            input_slot("audio", "AUDIO"),
            input_slot("brand_logo", "IMAGE"),
            input_slot("brand_logo_mask", "MASK"),
            input_slot("wordmark", "IMAGE"),
            input_slot("wordmark_mask", "MASK"),
            input_slot("apply_brand_logo", "BOOLEAN", widget=True),
            input_slot("brand_logo_width_percent", "FLOAT", widget=True),
            input_slot("brand_logo_opacity", "FLOAT", widget=True),
            input_slot("brand_logo_margin_px", "INT", widget=True),
            input_slot("apply_wordmark", "BOOLEAN", widget=True),
            input_slot("wordmark_width_percent", "FLOAT", widget=True),
            input_slot("wordmark_opacity", "FLOAT", widget=True),
            input_slot("wordmark_margin_px", "INT", widget=True),
            input_slot("song_name", "STRING", widget=True),
            input_slot("fps", "INT", widget=True),
            input_slot("reversal_crossfade_seconds", "FLOAT", widget=True),
            input_slot("variant_crossfade_seconds", "FLOAT", widget=True),
            input_slot("camera_zoom", "FLOAT", widget=True),
            input_slot("horizontal_drift_px", "FLOAT", widget=True),
            input_slot("vertical_drift_px", "FLOAT", widget=True),
            input_slot("output_prefix", "STRING", widget=True),
        ],
        "outputs": [output_slot("output_path", "STRING", slot_index=0)],
        "properties": {"Node name for S&R": "MotionPosterAssemble"},
        "widgets_values": [
            False, 12.0, 0.72, 16,
            False, 35.0, 0.95, 20,
            "Last Call for the Shareholders",
            16, 0.5, 1.0, 1.0, 0.0, 0.0,
            "motion_poster/guided_motion_poster",
        ],
        "widgets_values_named": {
            "apply_brand_logo": False,
            "brand_logo_width_percent": 12.0,
            "brand_logo_opacity": 0.72,
            "brand_logo_margin_px": 16,
            "apply_wordmark": False,
            "wordmark_width_percent": 35.0,
            "wordmark_opacity": 0.95,
            "wordmark_margin_px": 20,
            "song_name": "Last Call for the Shareholders",
            "fps": 16,
            "reversal_crossfade_seconds": 0.5,
            "variant_crossfade_seconds": 1.0,
            "camera_zoom": 1.0,
            "horizontal_drift_px": 0.0,
            "vertical_drift_px": 0.0,
            "output_prefix": "motion_poster/guided_motion_poster",
        },
        "title": "3. Assemble and save full song",
        "color": "#243",
        "bgcolor": "#354",
    }
    note = {
        "id": note_id,
        "type": "Note",
        "pos": [-90, -650],
        "size": [380, 430],
        "flags": {},
        "order": 5,
        "mode": 0,
        "inputs": [],
        "outputs": [],
        "properties": {},
        "widgets_values": [
            "# Guided motion poster\n\n"
            "1. Select the **Load Image** and **Load Song** inputs.\n"
            "2. Edit the positive and negative prompts in the green guidance node. Leave lip motion off unless deliberately testing it.\n"
            "3. Choose 1–3 variants. The base seed randomizes after each run unless you select fixed. Three variants give more variety but take roughly three times as long.\n"
            "4. Camera zoom `1.0` means no zoom; drift defaults to zero. Set the song-title field when changing audio; it starts the output filename.\n"
            "5. Optional branding is applied after generation: the logo sits subtly at lower right and the wordmark appears at upper left. Enable either independently.\n"
            "6. Queue once. The graph generates the variants sequentially, closes their loop seams, crossfades them, repeats them to the complete audio duration, and saves one final MP4.\n\n"
            "The normal path requires no manifest edits and no command-line rendering."
        ],
        "widgets_values_named": {"text": "Guided motion-poster instructions."},
        "title": "Start here",
        "color": "#223",
        "bgcolor": "#335",
    }
    logo = copy.deepcopy(nodes_by_id[52])
    logo.update(
        {
            "id": logo_id,
            "pos": [1950, -650],
            "title": "Optional Brand Logo — lower right",
            "order": 28,
            "widgets_values": ["TWS-Logo.png", "image"],
            "widgets_values_named": {"image": "TWS-Logo.png"},
        }
    )
    wordmark = copy.deepcopy(nodes_by_id[52])
    wordmark.update(
        {
            "id": wordmark_id,
            "pos": [2310, -650],
            "title": "Optional Wordmark — upper left",
            "order": 29,
            "widgets_values": ["TWS-Logo.png", "image"],
            "widgets_values_named": {"image": "TWS-Logo.png"},
        }
    )
    workflow["nodes"].extend([guidance, seeds, assemble, note, logo, wordmark])

    def add_link(origin, origin_slot, target, target_slot, data_type):
        nonlocal next_link
        next_link += 1
        workflow["links"].append(
            [next_link, origin, origin_slot, target, target_slot, data_type]
        )

    add_link(guidance_id, 0, 6, 1, "STRING")
    add_link(guidance_id, 1, 7, 1, "STRING")
    add_link(seeds_id, 0, 3, 4, "INT")
    add_link(seeds_id, 1, 79, 8, "INT")
    add_link(96, 0, assemble_id, 0, "IMAGE")
    add_link(58, 0, assemble_id, 1, "AUDIO")
    add_link(logo_id, 0, assemble_id, 2, "IMAGE")
    add_link(logo_id, 1, assemble_id, 3, "MASK")
    add_link(wordmark_id, 0, assemble_id, 4, "IMAGE")
    add_link(wordmark_id, 1, assemble_id, 5, "MASK")

    workflow["last_node_id"] = wordmark_id
    workflow["last_link_id"] = next_link
    workflow["revision"] = int(workflow.get("revision", 0)) + 1
    workflow.setdefault("state", {})["lastNodeId"] = wordmark_id
    workflow["state"]["lastLinkId"] = next_link
    prune_unused_layout(workflow)
    workflow["state"]["lastGroupId"] = max(
        (group["id"] for group in workflow["groups"]), default=0
    )
    workflow["extra"]["ds"] = {"scale": 0.58, "offset": [230, 500]}
    rebuild_links(workflow)
    load_types = [
        node["type"]
        for node in workflow["nodes"]
        if node["type"] in {"LoadImage", "LoadAudio"}
    ]
    if (
        load_types.count("LoadImage") != 3
        or load_types.count("LoadAudio") != 1
    ):
        raise RuntimeError(f"guided workflow must expose one image and audio loader: {load_types}")
    if any(group["bounding"][1] >= 1600 for group in workflow["groups"]):
        raise RuntimeError("stale lower-canvas workflow groups remain")
    if len(workflow["definitions"]["subgraphs"]) != 1:
        raise RuntimeError("unused subgraph definitions remain")
    if assemble["inputs"][14].get("widget", {}).get("name") != "song_name":
        raise RuntimeError("assembler song-title field is missing")
    TARGET.write_text(
        json.dumps(workflow, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
        newline="\n",
    )
    print(TARGET)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
