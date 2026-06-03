"""Parse a repo's conventions.yml into a normalized profile, and match a file
path to its directory role. Stdlib-only: uses PyYAML when importable, else a
minimal block-YAML parser for the documented (block-style) schema.
"""
from __future__ import annotations

try:
    import yaml as _yaml
except Exception:
    _yaml = None


def _strip_comment(line: str) -> str:
    out, in_q = [], ""
    for ch in line:
        if in_q:
            out.append(ch)
            if ch == in_q:
                in_q = ""
        elif ch in ('"', "'"):
            in_q = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


def _minimal_parse(text: str):
    """Indentation block-YAML parser for the documented schema. Decides each
    key's container type (map vs list) lazily from its first child line, so
    `key:` followed by `- item` becomes a list, not an empty map."""
    root: dict = {}
    stack = [(-1, root)]          # (indent, container)
    pending = None                # (parent_dict, key, indent) awaiting first child
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        body = line.strip()

        if pending is not None:
            p_dict, p_key, p_indent = pending
            if indent > p_indent:
                container = [] if body.startswith("- ") else {}
                p_dict[p_key] = container
                stack.append((p_indent, container))
            else:
                p_dict[p_key] = {}   # key with no children
            pending = None

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if body.startswith("- "):
            if isinstance(parent, list):
                parent.append(_unquote(body[2:]))
            continue
        if body.endswith(":"):
            key = _unquote(body[:-1])
            if isinstance(parent, dict):
                pending = (parent, key, indent)
            continue
        # key: value — find the ':' separating key from value, respecting quotes
        depth_q = ""
        split_at = -1
        for i, ch in enumerate(body):
            if depth_q:
                if ch == depth_q:
                    depth_q = ""
            elif ch in ('"', "'"):
                depth_q = ch
            elif ch == ":":
                split_at = i
                break
        if split_at < 0:
            continue
        key = _unquote(body[:split_at])
        val_raw = body[split_at + 1:].strip()
        if isinstance(parent, dict):
            parent[key] = _unquote(val_raw) if val_raw else {}
    return root


def _normalize(data):
    if not isinstance(data, dict) or not data:
        return None
    naming = data.get("naming") or {}
    structure = data.get("structure") or {}
    prof = {
        "casing": dict(naming.get("casing") or {}),
        "vague_denylist": list(naming.get("vague_denylist") or []),
        "structure_roots": dict(structure.get("roots") or {}),
        "consistency": list(data.get("consistency") or []),
    }
    if not any(prof.values()):
        return None
    return prof


def parse_conventions(text: str):
    """Return a normalized profile dict or None if absent/empty/unparseable."""
    if not text or not text.strip():
        return None
    if _yaml is not None:
        try:
            return _normalize(_yaml.safe_load(text))
        except Exception:
            pass
    try:
        return _normalize(_minimal_parse(text))
    except Exception:
        return None


# AIDEV-NOTE: canonical longest-prefix role match; the context-surface hook mirrors this inline (can't import across the bash heredoc boundary).
def match_role(file_rel: str, roots: dict):
    """Longest-prefix match of file_rel against the structure.roots keys."""
    best_key = None
    for key in roots:
        if file_rel.startswith(key) and (best_key is None or len(key) > len(best_key)):
            best_key = key
    return roots.get(best_key) if best_key is not None else None
