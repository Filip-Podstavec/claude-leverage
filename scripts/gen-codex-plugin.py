#!/usr/bin/env python3
"""Generate the Codex plugin artifacts from the Claude manifest pair.

Codex shipped a plugin marketplace whose format is close to Claude Code's, but
the plugin manifest has no legacy fallback (Codex reads ONLY
`.codex-plugin/plugin.json`), and the marketplace schema differs
(`interface.displayName` instead of `owner`, per-plugin `policy`). Rather than
hand-maintain a second + third manifest, we derive them from the Claude source
of truth:

    .claude-plugin/plugin.json       -> .codex-plugin/plugin.json
    .claude-plugin/marketplace.json  -> .agents/plugins/marketplace.json

Run without args to regenerate:
    python scripts/gen-codex-plugin.py

Run with --check to fail (exit 1) if regeneration would change any output file.
CI uses this to enforce parity. --dry-run prints the diff without writing.

Stdlib-only, matching scripts/gen-codex-agents.py.
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_PLUGIN = REPO_ROOT / ".claude-plugin" / "plugin.json"
CLAUDE_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
CODEX_PLUGIN = REPO_ROOT / ".codex-plugin" / "plugin.json"
CODEX_MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
PLUGIN_NAME = "claude-leverage"

# `skills` and `hooks` are documented optional manifest fields (see
# developers.openai.com/codex/plugins/build). Codex defaults already resolve
# skills/ and hooks/hooks.json, but we point at them explicitly so the security
# hooks load deterministically regardless of any future default change.
SKILLS_POINTER = "./skills/"
HOOKS_POINTER = "./hooks/hooks.json"


def build_codex_plugin(plugin_src: dict) -> dict:
    """Map .claude-plugin/plugin.json -> .codex-plugin/plugin.json.

    Carries the descriptive metadata verbatim and adds explicit component
    pointers. Key order here IS the on-disk order (json.dumps preserves it),
    so --check stays stable."""
    out: dict = {
        "name": plugin_src["name"],
        "version": plugin_src["version"],
        "description": plugin_src["description"],
    }
    for key in ("author", "homepage", "repository", "license", "keywords"):
        if key in plugin_src:
            out[key] = plugin_src[key]
    out["skills"] = SKILLS_POINTER
    out["hooks"] = HOOKS_POINTER
    return out


def build_codex_marketplace(marketplace_src: dict) -> dict:
    """Map .claude-plugin/marketplace.json -> .agents/plugins/marketplace.json.

    Claude's per-plugin `source: {source: "url", url: ...}` is already Codex's
    "url" source shape, so it copies through. The transform is: owner ->
    interface.displayName, and add per-plugin policy."""
    out: dict = {"name": marketplace_src["name"]}
    owner = marketplace_src.get("owner", {})
    if owner.get("name"):
        out["interface"] = {"displayName": owner["name"]}

    plugins_out = []
    for entry in marketplace_src.get("plugins", []):
        p: dict = {
            "name": entry["name"],
            "version": entry["version"],
            "description": entry["description"],
            "source": entry["source"],
            # AIDEV-NOTE: no `policy.authentication` — this plugin ships no app
            # integration. Add it (e.g. "ON_INSTALL") only if a Codex
            # test-install proves it's required for an app-less plugin.
            "policy": {"installation": "AVAILABLE"},
        }
        for key in ("category", "keywords"):
            if key in entry:
                p[key] = entry[key]
        plugins_out.append(p)
    out["plugins"] = plugins_out
    return out


def render(obj: dict) -> str:
    """Pretty JSON with a trailing newline (matches the Claude manifests)."""
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def _targets() -> list[tuple[Path, str]]:
    plugin_src = json.loads(CLAUDE_PLUGIN.read_text(encoding="utf-8"))
    marketplace_src = json.loads(CLAUDE_MARKETPLACE.read_text(encoding="utf-8"))
    return [
        (CODEX_PLUGIN, render(build_codex_plugin(plugin_src))),
        (CODEX_MARKETPLACE, render(build_codex_marketplace(marketplace_src))),
    ]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true",
                   help="Exit 1 if any generated file differs from disk. No writes.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the diff vs disk without writing.")
    args = p.parse_args()

    if args.check and args.dry_run:
        print("ERROR: --check and --dry-run are mutually exclusive", file=sys.stderr)
        return 2

    for src in (CLAUDE_PLUGIN, CLAUDE_MARKETPLACE):
        if not src.is_file():
            print(f"missing source {src.relative_to(REPO_ROOT)}", file=sys.stderr)
            return 1

    drift = 0
    written = 0
    for out_path, generated in _targets():
        rel = out_path.relative_to(REPO_ROOT)
        existing = out_path.read_text(encoding="utf-8") if out_path.is_file() else ""

        if existing == generated:
            print(f"OK    {rel} (no change)")
            continue

        if args.check or args.dry_run:
            drift += 1
            label = "DRIFT" if args.check else "WOULD WRITE"
            stream = sys.stderr if args.check else sys.stdout
            print(f"{label} {rel}", file=stream)
            for line in difflib.unified_diff(
                existing.splitlines(keepends=True),
                generated.splitlines(keepends=True),
                fromfile=str(rel) + " (on disk)",
                tofile=str(rel) + " (generated)",
                n=2,
            ):
                stream.write(line)
            continue

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(generated, encoding="utf-8")
        written += 1
        print(f"WRITE {rel}")

    if args.check:
        if drift:
            print(f"\n{drift} file(s) drifted. Re-run without --check to regenerate.",
                  file=sys.stderr)
            return 1
        print("all Codex plugin artifacts match the Claude manifest source")
        return 0
    if args.dry_run:
        print(f"\n{drift} file(s) would change." if drift else "\nno changes.")
        return 0
    print(f"\ngenerated {written} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
