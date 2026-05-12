#!/usr/bin/env python3
"""Assert that .claude-plugin/plugin.json and .claude-plugin/marketplace.json
report the same version for the claude-leverage plugin.

Recent v0.9.x patches were all release-time bookkeeping (literal backticks,
sanitize_int, secret patterns) and manual two-file version bumps are exactly
the kind of thing that drifts silently. This script is intended to run in CI
on every PR and on push to main.

Exit codes:
    0 = versions match
    1 = mismatch or structural problem (missing file, missing key, etc.)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
PLUGIN_NAME = "claude-leverage"


def fail(msg: str) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return 1


def main() -> int:
    for path in (PLUGIN_JSON, MARKETPLACE_JSON):
        if not path.is_file():
            return fail(f"missing {path.relative_to(REPO_ROOT)}")

    try:
        plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
        marketplace = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return fail(f"invalid JSON: {e}")

    plugin_version = plugin.get("version")
    if not isinstance(plugin_version, str) or not plugin_version:
        return fail("plugin.json: missing or non-string 'version'")

    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        return fail("marketplace.json: 'plugins' must be a list")

    entries = [p for p in plugins if isinstance(p, dict) and p.get("name") == PLUGIN_NAME]
    if not entries:
        return fail(f"marketplace.json: no entry with name == {PLUGIN_NAME!r}")
    if len(entries) > 1:
        return fail(f"marketplace.json: multiple entries with name == {PLUGIN_NAME!r}")

    marketplace_version = entries[0].get("version")
    if not isinstance(marketplace_version, str) or not marketplace_version:
        return fail("marketplace.json: missing or non-string 'version' for claude-leverage")

    if plugin_version != marketplace_version:
        return fail(
            f"version mismatch: plugin.json={plugin_version!r}, "
            f"marketplace.json={marketplace_version!r}"
        )

    print(f"OK: versions in sync ({plugin_version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
