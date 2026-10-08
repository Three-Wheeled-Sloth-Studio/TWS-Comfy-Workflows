from __future__ import annotations

import argparse
from pathlib import Path


MODEL_ID = "CIDAS/clipseg-rd64-refined"
MODEL_REVISION = "999e0328d9e10b484360c477313983f9afdd7050"
MODEL_FILES = (
    "config.json",
    "merges.txt",
    "model.safetensors",
    "preprocessor_config.json",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "vocab.json",
)
ESTIMATED_BYTES = 604_642_069


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install the optional local CLIPSeg model used by visualizer target detection."
    )
    parser.add_argument("--comfy-root", type=Path, default=Path.cwd())
    parser.add_argument("--list-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    comfy_root = arguments.comfy_root.resolve()
    destination = (comfy_root / "models" / "detection" / "clipseg-rd64-refined").resolve()
    models_root = (comfy_root / "models").resolve()
    if not destination.is_relative_to(models_root):
        raise RuntimeError(f"Refusing model destination outside {models_root}: {destination}")

    print(f"Model: {MODEL_ID}@{MODEL_REVISION}")
    print(f"Destination: {destination}")
    print(f"Download: approximately {ESTIMATED_BYTES / (1024 ** 2):.1f} MiB")
    for filename in MODEL_FILES:
        print(f"  {filename}")
    if arguments.list_only:
        return 0

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "Run this installer with ComfyUI's Python environment, which must provide huggingface_hub."
        ) from exc

    destination.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=destination,
        allow_patterns=list(MODEL_FILES),
    )
    missing = [filename for filename in MODEL_FILES if not (destination / filename).is_file()]
    if missing:
        raise RuntimeError(f"Model download completed without required files: {', '.join(missing)}")
    print("Semantic target model installed. Restart ComfyUI before using it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
