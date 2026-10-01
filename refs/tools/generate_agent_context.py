#!/usr/bin/env python3
"""Generate a compact, derived re-entry packet for coding-agent sessions."""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: python -m pip install pyyaml") from exc
try:
    from generate_source_catalog import check_catalog, query_catalog, refresh_catalog
except ImportError as exc:  # pragma: no cover
    raise SystemExit("refs/tools/generate_source_catalog.py is required") from exc

MAX_CHARS = 8_000
MAX_ITEMS = 8
MAX_CHANGED = 12
MAX_SOURCE_MATCHES = 6
TOKEN_RE = re.compile(r"[a-z0-9]+")
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
STOP = {"add", "agent", "and", "change", "code", "current", "for", "from", "into", "issue", "make", "project", "the", "this", "tool", "use", "with", "work"}


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def git(repo: Path, *args: str) -> str | None:
    try:
        run = subprocess.run(["git", *args], cwd=repo, capture_output=True, check=False, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return run.stdout.strip() if run.returncode == 0 else None


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def clean(value: Any) -> str:
    text = " ".join(str(value or "").split()).strip()
    return "" if "TEMPLATE_TODO" in text else text


def tokens(value: str) -> set[str]:
    return {t for t in TOKEN_RE.findall(value.casefold()) if len(t) > 2 and t not in STOP and not t.startswith("template")}


def truncate(value: str, limit: int = 320) -> str:
    value = " ".join(value.split())
    return value if len(value) <= limit else value[: limit - 3].rstrip() + "..."


def ranked(records: list[tuple[str, str]], wanted: set[str], limit: int = MAX_ITEMS) -> list[tuple[str, str]]:
    if not records:
        return []
    scored = sorted(records, key=lambda r: (len(tokens(f"{r[0]} {r[1]}") & wanted), r[0]), reverse=True)
    if wanted:
        matches = [r for r in scored if tokens(f"{r[0]} {r[1]}") & wanted]
        if matches:
            return matches[:limit]
    return scored[:limit]


def git_context(repo: Path, base_ref: str | None) -> dict[str, Any]:
    branch = git(repo, "branch", "--show-current") or "detached"
    candidates = [base_ref] if base_ref else []
    candidates += ["dev", "main", "master", "origin/dev", "origin/main", "origin/master"]
    base = next((c for c in candidates if c and (c == branch or git(repo, "rev-parse", "--verify", "--quiet", c) is not None)), None)
    status = git(repo, "status", "--short") or ""
    dirty = [row[3:].strip() for row in status.splitlines() if len(row) > 3 and row[3:].strip()]
    changed: list[str] = []
    if base and branch != base:
        changed = [p for p in (git(repo, "diff", "--name-only", f"{base}...HEAD") or "").splitlines() if p]
    return {"branch": branch, "head": git(repo, "rev-parse", "--short=12", "HEAD") or "unknown", "base": base or "unresolved", "changed": list(dict.fromkeys(changed + dirty))}


def planning(refs: Path, wanted: set[str]) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    decisions = []
    for item in read_yaml(refs / "planning/decisions.yaml").get("decisions") or []:
        if isinstance(item, dict) and str(item.get("status", "")).casefold() == "accepted" and clean(item.get("decision")):
            decisions.append((clean(item.get("id")) or "decision", clean(item.get("decision"))))
    active = {"open", "in_progress", "in-progress", "active", "blocked"}
    todos = []
    for item in read_yaml(refs / "planning/todos.yaml").get("todos") or []:
        if isinstance(item, dict) and str(item.get("status", "")).casefold() in active and clean(item.get("summary")):
            todos.append((clean(item.get("id")) or "todo", " - ".join(v for v in [clean(item.get("area")), clean(item.get("summary"))] if v)))
    road = []
    for item in read_yaml(refs / "planning/roadmap.yaml").get("roadmap") or []:
        if isinstance(item, dict) and str(item.get("status", "")).casefold() in {"planned", "in_progress", "in-progress", "active"} and clean(item.get("summary")):
            road.append((clean(item.get("id")) or "roadmap", " - ".join(v for v in [clean(item.get("horizon")), clean(item.get("summary"))] if v)))
    return ranked(decisions, wanted), ranked(todos, wanted), ranked(road, wanted)


def markdown_sections(path: Path) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    if not path.is_file():
        return sections
    current = "Overview"
    frontmatter, code = False, False
    paragraph: list[str] = []

    def flush() -> None:
        nonlocal paragraph
        text = clean(" ".join(paragraph))
        if text:
            sections.setdefault(current, []).append(text)
        paragraph = []

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line == "---" and not sections and not paragraph:
            frontmatter = not frontmatter; continue
        if frontmatter: continue
        if line.startswith("```"):
            flush(); code = not code; continue
        if code: continue
        heading = HEADING_RE.match(line)
        if heading:
            flush(); current = heading.group(1); continue
        if line.startswith("# "): flush(); continue
        if not line: flush(); continue
        if line.startswith(("- ", "* ")):
            flush(); value = clean(line[2:]);
            if value: sections.setdefault(current, []).append(value)
            continue
        if re.match(r"^\d+\.\s+", line):
            flush(); value = clean(re.sub(r"^\d+\.\s+", "", line));
            if value: sections.setdefault(current, []).append(value)
            continue
        paragraph.append(line)
    flush(); return sections


def handoff(refs: Path, wanted: set[str]) -> tuple[list[str], list[tuple[str, str]]]:
    sections = markdown_sections(refs / "handoffs/currentHandoff.md")
    required = (sections.get("Required Reads For Next Slice") or sections.get("Read before implementation") or [])[:10]
    ignore = {"Required Reads For Next Slice", "Read before implementation", "Validation", "Validation boundary"}
    records = [(name, text) for name, values in sections.items() if name not in ignore for text in values]
    priorities = {"next": 5, "gap": 5, "current": 4, "constraint": 3, "accepted": 3, "landed": 2}
    records.sort(key=lambda r: (10 * len(tokens(f"{r[0]} {r[1]}") & wanted) + sum(v for k, v in priorities.items() if k in r[0].casefold())), reverse=True)
    if wanted:
        matches = [r for r in records if tokens(f"{r[0]} {r[1]}") & wanted]
        if matches: records = matches
    return required, records[:6]


def file_hints(refs: Path, wanted: set[str]) -> list[tuple[str, list[str]]]:
    data = read_yaml(refs / "implementation/fileMap.yaml"); hints = []
    for item in data.get("common_tasks") or []:
        if isinstance(item, dict):
            label, paths = clean(item.get("task")), [clean(v) for v in item.get("look_in") or [] if clean(v)]
            if label and paths: hints.append((len(tokens(f"{label} {' '.join(paths)}") & wanted), label, paths))
    for name, item in (data.get("areas") or {}).items() if isinstance(data.get("areas") or {}, dict) else []:
        if not isinstance(item, dict): continue
        paths = [clean(v) for key in ("guidance", "source_roots") for v in item.get(key) or [] if clean(v)]
        label, note = clean(name), clean(item.get("notes"))
        if label and (paths or note): hints.append((len(tokens(f"{label} {note} {' '.join(paths)}") & wanted), label, paths))
    hints.sort(reverse=True)
    if wanted and any(score for score, _, _ in hints): hints = [h for h in hints if h[0]]
    return [(label, paths) for _, label, paths in hints[:3]]


def build_packet(repo: Path, focus: str = "", issue: int | None = None, base_ref: str | None = None) -> str:
    refs, wanted, session = repo / "refs", tokens(focus), git_context(repo, base_ref)
    identity = read_yaml(refs / "project.yaml").get("identity") or {}
    name, phase = clean(identity.get("name")) or "Project", clean(identity.get("current_phase")) or "unspecified"
    decisions, todos, road = planning(refs, wanted)
    required, highlights = handoff(refs, wanted)
    hints = file_hints(refs, wanted)
    matches = query_catalog(repo, focus, MAX_SOURCE_MATCHES) if focus.strip() else []
    validation = [(clean(i.get("id")) or "validation", clean(i.get("command"))) for i in read_yaml(refs / "testing/validationCommands.yaml").get("commands") or [] if isinstance(i, dict) and clean(i.get("command"))][:MAX_ITEMS]
    inferred = re.match(r"(?:agent|codex|issue)[/-](\d+)(?:-|$)", session["branch"])
    issue = issue or (int(inferred.group(1)) if inferred else None)
    lines = [f"# {name} - Generated Agent Re-entry Context", "", "> Derived orientation only. Authoritative refs and source remain the source of truth.", "", "## Session", f"- Branch: `{session['branch']}`", f"- HEAD: `{session['head']}`", f"- Base ref: `{session['base']}`", f"- Current phase: {phase}"]
    if issue is not None: lines.append(f"- Issue: #{issue}")
    if focus.strip(): lines.append(f"- Focus: {focus.strip()}")
    if session["changed"]:
        lines += ["", "## Changed paths"] + [f"- `{p}`" for p in session["changed"][:MAX_CHANGED]]
    if required: lines += ["", "## Required reads for next slice"] + [f"- {truncate(v)}" for v in required]
    if highlights: lines += ["", "## Current handoff highlights"] + [f"- **{k}:** {truncate(v)}" for k, v in highlights]
    for title, records in [("Relevant accepted decisions", decisions), ("Active todos", todos), ("Active roadmap", road)]:
        if records: lines += ["", f"## {title}"] + [f"- **{k}:** {truncate(v)}" for k, v in records]
    if matches:
        lines += ["", "## Source-catalog matches"]
        for item in matches:
            s, path = item.get("symbol"), item.get("path") or "unknown"
            if not s: lines.append(f"- `{path}` (file match)"); continue
            deps = s.get("dependencies") or []; suffix = f"; calls {', '.join(deps[:5])}" if deps else ""
            targets = s.get("dependency_targets") or []
            if targets:
                suffix += "; targets " + ", ".join(f"{t.get('path')}:{t.get('symbol')}" for t in targets[:3])
            lines.append(f"- `{path}:{s.get('line_start', '?')}-{s.get('line_end', '?')}` - `{truncate(str(s.get('signature') or s.get('name') or 'symbol'), 220)}`{suffix}")
    if hints:
        lines += ["", "## File-map hints"]
        for label, paths in hints: lines.append(f"- **{label}:** " + ", ".join(f"`{p}`" for p in paths) if paths else f"- **{label}**")
    if validation: lines += ["", "## Validation commands"] + [f"- `{k}` - `{v}`" for k, v in validation]
    lines += ["", "## Context discipline", "- Start with required reads and source-catalog matches. Expand context only for a concrete dependency, ambiguity, failing test, system boundary, or authoritative reference.", "- Query `python refs/tools/generate_source_catalog.py --query \"<task or symbol>\"` before broad repository search when the packet is insufficient.", "- Prefer symbol-level or targeted line-range reads. Do not open a whole source file when the relevant symbol or range is enough.", "- Continue diff-first from the accepted checkpoint instead of reconstructing unchanged repository state.", "- Treat accepted decisions as inputs; reopen them only when new runtime/test evidence contradicts them.", "- When the environment supports sub-agents, delegate bounded independent work when that reduces parent context or enables useful parallel work; use the least expensive capable model and keep the parent responsible for integration and validation."]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--focus", default=""); parser.add_argument("--issue", type=int); parser.add_argument("--base-ref"); parser.add_argument("--output", type=Path); parser.add_argument("--max-chars", type=int, default=MAX_CHARS); parser.add_argument("--check", action="store_true"); args = parser.parse_args()
    if args.max_chars < 2_000: raise SystemExit("--max-chars must be at least 2000")
    repo = root()
    if args.check:
        ok, problems = check_catalog(repo)
        if not ok: raise SystemExit("Source catalog is stale:\n- " + "\n- ".join(problems))
    else: refresh_catalog(repo)
    packet = build_packet(repo, args.focus, args.issue, args.base_ref)
    if len(packet) > args.max_chars: raise SystemExit(f"Generated packet is {len(packet)} characters; budget is {args.max_chars}. Tighten selectors or source material instead of increasing routine reset context.")
    if args.check:
        if "TEMPLATE_TODO" in packet: raise SystemExit("Generated packet leaked template placeholders.")
        print(f"agent context check ok: {len(packet)} characters"); return 0
    if args.output:
        path = args.output if args.output.is_absolute() else repo / args.output; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(packet, encoding="utf-8"); print(f"Wrote generated agent context: {path}"); return 0
    print(packet, end=""); return 0


if __name__ == "__main__":
    raise SystemExit(main())
