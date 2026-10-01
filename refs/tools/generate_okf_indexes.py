#!/usr/bin/env python3
"""Generate deterministic OKF discovery indexes for the Agent Academy refs bundle."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: python -m pip install pyyaml") from exc


ROOT = Path(__file__).resolve().parents[2]
REFS = ROOT / "refs"
PROFILE = REFS / "okfProfile.yaml"
RESERVED_MARKDOWN = {"index.md", "log.md"}
IGNORED_DIR_NAMES = {"__pycache__"}


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_frontmatter(contents: str) -> dict[str, Any]:
    if not contents.startswith("---\n"):
        return {}
    end = contents.find("\n---\n", 4)
    if end < 0:
        return {}
    raw = contents[4:end]
    data = yaml.load(raw, Loader=yaml.BaseLoader) or {}
    return data if isinstance(data, dict) else {}


def humanize(value: str) -> str:
    if value.isupper():
        return value
    value = value.replace("_", " ").replace("-", " ")
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    return " ".join(part.capitalize() for part in value.split())


def first_heading(contents: str) -> str | None:
    body = contents
    if contents.startswith("---\n"):
        end = contents.find("\n---\n", 4)
        if end >= 0:
            body = contents[end + 5 :]
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def visible_directories(directory: Path) -> list[Path]:
    items: list[Path] = []
    for child in directory.iterdir():
        if not child.is_dir():
            continue
        if child.name.startswith(".") or child.name in IGNORED_DIR_NAMES:
            continue
        items.append(child)
    return sorted(items, key=lambda p: p.name.casefold())


def visible_files(directory: Path) -> list[Path]:
    items: list[Path] = []
    for child in directory.iterdir():
        if not child.is_file():
            continue
        if child.name.startswith(".") or child.name in RESERVED_MARKDOWN:
            continue
        items.append(child)
    return sorted(items, key=lambda p: p.name.casefold())


def bundle_directories() -> list[Path]:
    directories = [REFS]
    for path in REFS.rglob("*"):
        if not path.is_dir():
            continue
        if any(part.startswith(".") or part in IGNORED_DIR_NAMES for part in path.relative_to(REFS).parts):
            continue
        directories.append(path)
    return sorted(directories, key=lambda p: p.relative_to(REFS).as_posix().casefold())


def concept_entry(path: Path) -> str:
    contents = text(path)
    frontmatter = load_frontmatter(contents)
    title = str(frontmatter.get("title") or first_heading(contents) or humanize(path.stem))
    description = str(frontmatter.get("description") or "Agent Academy knowledge concept.")
    return f"* [{title}]({path.name}) - {description}"


def resource_entry(path: Path, kind: str) -> str:
    return f"* [{path.name}]({path.name}) - Agent Academy {kind} resource."


def directory_entry(path: Path) -> str:
    title = humanize(path.name)
    return f"* [{title}]({path.name}/) - Browse {title} knowledge and resources."


def render_index(directory: Path, okf_version: str, bundle_title: str) -> str:
    is_root = directory == REFS
    title = bundle_title if is_root else humanize(directory.name)
    lines: list[str] = []
    if is_root:
        lines.extend(["---", f'okf_version: "{okf_version}"', "---", ""])
    lines.extend(
        [
            f"# {title}",
            "",
            "Generated OKF discovery index. Do not edit manually.",
            "",
        ]
    )

    directories = visible_directories(directory)
    files = visible_files(directory)
    concepts = [p for p in files if p.suffix.lower() == ".md"]
    structured = [p for p in files if p.suffix.lower() in {".yaml", ".yml"}]
    support = [p for p in files if p not in concepts and p not in structured]

    if directories:
        lines.extend(["## Directories", ""])
        lines.extend(directory_entry(path) for path in directories)
        lines.append("")
    if concepts:
        lines.extend(["## Concepts", ""])
        lines.extend(concept_entry(path) for path in concepts)
        lines.append("")
    if structured:
        lines.extend(["## Structured Resources", ""])
        lines.extend(resource_entry(path, "structured") for path in structured)
        lines.append("")
    if support:
        lines.extend(["## Supporting Files", ""])
        lines.extend(resource_entry(path, "supporting") for path in support)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def load_profile() -> dict[str, Any]:
    if not PROFILE.is_file():
        raise SystemExit(f"Missing OKF profile: {PROFILE.relative_to(ROOT).as_posix()}")
    data = yaml.safe_load(text(PROFILE)) or {}
    if not isinstance(data, dict):
        raise SystemExit("refs/okfProfile.yaml must contain a mapping")
    return data


def expected_indexes() -> dict[Path, str]:
    profile = load_profile()
    okf = profile.get("okf", {})
    bundle = profile.get("bundle", {})
    version = str(okf.get("version") or "")
    title = str(bundle.get("title") or "Agent Academy Knowledge Bundle")
    if not version:
        raise SystemExit("refs/okfProfile.yaml is missing okf.version")
    return {
        directory / "index.md": render_index(directory, version, title)
        for directory in bundle_directories()
    }


def check_indexes(expected: dict[Path, str]) -> int:
    errors: list[str] = []
    expected_paths = set(expected)
    existing_paths = {
        path
        for path in REFS.rglob("index.md")
        if not any(part.startswith(".") or part in IGNORED_DIR_NAMES for part in path.relative_to(REFS).parts)
    }

    for path, wanted in expected.items():
        if not path.is_file():
            errors.append(f"{path.relative_to(ROOT).as_posix()}: generated index is missing")
            continue
        actual = text(path)
        if actual != wanted:
            errors.append(f"{path.relative_to(ROOT).as_posix()}: generated index is stale")

    for path in sorted(existing_paths - expected_paths):
        errors.append(f"{path.relative_to(ROOT).as_posix()}: unexpected generated index")

    if errors:
        print("OKF index check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"OKF index check passed ({len(expected)} indexes)")
    return 0


def write_indexes(expected: dict[Path, str]) -> int:
    expected_paths = set(expected)
    for path, contents in expected.items():
        path.write_text(contents, encoding="utf-8")

    for path in REFS.rglob("index.md"):
        if path not in expected_paths and not any(
            part.startswith(".") or part in IGNORED_DIR_NAMES for part in path.relative_to(REFS).parts
        ):
            path.unlink()

    print(f"Wrote {len(expected)} OKF indexes")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if committed OKF indexes do not match deterministic generated output.",
    )
    args = parser.parse_args()
    expected = expected_indexes()
    return check_indexes(expected) if args.check else write_indexes(expected)


if __name__ == "__main__":
    raise SystemExit(main())
