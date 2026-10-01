import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "user/default/workflows/video_wan2_2_14B_s2v.json"
TARGET = ROOT / "user/default/workflows/video_wan2_2_14B_s2v_auto_duration.json"


def input_slot(name, data_type, link=None, *, widget=False, shape=None, label=None):
    value = {"localized_name": label or name, "name": name, "type": data_type, "link": link}
    if shape is not None:
        value["shape"] = shape
    if widget:
        value["widget"] = {"name": name}
    return value


def output_slot(name, data_type, *, shape=None, slot_index=None):
    value = {"localized_name": name, "name": name, "type": data_type, "links": None}
    if shape is not None:
        value["shape"] = shape
    if slot_index is not None:
        value["slot_index"] = slot_index
    return value


def core_properties(name):
    return {"Node name for S&R": name, "cnr_id": "comfy-core", "ver": "0.3.54"}


with SOURCE.open("r", encoding="utf-8") as handle:
    workflow = json.load(handle)

# Keep the active Lightning-LoRA branch and replace its manually repeated
# extension subgraphs with one native loop. The original workflow is untouched.
remove_ids = {node["id"] for node in workflow["nodes"] if node.get("mode") == 4}
remove_ids.update({79, 85, 87, 100, 111, 145, 179, 80})
workflow["nodes"] = [node for node in workflow["nodes"] if node["id"] not in remove_ids]
workflow["links"] = [
    link
    for link in workflow["links"]
    if link[1] not in remove_ids and link[3] not in remove_ids
]

by_id = {node["id"]: node for node in workflow["nodes"]}

# Make room for the loop and final tiled decoder.
positions = {
    94: [3090, 390],
    95: [3090, 275],
    96: [3690, 175],
    82: [3380, 580],
    113: [3690, 580],
    99: [3390, 390],
    104: [420, 880],
    103: [420, 1050],
    105: [420, 1180],
}
for node_id, position in positions.items():
    if node_id in by_id:
        by_id[node_id]["pos"] = position

# The frame range is now calculated, rather than hard-coded to 4096.
by_id[96]["widgets_values"] = [0, 3022]
by_id[96]["widgets_values_named"] = {"batch_index": 0, "length": 3022}

# CreateVideo's FPS is driven by a shared primitive.
by_id[82]["widgets_values"] = [16.0, "auto", "sRGB", "none"]
by_id[82]["widgets_values_named"]["fps"] = 16.0

new_nodes = [
    {
        "id": 197,
        "type": "AudioDurationToWanChunks",
        "pos": [760, 760],
        "size": [330, 190],
        "flags": {},
        "order": 38,
        "mode": 0,
        "inputs": [
            input_slot("audio", "AUDIO"),
            input_slot("fps", "FLOAT", widget=True),
            input_slot("chunk_length", "INT", widget=True),
        ],
        "outputs": [
            output_slot("duration_seconds", "FLOAT", slot_index=0),
            output_slot("target_frames", "INT", slot_index=1),
            output_slot("total_chunks", "INT", slot_index=2),
            output_slot("extension_iterations", "INT", slot_index=3),
        ],
        "properties": {"Node name for S&R": "AudioDurationToWanChunks"},
        "widgets_values": [16.0, 77],
        "widgets_values_named": {"fps": 16.0, "chunk_length": 77},
        "title": "Automatic song-length plan",
    },
    {
        "id": 198,
        "type": "StartLoop",
        "pos": [1480, 180],
        "size": [310, 222],
        "flags": {},
        "order": 45,
        "mode": 0,
        "showAdvanced": True,
        "inputs": [
            input_slot("parent_iteration", "INT", shape=7),
            input_slot("initial_iteration_value", "LATENT", shape=7),
            input_slot("mode.num_iterations", "INT", widget=True, label="num_iterations"),
        ],
        "outputs": [
            output_slot("iteration_index", "INT"),
            output_slot("is_first", "BOOLEAN"),
            output_slot("is_last", "BOOLEAN"),
            output_slot("list_item", "*"),
            output_slot("current_iteration_value", "LATENT"),
        ],
        "properties": {"Node name for S&R": "StartLoop"},
        "widgets_values": ["simple", 1, False],
        "widgets_values_named": {
            "mode": "simple",
            "mode.num_iterations": 1,
            "cache_iterations": False,
        },
        "color": "#322",
        "bgcolor": "#533",
        "title": "Extend until the song is covered",
    },
    {
        "id": 199,
        "type": "ComfyMathExpression",
        "pos": [1790, 560],
        "size": [330, 150],
        "flags": {},
        "order": 46,
        "mode": 0,
        "inputs": [
            input_slot("values.a", "FLOAT,INT,BOOLEAN", label="iteration"),
            input_slot("values.b", "FLOAT,INT,BOOLEAN", label="base_seed"),
        ],
        "outputs": [
            output_slot("FLOAT", "FLOAT"),
            output_slot("INT", "INT"),
            output_slot("BOOL", "BOOLEAN"),
        ],
        "properties": {"Node name for S&R": "ComfyMathExpression"},
        "widgets_values": ["b + (a * 9973)"],
        "widgets_values_named": {"expression": "b + (a * 9973)"},
        "title": "Different deterministic seed per chunk",
    },
    {
        "id": 200,
        "type": "PrimitiveInt",
        "pos": [1450, 570],
        "size": [280, 82],
        "flags": {},
        "order": 10,
        "mode": 0,
        "inputs": [input_slot("value", "INT", widget=True)],
        "outputs": [output_slot("INT", "INT", slot_index=0)],
        "properties": core_properties("PrimitiveInt"),
        "widgets_values": [250, "fixed"],
        "widgets_values_named": {"value": 250, "fixed": "fixed"},
        "title": "Extension seed base",
    },
    {
        "id": 201,
        "type": "WanSoundImageToVideoExtend",
        "pos": [1810, 150],
        "size": [300, 250],
        "flags": {},
        "order": 47,
        "mode": 0,
        "inputs": [
            input_slot("positive", "CONDITIONING"),
            input_slot("negative", "CONDITIONING"),
            input_slot("vae", "VAE"),
            input_slot("video_latent", "LATENT"),
            input_slot("audio_encoder_output", "AUDIO_ENCODER_OUTPUT", shape=7),
            input_slot("ref_image", "IMAGE", shape=7),
            input_slot("control_video", "IMAGE", shape=7),
            input_slot("length", "INT", widget=True),
        ],
        "outputs": [
            output_slot("positive", "CONDITIONING"),
            output_slot("negative", "CONDITIONING"),
            output_slot("latent", "LATENT"),
        ],
        "properties": core_properties("WanSoundImageToVideoExtend"),
        "widgets_values": [77],
        "widgets_values_named": {"length": 77},
    },
    {
        "id": 202,
        "type": "KSampler",
        "pos": [2140, 140],
        "size": [300, 440],
        "flags": {},
        "order": 48,
        "mode": 0,
        "inputs": copy.deepcopy(by_id[3]["inputs"]),
        "outputs": [output_slot("LATENT", "LATENT", slot_index=0)],
        "properties": core_properties("KSampler"),
        "widgets_values": [250, "fixed", 4, 1.0, "uni_pc", "simple", 1.0],
        "widgets_values_named": {
            "seed": 250,
            "control_after_generate": "fixed",
            "steps": 4,
            "cfg": 1.0,
            "sampler_name": "uni_pc",
            "scheduler": "simple",
            "denoise": 1.0,
        },
        "title": "Sample one continuation chunk",
    },
    {
        "id": 203,
        "type": "LatentConcat",
        "pos": [2480, 220],
        "size": [240, 90],
        "flags": {},
        "order": 49,
        "mode": 0,
        "inputs": [
            input_slot("samples1", "LATENT"),
            input_slot("samples2", "LATENT"),
            input_slot("dim", "COMBO", widget=True),
        ],
        "outputs": [output_slot("LATENT", "LATENT", slot_index=0)],
        "properties": core_properties("LatentConcat"),
        "widgets_values": ["t"],
        "widgets_values_named": {"dim": "t"},
        "title": "Append continuation",
    },
    {
        "id": 204,
        "type": "EndLoop",
        "pos": [2780, 190],
        "size": [270, 120],
        "flags": {},
        "order": 50,
        "mode": 0,
        "inputs": [
            input_slot("output_value", "LATENT", shape=7),
            input_slot("next_iteration_value", "LATENT", shape=7),
        ],
        "outputs": [output_slot("outputs", "LATENT", shape=6)],
        "properties": {"Node name for S&R": "EndLoop"},
        "widgets_values": [False],
        "widgets_values_named": {"accumulate": False},
        "color": "#322",
        "bgcolor": "#533",
    },
    {
        "id": 205,
        "type": "VAEDecodeTiled",
        "pos": [3380, 150],
        "size": [280, 210],
        "flags": {},
        "order": 55,
        "mode": 0,
        "inputs": [
            input_slot("samples", "LATENT"),
            input_slot("vae", "VAE"),
            input_slot("tile_size", "INT", widget=True),
            input_slot("overlap", "INT", widget=True),
            input_slot("temporal_size", "INT", widget=True),
            input_slot("temporal_overlap", "INT", widget=True),
        ],
        "outputs": [output_slot("IMAGE", "IMAGE", slot_index=0)],
        "properties": core_properties("VAEDecodeTiled"),
        "widgets_values": [512, 64, 64, 8],
        "widgets_values_named": {
            "tile_size": 512,
            "overlap": 64,
            "temporal_size": 64,
            "temporal_overlap": 8,
        },
        "title": "Tiled decode for long video",
    },
    {
        "id": 206,
        "type": "MarkdownNote",
        "pos": [760, 980],
        "size": [530, 260],
        "flags": {},
        "order": 11,
        "mode": 0,
        "inputs": [],
        "outputs": [],
        "properties": {},
        "widgets_values": [
            "## Automatic duration\n\n"
            "The loaded audio determines the target frame count and the number of "
            "77-frame Wan continuation passes. The loop carries the complete latent "
            "forward so transitions remain continuous.\n\n"
            "The final tiled decode is trimmed to the exact calculated audio frame "
            "count. Keep **FPS**, **Chunk Length**, and the Create Video settings "
            "connected as supplied."
        ],
        "widgets_values_named": {
            "text": "Automatic duration is calculated from the loaded audio."
        },
        "title": "How this version works",
        "color": "#223",
        "bgcolor": "#335",
    },
    {
        "id": 207,
        "type": "PrimitiveFloat",
        "pos": [420, 1350],
        "size": [300, 82],
        "flags": {},
        "order": 12,
        "mode": 0,
        "inputs": [input_slot("value", "FLOAT", widget=True)],
        "outputs": [output_slot("FLOAT", "FLOAT", slot_index=0)],
        "properties": core_properties("PrimitiveFloat"),
        "widgets_values": [16.0],
        "widgets_values_named": {"value": 16.0},
        "title": "FPS",
    },
]

workflow["nodes"].extend(new_nodes)
by_id = {node["id"]: node for node in workflow["nodes"]}

# Links are [id, origin node, origin slot, target node, target slot, type].
next_link = max(workflow.get("last_link_id", 0), 604)


def add_link(origin, origin_slot, target, target_slot, data_type):
    global next_link
    next_link += 1
    workflow["links"].append([next_link, origin, origin_slot, target, target_slot, data_type])


# Planner and shared controls.
add_link(58, 0, 197, 0, "AUDIO")
add_link(207, 0, 197, 1, "FLOAT")
add_link(104, 0, 197, 2, "INT")
add_link(197, 1, 96, 2, "INT")
add_link(197, 2, 96, 1, "INT")
add_link(197, 3, 198, 2, "INT")
add_link(207, 0, 82, 2, "FLOAT")

# Initial sampled latent becomes the loop-carried value.
add_link(3, 0, 198, 1, "LATENT")
add_link(198, 4, 201, 3, "LATENT")
add_link(198, 4, 203, 0, "LATENT")

# Wan continuation conditioning.
add_link(6, 0, 201, 0, "CONDITIONING")
add_link(7, 0, 201, 1, "CONDITIONING")
add_link(39, 0, 201, 2, "VAE")
add_link(56, 0, 201, 4, "AUDIO_ENCODER_OUTPUT")
add_link(52, 0, 201, 5, "IMAGE")
add_link(104, 0, 201, 7, "INT")

# Sample and append one continuation per loop iteration.
add_link(54, 0, 202, 0, "MODEL")
add_link(201, 0, 202, 1, "CONDITIONING")
add_link(201, 1, 202, 2, "CONDITIONING")
add_link(201, 2, 202, 3, "LATENT")
add_link(198, 0, 199, 0, "INT")
add_link(200, 0, 199, 1, "INT")
add_link(199, 1, 202, 4, "INT")
add_link(103, 0, 202, 5, "INT")
add_link(105, 0, 202, 6, "FLOAT")
add_link(202, 0, 203, 1, "LATENT")
add_link(203, 0, 204, 0, "LATENT")
add_link(203, 0, 204, 1, "LATENT")

# Preserve the original first-frame VAE workaround, now with a dynamic trim.
add_link(204, 0, 94, 0, "LATENT")
add_link(204, 0, 95, 1, "LATENT")
add_link(95, 0, 205, 0, "LATENT")
add_link(39, 0, 205, 1, "VAE")
add_link(205, 0, 96, 0, "IMAGE")

# Reconstruct every input/output link list from the authoritative link table.
for node in workflow["nodes"]:
    for item in node.get("inputs", []):
        item["link"] = None
    for item in node.get("outputs", []):
        item["links"] = None

for link_id, origin_id, origin_slot, target_id, target_slot, _ in workflow["links"]:
    origin = by_id.get(origin_id)
    target = by_id.get(target_id)
    if origin is None or target is None:
        raise RuntimeError(f"Broken link {link_id}: {origin_id} -> {target_id}")
    outputs = origin.get("outputs", [])
    inputs = target.get("inputs", [])
    if origin_slot >= len(outputs) or target_slot >= len(inputs):
        raise RuntimeError(f"Invalid slot on link {link_id}")
    if outputs[origin_slot]["links"] is None:
        outputs[origin_slot]["links"] = []
    outputs[origin_slot]["links"].append(link_id)
    inputs[target_slot]["link"] = link_id

workflow["last_node_id"] = max(by_id)
workflow["last_link_id"] = next_link
workflow["revision"] = int(workflow.get("revision", 0)) + 1
workflow.setdefault("state", {})["lastNodeId"] = max(by_id)
workflow["state"]["lastLinkId"] = next_link
workflow.setdefault("definitions", {})["subgraphs"] = []
workflow["extra"]["ds"] = {"scale": 0.52, "offset": [330, 190]}

with TARGET.open("w", encoding="utf-8", newline="\n") as handle:
    json.dump(workflow, handle, ensure_ascii=False, separators=(",", ":"))

print(TARGET)
