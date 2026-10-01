import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "user/default/workflows/video_wan2_2_14B_s2v_auto_duration.json"
TARGET = ROOT / "user/default/workflows/video_wan2_2_14B_s2v_auto_duration_windowed.json"

workflow = json.loads(SOURCE.read_text(encoding="utf-8"))
nodes = {node["id"]: node for node in workflow["nodes"]}

# The template's disabled 20-step alternative has already been omitted from
# this generated workflow; remove its leftover empty group rectangles too.
workflow["groups"] = [
    group
    for group in workflow.get("groups", [])
    if group.get("bounding", [0, 0])[1] < 1600
]

# Default to Wan's practical 16:9 working resolution.
nodes[93]["widgets_values"][0] = 832
nodes[93]["widgets_values"][1] = 480

# Replace the growing GPU latent carried by the loop with a compact CPU state.
nodes[201]["type"] = "WanSoundImageToVideoExtendState"
nodes[201]["title"] = "Extend from 19-frame CPU motion tail"
nodes[201]["properties"] = {"Node name for S&R": "WanSoundImageToVideoExtendState"}
nodes[201]["inputs"] = [
    {"localized_name": "positive", "name": "positive", "type": "CONDITIONING", "link": None},
    {"localized_name": "negative", "name": "negative", "type": "CONDITIONING", "link": None},
    {"localized_name": "vae", "name": "vae", "type": "VAE", "link": None},
    {"localized_name": "length", "name": "length", "type": "INT", "link": None},
    {"localized_name": "state", "name": "state", "type": "WAN_S2V_STATE", "link": None},
    {"localized_name": "audio_encoder_output", "name": "audio_encoder_output", "type": "AUDIO_ENCODER_OUTPUT", "link": None},
    {"localized_name": "ref_image", "name": "ref_image", "type": "IMAGE", "link": None},
    {"localized_name": "control_video", "name": "control_video", "type": "IMAGE", "link": None},
]

nodes[203]["type"] = "WanS2VStateAppend"
nodes[203]["title"] = "Store completed chunk on CPU"
nodes[203]["properties"] = {"Node name for S&R": "WanS2VStateAppend"}
nodes[203]["inputs"] = [
    {"localized_name": "state", "name": "state", "type": "WAN_S2V_STATE", "link": None},
    {"localized_name": "chunk_latent", "name": "chunk_latent", "type": "LATENT", "link": None},
]
nodes[203]["outputs"] = [
    {"localized_name": "state", "name": "state", "type": "WAN_S2V_STATE", "slot_index": 0, "links": None}
]
nodes[203]["widgets_values"] = []
nodes[203]["widgets_values_named"] = {}

# Remove loop links; they are rebuilt below.
loop_node_ids = {198, 199, 200, 201, 202, 203, 204}
workflow["links"] = [
    link
    for link in workflow["links"]
    if not (link[1] in loop_node_ids or link[3] in loop_node_ids)
]

new_nodes = [
    {
        "id": 208,
        "type": "WanS2VStateStart",
        "pos": [1450, 30],
        "size": [290, 70],
        "flags": {},
        "order": 44,
        "mode": 0,
        "inputs": [
            {"localized_name": "initial_latent", "name": "initial_latent", "type": "LATENT", "link": None},
            {"localized_name": "initial_positive", "name": "initial_positive", "type": "CONDITIONING", "link": None},
        ],
        "outputs": [{"localized_name": "state", "name": "state", "type": "WAN_S2V_STATE", "slot_index": 0, "links": None}],
        "properties": {"Node name for S&R": "WanS2VStateStart"},
        "widgets_values": [],
        "title": "Move initial chunk to CPU",
    },
    {
        "id": 209,
        "type": "WanS2VStateToLatent",
        "pos": [2780, 30],
        "size": [270, 70],
        "flags": {},
        "order": 51,
        "mode": 0,
        "inputs": [{"localized_name": "state", "name": "state", "type": "WAN_S2V_STATE", "link": None}],
        "outputs": [{"localized_name": "latent", "name": "latent", "type": "LATENT", "slot_index": 0, "links": None}],
        "properties": {"Node name for S&R": "WanS2VStateToLatent"},
        "widgets_values": [],
        "title": "Combine CPU chunks once at end",
    },
    {
        "id": 210,
        "type": "MarkdownNote",
        "pos": [1450, 760],
        "size": [620, 210],
        "flags": {},
        "order": 13,
        "mode": 0,
        "inputs": [],
        "outputs": [],
        "properties": {},
        "widgets_values": [
            "## Constant-memory continuation loop\n\n"
            "Each completed latent chunk is moved to system RAM. Only the last 19 latent "
            "frames are supplied as motion context to the next Wan pass. This matches the "
            "core Wan extension implementation while avoiding progressively cached GPU "
            "concatenations. The reference-image latent is reused from the initial pass, so "
            "the VAE is not reloaded between every Wan iteration. All CPU chunks are "
            "concatenated once after the loop."
        ],
        "widgets_values_named": {"text": "Constant-memory Wan continuation."},
        "title": "Why this version avoids late-loop OOM",
        "color": "#232",
        "bgcolor": "#353",
    },
]
workflow["nodes"].extend(new_nodes)
nodes = {node["id"]: node for node in workflow["nodes"]}

next_link = max(workflow["last_link_id"], max(link[0] for link in workflow["links"]))


def add(origin, origin_slot, target, target_slot, data_type):
    global next_link
    next_link += 1
    workflow["links"].append([next_link, origin, origin_slot, target, target_slot, data_type])


# Initial latent -> CPU state -> loop.
add(3, 0, 208, 0, "LATENT")
add(93, 0, 208, 1, "CONDITIONING")
add(208, 0, 198, 1, "WAN_S2V_STATE")
add(197, 3, 198, 2, "INT")

# Constant-size extension body.
add(198, 4, 201, 4, "WAN_S2V_STATE")
add(198, 4, 203, 0, "WAN_S2V_STATE")
add(6, 0, 201, 0, "CONDITIONING")
add(7, 0, 201, 1, "CONDITIONING")
add(39, 0, 201, 2, "VAE")
add(104, 0, 201, 3, "INT")
add(56, 0, 201, 5, "AUDIO_ENCODER_OUTPUT")
add(54, 0, 202, 0, "MODEL")
add(201, 0, 202, 1, "CONDITIONING")
add(201, 1, 202, 2, "CONDITIONING")
add(201, 2, 202, 3, "LATENT")
add(198, 0, 199, 0, "INT")
add(200, 0, 199, 1, "INT")
add(199, 1, 202, 4, "INT")
add(103, 0, 202, 5, "INT")
add(105, 0, 202, 6, "FLOAT")
add(202, 0, 203, 1, "LATENT")
add(203, 0, 204, 0, "WAN_S2V_STATE")
add(203, 0, 204, 1, "WAN_S2V_STATE")

# Final CPU state -> one latent concat -> existing decode workaround.
add(204, 0, 209, 0, "WAN_S2V_STATE")
add(209, 0, 94, 0, "LATENT")
add(209, 0, 95, 1, "LATENT")

# Rebuild serialized input/output link references.
for node in workflow["nodes"]:
    for item in node.get("inputs", []):
        item["link"] = None
    for item in node.get("outputs", []):
        item["links"] = None

for link_id, origin_id, origin_slot, target_id, target_slot, _ in workflow["links"]:
    origin = nodes[origin_id]
    target = nodes[target_id]
    if origin["outputs"][origin_slot]["links"] is None:
        origin["outputs"][origin_slot]["links"] = []
    origin["outputs"][origin_slot]["links"].append(link_id)
    target["inputs"][target_slot]["link"] = link_id

workflow["last_node_id"] = max(nodes)
workflow["last_link_id"] = next_link
workflow["revision"] = int(workflow.get("revision", 0)) + 1
workflow.setdefault("state", {})["lastNodeId"] = max(nodes)
workflow["state"]["lastLinkId"] = next_link

TARGET.write_text(json.dumps(workflow, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(TARGET)
