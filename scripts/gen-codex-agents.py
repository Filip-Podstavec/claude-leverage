#!/usr/bin/env python3
"""Generate .codex/agents/*.toml from agents/*.md.

Reads each Claude subagent definition (Markdown with YAML frontmatter) and
emits the equivalent Codex TOML. The fields shift:

    Claude (YAML frontmatter)          Codex (TOML)
    --------------------------          -------------------------
    name: <name>                        name = "<name>"
    description: <text>                 description = "<text>"
    tools: <comma list>                 allowed_tools array (best effort)
    model: <sonnet|haiku|opus>          model = "<claude-sonnet-4-6 | ...>"
    <body after frontmatter>            developer_instructions multi-line

Run without args to regenerate all agents:
    python scripts/gen-codex-agents.py

Run with --check to fail (exit 1) if regeneration would change any output
file. CI uses this to enforce parity.

Run with --agent <name> to regenerate just one.

The script is intentionally stdlib-only (no PyYAML, no tomli_w). Frontmatter
is the same hand-rolled YAML subset that tests/test_agent_command_frontmatter.py
parses; TOML output is a small string template.
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
CODEX_OUT = REPO_ROOT / ".codex" / "agents"

# AIDEV-NOTE: model id mapping. The Codex CLI accepts model strings; pick
# the most recent Claude family members. Update here when Anthropic ships
# new model versions.
MODEL_MAP = {
    "opus": "claude-opus-4-7",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Same hand-rolled YAML-subset parser as tests/test_agent_command_frontmatter.py.

    Returns (fields, body) where body is everything after the closing '---'.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("file does not start with '---' frontmatter")
    end_idx = -1
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_idx = i
            break
    if end_idx == -1:
        raise ValueError("unterminated frontmatter")
    fields: dict[str, str] = {}
    for line in lines[1:end_idx]:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1]
        fields[key.strip()] = value
    body = "\n".join(lines[end_idx + 1 :]).strip()
    return fields, body


def toml_escape_basic(s: str) -> str:
    """Escape for a TOML basic string ("..."). Newlines and quotes escape."""
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "")
        .replace("\t", "\\t")
    )


def toml_multiline_escape(s: str) -> str:
    """Escape for a TOML multi-line basic string ("\"\"...\"\""). Only
    backslash and the closing delimiter need escaping; newlines stay raw."""
    s = s.replace("\\", "\\\\")
    # Guard against '"""' appearing in body, which would close the string.
    s = s.replace('"""', '\\"\\"\\"')
    return s


def render_toml(fields: dict[str, str], body: str) -> str:
    name = fields.get("name", "").strip()
    if not name:
        raise ValueError("frontmatter has no 'name'")
    description = fields.get("description", "").strip()
    tools_raw = fields.get("tools", "").strip()
    # Without a tools field we can't reason about sandbox_mode (the heuristic
    # below would silently default to read-only, which is the safest but
    # invisible decision). Require the field explicitly — the Claude pytest
    # `test_agent_required_fields` already enforces it on the MD side.
    if not tools_raw:
        raise ValueError(
            "frontmatter has no 'tools' field — add it to the agent .md "
            "before regenerating Codex parity"
        )
    model_short = fields.get("model", "").strip().lower()
    model_full = MODEL_MAP.get(model_short, model_short)

    # tools field: try to split on commas, strip trailing parens-arguments
    # like "Bash(git diff:*)" → "Bash" only for the array. (Codex uses
    # tool-name allowlist; the per-arg restriction is not in the spec.)
    if tools_raw:
        raw_items = [t.strip() for t in tools_raw.split(",") if t.strip()]
        # Strip parenthetical sub-restrictions for the Codex array.
        base_tools = sorted({re.sub(r"\(.*\)", "", t).strip() for t in raw_items})
    else:
        base_tools = []

    lines: list[str] = []
    lines.append("# Generated from agents/{n}.md by scripts/gen-codex-agents.py".format(n=name))
    lines.append("# Do not edit by hand — re-run the generator after modifying the MD source.")
    lines.append("")
    lines.append(f'name = "{toml_escape_basic(name)}"')
    if description:
        lines.append(f'description = "{toml_escape_basic(description)}"')
    if model_full:
        lines.append(f'model = "{toml_escape_basic(model_full)}"')
    if base_tools:
        tools_arr = ", ".join(f'"{toml_escape_basic(t)}"' for t in base_tools)
        lines.append(f"allowed_tools = [{tools_arr}]")
    # AIDEV-NOTE: read-only subagents should declare sandbox_mode=read-only
    # so Codex enforces it regardless of the model behaving. Heuristic:
    # if the original tools list contains no Write/Edit/MultiEdit, set
    # sandbox_mode = "read-only".
    write_capable = any(
        tool.startswith(("Write", "Edit", "MultiEdit", "NotebookEdit"))
        for tool in (re.sub(r"\(.*\)", "", t).strip() for t in tools_raw.split(","))
    )
    if not write_capable:
        lines.append('sandbox_mode = "read-only"')

    lines.append("")
    lines.append("developer_instructions = \"\"\"")
    lines.append(toml_multiline_escape(body))
    lines.append("\"\"\"")
    return "\n".join(lines).rstrip() + "\n"


def regenerate(agent_path: Path) -> tuple[Path, str]:
    text = agent_path.read_text(encoding="utf-8")
    fields, body = parse_frontmatter(text)
    out_path = CODEX_OUT / (agent_path.stem + ".toml")
    return out_path, render_toml(fields, body)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true",
                   help="Exit 1 if any generated file differs from disk. No writes.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would be written (and the diff vs disk) without writing.")
    p.add_argument("--agent", metavar="NAME",
                   help="Regenerate only the agent with this name (stem of the .md file).")
    args = p.parse_args()

    if args.check and args.dry_run:
        print("ERROR: --check and --dry-run are mutually exclusive "
              "(both already imply 'no writes')", file=sys.stderr)
        return 2

    CODEX_OUT.mkdir(parents=True, exist_ok=True)

    if not AGENTS_DIR.is_dir():
        print(f"no agents/ dir found at {AGENTS_DIR}", file=sys.stderr)
        return 1

    md_files = sorted(p for p in AGENTS_DIR.glob("*.md") if p.name.lower() != "readme.md")
    if args.agent:
        md_files = [p for p in md_files if p.stem == args.agent]
        if not md_files:
            print(f"no agent named {args.agent!r} in {AGENTS_DIR}", file=sys.stderr)
            return 1

    drift = 0
    written = 0
    would_write = 0
    for src in md_files:
        try:
            out_path, generated = regenerate(src)
        except Exception as e:
            print(f"ERROR processing {src.name}: {e}", file=sys.stderr)
            return 1
        existing = out_path.read_text(encoding="utf-8") if out_path.is_file() else ""
        rel = out_path.relative_to(REPO_ROOT)

        if existing == generated:
            print(f"OK    {rel} (no change)")
            continue

        if args.check:
            drift += 1
            print(f"DRIFT {rel}", file=sys.stderr)
            for line in difflib.unified_diff(
                existing.splitlines(keepends=True),
                generated.splitlines(keepends=True),
                fromfile=str(rel) + " (on disk)",
                tofile=str(rel) + " (generated)",
                n=2,
            ):
                sys.stderr.write(line)
            continue

        if args.dry_run:
            would_write += 1
            status = "WOULD CREATE" if not existing else "WOULD UPDATE"
            print(f"{status} {rel}")
            # Show the diff so the user sees what would change.
            for line in difflib.unified_diff(
                existing.splitlines(keepends=True),
                generated.splitlines(keepends=True),
                fromfile=str(rel) + " (on disk)",
                tofile=str(rel) + " (would write)",
                n=2,
            ):
                sys.stdout.write(line)
            continue

        out_path.write_text(generated, encoding="utf-8")
        written += 1
        print(f"WRITE {rel}")

    if args.check:
        if drift:
            print(f"\n{drift} file(s) drifted. Re-run without --check to regenerate.", file=sys.stderr)
            return 1
        print("all .codex/agents/*.toml match agents/*.md sources")
        return 0
    if args.dry_run:
        if would_write == 0:
            print("\nno changes would be written.")
        else:
            print(f"\n{would_write} file(s) would be written. Re-run without --dry-run to apply.")
        return 0
    print(f"\ngenerated {written} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
