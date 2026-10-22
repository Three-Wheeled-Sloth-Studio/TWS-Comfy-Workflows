from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "user/default/workflows/music_visualizer_cached_motion_full.json"
WORKFLOW = ROOT / "user/default/workflows/music_visualizer_ti2v5b_full.json"

POSITIVE_PROMPT = (
    "Locked camera and exact source composition. Preserve all people, faces, bodies, architecture, "
    "symbols, text, objects, framing, colors, identity, exposure, brightness, and contrast. Where present, thick smoke, fog, mist, "
    "and clouds roll, curl, and billow dynamically in multiple independent layers while retaining "
    "their original color and texture. Water surfaces ripple and surge naturally. Hair and loose "
    "fabric flow in a steady breeze. Flags and hanging banners wave naturally. Chains sway slightly. "
    "Tentacles or organic appendages wriggle subtly in place. Other environmental motion may be "
    "restrained and physically plausible. Keep lights spatially fixed; music-synchronized glow and "
    "flicker are added later by the compositor. Strong atmospheric motion, crisp stable structures, "
    "stable geometry, stable camera, seamless-loop-friendly pacing."
)
NEGATIVE_PROMPT = (
    "camera movement, pan, tilt, zoom, vertical jump, frame translation, scene cut, composition shift, "
    "architecture deformation, symbol or text deformation, identity drift, face deformation, lip "
    "movement, new people, duplicate people, new objects, watermark, overexposure, blur, smeared detail, "
    "pale opaque fog, white blob, glowing haze overlay, moving light fixtures, whole-image pulsing, "
    "progressive darkening, fade to black, exposure drift"
)


def _node(node_id, node_type, pos, size, inputs, outputs, widgets, title=None, properties=None):
    node = {
        "id": node_id,
        "type": node_type,
        "pos": list(pos),
        "size": list(size),
        "flags": {},
        "order": 0,
        "mode": 0,
        "inputs": inputs,
        "outputs": outputs,
        "properties": {
            "cnr_id": "comfy-core",
            "ver": "0.3.45",
            "Node name for S&R": node_type,
            "tws_stage": "wan22_ti2v5b_generation",
            **(properties or {}),
        },
        "widgets_values": widgets,
    }
    if title:
        node["title"] = title
    return node


def _input(name, value_type, shape=None):
    result = {"name": name, "type": value_type, "link": None}
    if shape is not None:
        result["shape"] = shape
    return result


def _output(name, value_type):
    return {"name": name, "type": value_type, "slot_index": 0, "links": []}


def _strip_old_generation(workflow):
    removed = {
        node["id"] for node in workflow["nodes"]
        if node.get("properties", {}).get("tws_stage") == "wan_generation"
    }
    workflow["nodes"] = [node for node in workflow["nodes"] if node["id"] not in removed]
    surviving_links = [
        link for link in workflow["links"] if link[1] not in removed and link[3] not in removed
    ]
    valid_link_ids = {link[0] for link in surviving_links}
    workflow["links"] = surviving_links
    for node in workflow["nodes"]:
        for item in node.get("inputs", []):
            if item.get("link") not in valid_link_ids:
                item["link"] = None
        for item in node.get("outputs", []):
            if item.get("links") is not None:
                item["links"] = [link for link in item["links"] if link in valid_link_ids]
    removed_types = {
        node["type"] for node in json.loads(SOURCE.read_text(encoding="utf-8"))["nodes"]
        if node["id"] in removed
    }
    definitions = workflow.get("definitions", {}).get("subgraphs", [])
    if definitions:
        workflow["definitions"]["subgraphs"] = [item for item in definitions if item.get("id") not in removed_types]


def _connect(workflow, link_id, origin_id, output_name, target_id, input_name, value_type):
    nodes = {node["id"]: node for node in workflow["nodes"]}
    origin = nodes[origin_id]
    target = nodes[target_id]
    output_index = next(index for index, item in enumerate(origin["outputs"]) if item["name"] == output_name)
    input_index = next(index for index, item in enumerate(target["inputs"]) if item["name"] == input_name)
    origin["outputs"][output_index].setdefault("links", []).append(link_id)
    target["inputs"][input_index]["link"] = link_id
    workflow["links"].append([link_id, origin_id, output_index, target_id, input_index, value_type])


def _generation_nodes(left):
    x0, y0 = left, -690
    return [
        _node(400, "UNETLoader", (x0, y0), (390, 82), [], [_output("MODEL", "MODEL")],
              ["wan2.2_ti2v_5B_fp16.safetensors", "default"], "WAN 2.2 TI2V 5B MODEL"),
        _node(401, "CLIPLoader", (x0, y0 + 135), (390, 106), [], [_output("CLIP", "CLIP")],
              ["umt5_xxl_fp8_e4m3fn_scaled.safetensors", "wan", "default"], "WAN TEXT ENCODER"),
        _node(402, "VAELoader", (x0, y0 + 295), (390, 60), [], [_output("VAE", "VAE")],
              ["wan2.2_vae.safetensors"], "WAN 2.2 VAE"),
        _node(403, "CLIPTextEncode", (x0 + 450, y0), (560, 235), [_input("clip", "CLIP")],
              [_output("CONDITIONING", "CONDITIONING")], [POSITIVE_PROMPT],
              "MOTION BEHAVIOR — generic; edit for artwork only when needed"),
        _node(404, "CLIPTextEncode", (x0 + 450, y0 + 285), (560, 220), [_input("clip", "CLIP")],
              [_output("CONDITIONING", "CONDITIONING")], [NEGATIVE_PROMPT], "STABILITY / EXCLUSION PROMPT"),
        _node(405, "ModelSamplingSD3", (x0 + 1080, y0), (250, 60), [_input("model", "MODEL")],
              [_output("MODEL", "MODEL")], [8], "TI2V SAMPLING SHIFT"),
        _node(406, "Wan22ImageToVideoLatent", (x0 + 1080, y0 + 335), (300, 150),
              [_input("vae", "VAE"), _input("start_image", "IMAGE", 7)], [_output("LATENT", "LATENT")],
              [1024, 576, 77, 1], "SOURCE ARTWORK → 77-FRAME MOTION"),
        _node(407, "KSampler", (x0 + 1450, y0), (315, 300),
              [_input("model", "MODEL"), _input("positive", "CONDITIONING"),
               _input("negative", "CONDITIONING"), _input("latent_image", "LATENT")],
              [_output("LATENT", "LATENT")], [22102026, "fixed", 20, 5, "uni_pc", "simple", 1],
              "GENERATE MOTION — 20-step production setting"),
        _node(408, "VAEDecode", (x0 + 1835, y0 + 35), (230, 46),
              [_input("samples", "LATENT"), _input("vae", "VAE")], [_output("IMAGE", "IMAGE")], [],
              "DECODE GENERATED MOTION"),
        _node(409, "InfraChoirPersistMotionClip", (x0 + 2135, y0), (430, 150),
              [_input("images", "IMAGE")],
              [_output("persisted_images", "IMAGE"), _output("generated_clip_path", "STRING"),
               _output("diagnostic", "STRING")],
              [16, "music_visualizer/motion_assets/generated_motion"],
              "RUN THIS OUTPUT — generate and save reusable motion clip",
              {"cnr_id": "comfyui_audio_duration_plan", "Node name for S&R": "InfraChoirPersistMotionClip"}),
        _node(410, "PreviewImage", (x0 + 2635, y0), (420, 330), [_input("images", "IMAGE")], [], [],
              "MOTION PREVIEW — saved before full-song compositor"),
    ]


def _validate(workflow, source_hash):
    nodes = {node["id"]: node for node in workflow["nodes"]}
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash
    assert not any(node.get("properties", {}).get("tws_stage") == "wan_generation" for node in workflow["nodes"])
    assert nodes[400]["widgets_values"][0] == "wan2.2_ti2v_5B_fp16.safetensors"
    assert nodes[406]["widgets_values"] == [1024, 576, 77, 1]
    assert nodes[407]["widgets_values"][2:4] == [20, 5]
    assert nodes[409]["type"] == "InfraChoirPersistMotionClip"
    assert nodes[5]["inputs"][1]["link"] == 2110
    assert nodes[11]["widgets_values_named"]["maximum_stabilization_percent"] == 0.0
    assert nodes[1]["widgets_values_named"] == json.loads(SOURCE.read_text(encoding="utf-8"))["nodes"][0]["widgets_values_named"]
    links = {link[0]: link for link in workflow["links"]}
    assert links[2101][1:5] == [401, 0, 403, 0]
    assert links[2107][1:5] == [407, 0, 408, 0]
    assert links[2108][1:5] == [408, 0, 409, 0]
    assert links[2110][1:5] == [409, 0, 5, 1]
    assert workflow["state"]["lastNodeId"] == workflow["last_node_id"] == 410
    assert workflow["state"]["lastLinkId"] == workflow["last_link_id"] == 2114


def build():
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    workflow = copy.deepcopy(json.loads(SOURCE.read_text(encoding="utf-8")))
    _strip_old_generation(workflow)
    minimum_x = min(float(node["pos"][0]) for node in workflow["nodes"])
    left = minimum_x - 3250
    workflow["nodes"].extend(_generation_nodes(left))

    connections = [
        (2101, 401, "CLIP", 403, "clip", "CLIP"),
        (2102, 401, "CLIP", 404, "clip", "CLIP"),
        (2103, 400, "MODEL", 405, "model", "MODEL"),
        (2104, 405, "MODEL", 407, "model", "MODEL"),
        (2105, 403, "CONDITIONING", 407, "positive", "CONDITIONING"),
        (2106, 404, "CONDITIONING", 407, "negative", "CONDITIONING"),
        (2107, 407, "LATENT", 408, "samples", "LATENT"),
        (2108, 408, "IMAGE", 409, "images", "IMAGE"),
        (2109, 409, "persisted_images", 410, "images", "IMAGE"),
        (2110, 409, "persisted_images", 5, "generated_motion", "IMAGE"),
        (2111, 402, "VAE", 406, "vae", "VAE"),
        (2112, 1, "IMAGE", 406, "start_image", "IMAGE"),
        (2113, 406, "LATENT", 407, "latent_image", "LATENT"),
        (2114, 402, "VAE", 408, "vae", "VAE"),
    ]
    for connection in connections:
        _connect(workflow, *connection)

    node5 = next(node for node in workflow["nodes"] if node["id"] == 5)
    node5["title"] = "GENERATED MOTION — persisted before full-song render"
    workflow.setdefault("groups", []).append({
        "id": max([group.get("id", 0) for group in workflow.get("groups", [])] + [0]) + 1,
        "title": "WAN 2.2 TI2V 5B — GENERATE AND PERSIST MOTION FIRST",
        "bounding": [left - 60, -770, 3185, 960],
        "color": "#3f789e",
        "font_size": 24,
        "flags": {},
    })
    workflow["last_node_id"] = workflow["state"]["lastNodeId"] = 410
    workflow["last_link_id"] = workflow["state"]["lastLinkId"] = 2114
    _validate(workflow, source_hash)
    WORKFLOW.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash
    print(f"Wrote {WORKFLOW}")
    print(f"Preserved source SHA256 {source_hash.upper()}")


if __name__ == "__main__":
    build()
