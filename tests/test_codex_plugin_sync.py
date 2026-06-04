"""The generated Codex plugin artifacts must stay in sync with the Claude
manifest pair that is their single source of truth.

Mirrors the contract that CI enforces with `gen-codex-plugin.py --check`, but
as importable unit tests so a drift shows up in the normal pytest run too.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GEN_PATH = REPO_ROOT / "scripts" / "gen-codex-plugin.py"
CODEX_PLUGIN = REPO_ROOT / ".codex-plugin" / "plugin.json"
CODEX_MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
CLAUDE_PLUGIN = REPO_ROOT / ".claude-plugin" / "plugin.json"
CLAUDE_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
PLUGIN_NAME = "claude-leverage"


def _load_generator():
    spec = importlib.util.spec_from_file_location("gen_codex_plugin", GEN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_codex_plugin_manifest_matches_generator():
    gen = _load_generator()
    plugin_src = _read_json(CLAUDE_PLUGIN)
    expected = gen.build_codex_plugin(plugin_src)
    assert _read_json(CODEX_PLUGIN) == expected, (
        "Run: python scripts/gen-codex-plugin.py"
    )


def test_codex_marketplace_matches_generator():
    gen = _load_generator()
    marketplace_src = _read_json(CLAUDE_MARKETPLACE)
    expected = gen.build_codex_marketplace(marketplace_src)
    assert _read_json(CODEX_MARKETPLACE) == expected, (
        "Run: python scripts/gen-codex-plugin.py"
    )


def test_versions_agree_across_all_manifests():
    claude_v = _read_json(CLAUDE_PLUGIN)["version"]
    codex_v = _read_json(CODEX_PLUGIN)["version"]
    entry = next(
        p for p in _read_json(CODEX_MARKETPLACE)["plugins"]
        if p["name"] == PLUGIN_NAME
    )
    assert claude_v == codex_v == entry["version"]
