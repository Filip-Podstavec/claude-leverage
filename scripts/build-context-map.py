#!/usr/bin/env python3
"""Build .claude-leverage-context-map.json — a per-file index of AIDEV
anchors, per-dir AGENTS.md chain, and ADR cross-references.

Used by scripts/hooks/context-surface.sh (PreToolUse hook) to surface
context relevant to the specific file the agent is about to read or edit,
instead of forcing the agent to consume the full leverage-doc surface
upfront. See docs/adr/0008-smart-context-surfacing-via-pretooluse-hook.md.

Usage:
    python scripts/build-context-map.py              # writes manifest at repo root
    python scripts/build-context-map.py --check      # exit 1 if regen would diff committed file
    python scripts/build-context-map.py --quiet      # suppress summary stdout

Stdlib-only — runs anywhere Python 3.8+ runs.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from conventions import parse_conventions
except Exception:
    def parse_conventions(_text):  # graceful: no conventions support
        return None

SCHEMA_VERSION = 1
# 1.9.0: fold conventions.yml into _meta.conventions; --check drift is expected until the manifest is regenerated + committed
BUILDER_VERSION = "1.9.0"  # bump on schema or anchor-extraction semantic changes
MANIFEST_NAME = ".claude-leverage-context-map.json"
GENERATOR = "scripts/build-context-map.py"

# AIDEV-NOTE: regex matches `AIDEV-NOTE:`, `AIDEV-TODO(by: YYYY-MM-DD):`,
# `AIDEV-QUESTION:` — case-sensitive, all-caps prefix per convention in
# AGENTS.md. Deadline-bearing variant captures the date in group 2.
ANCHOR_RE = re.compile(
    r"AIDEV-(NOTE|TODO|QUESTION)(?:\(by:\s*(\d{4}-\d{2}-\d{2})\))?:\s*(.*)"
)

# Comment-marker prefixes that count as "this line is a real comment, the
# AIDEV anchor isn't inside a string literal". Covers Python/shell (#),
# C-family + JS/TS/Go/Rust (// and /*), SQL/Lua/Haskell (--), Lisp (;),
# and `*` continuation lines inside /* ... */ blocks.
_COMMENT_MARKERS = ("#", "//", "/*", "--", ";", "*")


def find_repo_root(start: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def list_tracked_files(repo_root: Path) -> list[Path]:
    """Use git to enumerate files — skips .gitignored content for free."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "--cached", "--others",
             "--exclude-standard"],
            capture_output=True, text=True, check=True, timeout=30,
        )
        return [repo_root / p for p in out.stdout.splitlines() if p]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []


def _scan_anchors(file_path: Path) -> list[dict]:
    """Return list of anchor dicts for the file. Skips:
      - Files >1 MiB (too large to be meaningful source)
      - Binary files (NUL byte in first 8 KiB sniff)
      - Files with unreadable bytes
    NUL-byte sniff is the same heuristic git uses internally — keeps PNGs,
    parquet, zips, etc. out of the manifest without an extension allowlist
    that would miss legitimate non-standard source files.
    """
    try:
        if file_path.stat().st_size > 1_048_576:
            return []
        with file_path.open("rb") as fh:
            head = fh.read(8192)
        if b"\x00" in head:
            return []
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return []

    anchors: list[dict] = []
    for i, line in enumerate(text.splitlines(), start=1):
        m = ANCHOR_RE.search(line)
        if not m:
            continue
        # Comment-context gate: skip matches inside string literals or
        # arbitrary code. The text from line-start up to the anchor must
        # begin (after stripping leading whitespace) with a comment marker.
        # Without this, the manifest builder would extract AIDEV-NOTE from
        # its own JSON values, test fixtures like
        # `{"src/x.py": "# AIDEV-NOTE: real anchor\n"}`, and prose
        # mentioning "AIDEV-NOTE: ..." inside docstrings.
        prefix_stripped = line[: m.start()].lstrip()
        if not prefix_stripped or not prefix_stripped.startswith(_COMMENT_MARKERS):
            continue
        a = {
            "line": i,
            "type": f"AIDEV-{m.group(1)}",
            "text": m.group(3).strip(),
        }
        if m.group(2):
            a["deadline"] = m.group(2)
        anchors.append(a)
    return anchors


def _agents_md_chain(file_rel: Path, repo_root: Path) -> list[str]:
    """Walk from dirname(file) up to repo_root, listing every AGENTS.md
    that exists, dirname-first.

    Tolerant of symlinks: if `.resolve()` escapes `repo_root`, return
    whatever chain we built so far rather than crashing on `relative_to`.
    """
    chain: list[str] = []
    try:
        cur = (repo_root / file_rel).parent.resolve()
        root_resolved = repo_root.resolve()
    except (OSError, RuntimeError):
        return chain
    while True:
        candidate = cur / "AGENTS.md"
        if candidate.is_file():
            try:
                chain.append(candidate.relative_to(root_resolved).as_posix())
            except ValueError:
                return chain  # symlink escaped repo — stop walking
        if cur == root_resolved:
            break
        parent = cur.parent
        if parent == cur:
            break  # filesystem root reached
        cur = parent
    return chain


def _adr_index(repo_root: Path) -> list[tuple[str, str]]:
    """Return list of (relpath, body_text) for every docs/adr/*.md except
    README and the 0000-template file. Read once, queried per file."""
    adr_dir = repo_root / "docs" / "adr"
    if not adr_dir.is_dir():
        return []
    out: list[tuple[str, str]] = []
    for p in sorted(adr_dir.glob("*.md")):
        name = p.name.lower()
        if name == "readme.md" or name.startswith("0000-") or name == "template.md":
            continue
        try:
            body = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        out.append((p.relative_to(repo_root).as_posix(), body))
    return out


def build(repo_root: Path) -> dict:
    """Walk repo, extract anchors, return manifest dict."""
    files_map: dict[str, dict] = {}
    total_anchors = 0
    file_count = 0

    for abs_path in list_tracked_files(repo_root):
        if not abs_path.is_file():
            continue
        # AIDEV-NOTE: skip the manifest itself — its own JSON literals
        # contain the AIDEV-NOTE substring inside text values, which would
        # otherwise cause the builder to (a) include itself with bogus
        # anchors and (b) drift between runs whenever anchor text changes.
        if abs_path.name == MANIFEST_NAME:
            continue
        anchors = _scan_anchors(abs_path)
        if not anchors:
            continue
        try:
            rel = abs_path.relative_to(repo_root).as_posix()
        except ValueError:
            continue
        files_map[rel] = {
            "anchors_in_file": anchors,
            "anchors_in_dir": [],
            "agents_md": [],
            "adrs": [],
        }
        total_anchors += len(anchors)
        file_count += 1

    # Second pass: cross-populate anchors_in_dir from same-directory siblings.
    by_dir: dict[str, list[tuple[str, dict]]] = {}
    for rel, entry in files_map.items():
        d = str(Path(rel).parent.as_posix())
        for a in entry["anchors_in_file"]:
            by_dir.setdefault(d, []).append((rel, a))

    for rel, entry in files_map.items():
        d = str(Path(rel).parent.as_posix())
        for sibling_rel, a in by_dir.get(d, []):
            if sibling_rel == rel:
                continue
            entry["anchors_in_dir"].append({
                "file": sibling_rel,
                "line": a["line"],
                "type": a["type"],
                "text": a["text"],
            })

    # Third pass: AGENTS.md chain + ADR cross-references.
    adrs = _adr_index(repo_root)
    for rel, entry in files_map.items():
        entry["agents_md"] = _agents_md_chain(Path(rel), repo_root)
        # Word-boundary path match: `src/api.py` in ADR matches `src/api.py`
        # but NOT `src/api.pyc` or `src/api.py.bak`. Boundaries are chars
        # that aren't path or alphanumeric continuations.
        path_re = re.compile(
            r"(?<![A-Za-z0-9_./-])" + re.escape(rel) + r"(?![A-Za-z0-9_/-])"
        )
        entry["adrs"] = [adr_rel for adr_rel, body in adrs if path_re.search(body)]

    conv_path = repo_root / "conventions.yml"
    conventions = None
    if conv_path.is_file():
        try:
            conventions = parse_conventions(conv_path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            conventions = None

    meta = {
        "schema_version": SCHEMA_VERSION,
        "builder_version": BUILDER_VERSION,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "generator": GENERATOR,
        "file_count": file_count,
        "anchor_count": total_anchors,
        "repo_root": ".",
    }
    if conventions:
        meta["conventions"] = conventions
    return {"_meta": meta, "files": files_map}


def _atomic_write(path: Path, content: str) -> None:
    """Write `content` to `path` atomically — write to `.tmp` sibling then
    os.replace into place. Prevents the hook from observing a half-written
    manifest if a builder run races with a tool call."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if regen would differ from on-disk manifest")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    repo_root = find_repo_root(Path.cwd())
    if repo_root is None:
        print("ERROR: not inside a git repo", file=sys.stderr)
        return 2

    manifest = build(repo_root)
    out_path = repo_root / MANIFEST_NAME
    new_json = json.dumps(manifest, indent=2, sort_keys=True) + "\n"

    if args.check:
        old_json = out_path.read_text(encoding="utf-8") if out_path.exists() else ""
        if _strip_generated_at(old_json) != _strip_generated_at(new_json):
            print(f"DRIFT: {out_path} differs from regen — run "
                  f"`python scripts/build-context-map.py` to update", file=sys.stderr)
            return 1
        if not args.quiet:
            print(f"OK: {out_path} is up to date")
        return 0

    _atomic_write(out_path, new_json)
    if not args.quiet:
        print(f"Wrote {out_path} "
              f"({manifest['_meta']['file_count']} files, "
              f"{manifest['_meta']['anchor_count']} anchors)")
    return 0


def _strip_generated_at(blob: str) -> str:
    """Strip the generated_at line so --check ignores pure-timestamp diffs.
    Without this, running --check moments after a rebuild would always
    flag drift because of the new timestamp."""
    return re.sub(r'"generated_at":\s*"[^"]+",?\s*\n', "", blob)


if __name__ == "__main__":
    sys.exit(main())
