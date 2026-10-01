#!/usr/bin/env python3
"""Validate the reusable refs harness and its Agent Academy OKF profile."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: python -m pip install pyyaml") from exc

try:
    from generate_okf_indexes import expected_indexes
except ImportError as exc:  # pragma: no cover
    raise SystemExit("refs/tools/generate_okf_indexes.py is required") from exc


ROOT = Path(__file__).resolve().parents[2]
REFS = ROOT / "refs"
POLICY = REFS / "templatePolicy.yaml"
OKF_PROFILE = REFS / "okfProfile.yaml"
OKF_RESERVED = {"index.md", "log.md"}
OKF_STATUSES = {"draft", "stable", "deprecated"}
OKF_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def all_ref_files() -> list[Path]:
    return [p for p in REFS.rglob("*") if p.is_file() and "__pycache__" not in p.parts]


def yaml_files() -> list[Path]:
    return [p for p in all_ref_files() if p.suffix in {".yaml", ".yml"}]


def markdown_files() -> list[Path]:
    return [p for p in all_ref_files() if p.suffix.lower() == ".md"]


def add_error(errors: list[str], path: Path | str, message: str) -> None:
    label = path if isinstance(path, str) else rel(path)
    errors.append(f"{label}: {message}")


def validate_required_files(policy: dict[str, Any], errors: list[str]) -> None:
    for item in policy.get("required_files", []):
        if not (ROOT / item).is_file():
            add_error(errors, item, "required file is missing")


def validate_yaml_parse(errors: list[str]) -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    for path in yaml_files():
        try:
            loaded[rel(path)] = load_yaml(path)
        except yaml.YAMLError as exc:
            add_error(errors, path, f"invalid YAML: {exc}")
    return loaded


def validate_schema_keys(loaded: dict[str, Any], errors: list[str]) -> None:
    registry_path = REFS / "schemas" / "schemaRegistry.yaml"
    registry = loaded.get(rel(registry_path)) or load_yaml(registry_path)
    defaults = registry.get("defaults", {}).get("yaml_required_top_level_keys", [])

    for path in yaml_files():
        data = loaded.get(rel(path), {})
        if not isinstance(data, dict):
            add_error(errors, path, "YAML root must be a mapping")
            continue
        for key in defaults:
            if key not in data:
                add_error(errors, path, f"missing required top-level key `{key}`")

    for item, schema in registry.get("schemas", {}).items():
        data = loaded.get(item)
        if data is None:
            continue
        for key in schema.get("required_top_level_keys", []):
            if key not in data:
                add_error(errors, item, f"missing schema top-level key `{key}`")

    integration_schema = registry.get("integration_file_schema", {})
    allowed = set(integration_schema.get("allowed_statuses", []))
    required_keys = integration_schema.get("required_integration_keys", [])
    for path in REFS.glob("integrations/*.yaml"):
        data = loaded.get(rel(path), {})
        integration = data.get("integration") if isinstance(data, dict) else None
        if not isinstance(integration, dict):
            add_error(errors, path, "missing integration mapping")
            continue
        for key in required_keys:
            if key not in integration:
                add_error(errors, path, f"missing integration key `{key}`")
        status = integration.get("status")
        if allowed and status not in allowed:
            add_error(errors, path, f"integration status `{status}` is not allowed")


def validate_schema_references(loaded: dict[str, Any], errors: list[str]) -> None:
    for item, data in loaded.items():
        if not isinstance(data, dict) or "schema" not in data:
            continue
        schema_ref = data["schema"]
        if not isinstance(schema_ref, str):
            add_error(errors, item, "`schema` must be a relative path string")
            continue
        if Path(schema_ref).is_absolute() or re.match(r"^[A-Za-z]:", schema_ref):
            add_error(errors, item, "`schema` must be relative")
            continue
        if not (ROOT / schema_ref).is_file():
            add_error(errors, item, f"schema reference `{schema_ref}` does not exist")


def validate_placeholders(policy: dict[str, Any], mode: str, errors: list[str]) -> None:
    allowed_tokens = set(policy.get("placeholder_tokens", []))
    token_re = re.compile(r"\b[A-Z][A-Z0-9_]*TODO[A-Z0-9_]*\b")
    bootstrap = {ROOT / item for item in policy.get("bootstrap_files", [])}

    for path in all_ref_files():
        found = set(token_re.findall(text(path)))
        disallowed = found - allowed_tokens
        for token in sorted(disallowed):
            add_error(errors, path, f"placeholder token `{token}` is not allowed")
        if mode == "initialized" and path in bootstrap and found:
            add_error(errors, path, "bootstrap file still contains template placeholders")


def validate_secret_scan(policy: dict[str, Any], errors: list[str]) -> None:
    patterns = policy.get("validation", {}).get("disallowed_secret_patterns", [])
    regexes = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    assignment_re = re.compile(r"[:=]\s*['\"]?[A-Za-z0-9_/\-+=]{16,}")

    for path in all_ref_files():
        if rel(path).startswith("refs/examples/"):
            continue
        for lineno, line in enumerate(text(path).splitlines(), start=1):
            if any(regex.search(line) for regex in regexes) and assignment_re.search(line):
                add_error(errors, path, f"possible secret-like value on line {lineno}")


def validate_portable_paths(errors: list[str]) -> None:
    absolute_windows = re.compile(r"[A-Za-z]:\\")
    absolute_unix = re.compile(r"(?<!:)\s/[A-Za-z0-9_.-]")
    for path in yaml_files():
        contents = text(path)
        if absolute_windows.search(contents):
            add_error(errors, path, "contains a Windows absolute path")
        if absolute_unix.search(contents):
            add_error(errors, path, "contains a Unix absolute path")


def parse_okf_frontmatter(path: Path, errors: list[str]) -> dict[str, Any] | None:
    contents = text(path)
    if not contents.startswith("---\n"):
        add_error(errors, path, "OKF concept is missing YAML frontmatter")
        return None
    end = contents.find("\n---\n", 4)
    if end < 0:
        add_error(errors, path, "OKF frontmatter is not closed")
        return None
    raw = contents[4:end]
    try:
        data = yaml.load(raw, Loader=yaml.BaseLoader) or {}
    except yaml.YAMLError as exc:
        add_error(errors, path, f"invalid OKF frontmatter: {exc}")
        return None
    if not isinstance(data, dict):
        add_error(errors, path, "OKF frontmatter must be a mapping")
        return None
    return data


def validate_timestamp(value: Any, path: Path, field: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not OKF_TIMESTAMP_RE.match(value):
        add_error(
            errors,
            path,
            f"`{field}` must be an ISO 8601 datetime with an explicit UTC offset",
        )


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def validate_okf_metadata(path: Path, data: dict[str, Any], errors: list[str]) -> None:
    concept_type = data.get("type")
    if not isinstance(concept_type, str) or not concept_type.strip():
        add_error(errors, path, "OKF frontmatter must contain a non-empty `type`")

    status = data.get("status")
    if status is not None and status not in OKF_STATUSES:
        add_error(errors, path, f"OKF status `{status}` is not supported")

    generated = data.get("generated")
    if generated is not None:
        if not isinstance(generated, dict) or not generated.get("by"):
            add_error(errors, path, "`generated` must be a mapping with non-empty `by`")
        elif generated.get("at") is not None:
            validate_timestamp(generated.get("at"), path, "generated.at", errors)

    verified = data.get("verified")
    if verified is not None:
        records = as_list(verified)
        if not records:
            add_error(errors, path, "`verified` must be a mapping or list of mappings")
        for index, record in enumerate(records):
            if not isinstance(record, dict) or not record.get("by") or not record.get("at"):
                add_error(errors, path, f"`verified[{index}]` must contain `by` and `at`")
                continue
            validate_timestamp(record.get("at"), path, f"verified[{index}].at", errors)

    stale_after = data.get("stale_after")
    if stale_after is not None:
        validate_timestamp(stale_after, path, "stale_after", errors)

    sources = data.get("sources")
    if sources is not None:
        if not isinstance(sources, list):
            add_error(errors, path, "`sources` must be a list")
        else:
            for index, source in enumerate(sources):
                if not isinstance(source, dict) or not source.get("resource"):
                    add_error(errors, path, f"`sources[{index}]` must contain `resource`")
                    continue
                if source.get("last_modified") is not None:
                    validate_timestamp(
                        source.get("last_modified"),
                        path,
                        f"sources[{index}].last_modified",
                        errors,
                    )
                usage_window = source.get("usage_window")
                if isinstance(usage_window, dict):
                    for key in ("from", "to"):
                        if usage_window.get(key) is not None:
                            validate_timestamp(
                                usage_window.get(key),
                                path,
                                f"sources[{index}].usage_window.{key}",
                                errors,
                            )

    usage_window = data.get("usage_window")
    if isinstance(usage_window, dict):
        for key in ("from", "to"):
            if usage_window.get(key) is not None:
                validate_timestamp(usage_window.get(key), path, f"usage_window.{key}", errors)


def validate_okf_concepts(errors: list[str]) -> None:
    for path in markdown_files():
        if path.name in OKF_RESERVED:
            continue
        data = parse_okf_frontmatter(path, errors)
        if data is not None:
            validate_okf_metadata(path, data, errors)


def validate_okf_profile(loaded: dict[str, Any], errors: list[str]) -> None:
    profile = loaded.get(rel(OKF_PROFILE))
    if not isinstance(profile, dict):
        add_error(errors, OKF_PROFILE, "OKF profile must be a mapping")
        return
    okf = profile.get("okf")
    bundle = profile.get("bundle")
    if not isinstance(okf, dict) or not okf.get("version"):
        add_error(errors, OKF_PROFILE, "missing `okf.version`")
        return
    if not isinstance(bundle, dict) or bundle.get("root") != "refs":
        add_error(errors, OKF_PROFILE, "`bundle.root` must be `refs`")

    baseline = okf.get("baseline_commit")
    if not isinstance(baseline, str) or not re.fullmatch(r"[0-9a-f]{40}", baseline):
        add_error(errors, OKF_PROFILE, "`okf.baseline_commit` must be a full commit SHA")

    root_index = REFS / "index.md"
    if not root_index.is_file():
        add_error(errors, root_index, "OKF bundle root index is missing")
        return
    data = parse_okf_frontmatter(root_index, errors)
    if data is None:
        return
    if set(data) != {"okf_version"}:
        add_error(errors, root_index, "root index frontmatter may contain only `okf_version`")
    if data.get("okf_version") != str(okf.get("version")):
        add_error(errors, root_index, "`okf_version` does not match refs/okfProfile.yaml")

    for path in REFS.rglob("index.md"):
        if path == root_index:
            continue
        if text(path).startswith("---\n"):
            add_error(errors, path, "non-root OKF index files must not contain frontmatter")


def validate_okf_indexes(errors: list[str]) -> None:
    try:
        expected = expected_indexes()
    except SystemExit as exc:
        add_error(errors, "refs/index.md", f"could not generate OKF indexes: {exc}")
        return

    expected_paths = set(expected)
    existing_paths = {
        path for path in REFS.rglob("index.md") if "__pycache__" not in path.parts
    }

    for path, wanted in expected.items():
        if not path.is_file():
            add_error(errors, path, "generated OKF index is missing")
        elif text(path) != wanted:
            add_error(errors, path, "generated OKF index is stale")

    for path in existing_paths - expected_paths:
        add_error(errors, path, "unexpected generated OKF index")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["template", "initialized"], default="template")
    args = parser.parse_args()

    errors: list[str] = []
    if not POLICY.is_file():
        add_error(errors, POLICY, "template policy is missing")
        print("\n".join(errors), file=sys.stderr)
        return 1

    policy = load_yaml(POLICY)
    validate_required_files(policy, errors)
    loaded = validate_yaml_parse(errors)
    validate_schema_keys(loaded, errors)
    validate_schema_references(loaded, errors)
    validate_placeholders(policy, args.mode, errors)
    validate_secret_scan(policy, errors)
    validate_portable_paths(errors)
    validate_okf_concepts(errors)
    validate_okf_profile(loaded, errors)
    validate_okf_indexes(errors)

    if errors:
        print("refs validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"refs validation passed ({args.mode} mode, OKF-compatible)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
