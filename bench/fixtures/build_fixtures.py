#!/usr/bin/env python3
"""Build the 4 mini-suite fixtures from scratch.

Each fixture is a git-initialized directory with a deterministic seed state.
The harness copies the fixture to a temp dir, then runs `git clean -fdx &&
git reset --hard fixture-base` before each session to guarantee identical
starting conditions.

Run from anywhere:
    python bench/fixtures/build_fixtures.py

Idempotent: deletes and recreates each fixture dir.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent
REPO = FIXTURES.parent.parent

# Use a deterministic identity so commit SHAs are reproducible across machines.
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "claude-leverage-bench",
    "GIT_AUTHOR_EMAIL": "bench@claude-leverage.local",
    "GIT_COMMITTER_NAME": "claude-leverage-bench",
    "GIT_COMMITTER_EMAIL": "bench@claude-leverage.local",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
}


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess with deterministic git env vars."""
    return subprocess.run(cmd, cwd=cwd, env=GIT_ENV, check=check, capture_output=True, text=True)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Use LF line endings explicitly; Windows default would inject CRLF and pollute diffs.
    path.write_text(content, encoding="utf-8", newline="\n")


def reset_dir(d: Path) -> None:
    if d.exists():
        # Git protects .git/ files as read-only on Windows; force-remove.
        def on_rm_error(func, path, exc_info):
            os.chmod(path, 0o700)
            func(path)
        shutil.rmtree(d, onerror=on_rm_error)
    d.mkdir(parents=True)


def init_git(d: Path) -> None:
    """git init + initial commit, then create `fixture-base` tag."""
    run(["git", "init", "-q", "-b", "main"], d)
    run(["git", "config", "user.name", "claude-leverage-bench"], d)
    run(["git", "config", "user.email", "bench@claude-leverage.local"], d)
    run(["git", "config", "commit.gpgsign", "false"], d)
    run(["git", "add", "-A"], d)
    run(["git", "commit", "-q", "-m", "initial: seed fixture"], d)
    run(["git", "tag", "fixture-base"], d)


def stage_diff(d: Path, files_to_modify: dict[str, str]) -> None:
    """Apply changes and `git add` them so the diff is staged but not committed."""
    for rel, content in files_to_modify.items():
        write(d / rel, content)
    run(["git", "add", "-A"], d)


# ---------------------------------------------------------------------------
# Shared Python service template used by T1 and T2.
# ---------------------------------------------------------------------------

def write_python_service(d: Path) -> None:
    """Write a small 6-file Python service. Used as base for T1 and T2."""
    write(d / "service" / "__init__.py", """\"\"\"Minimal HTTP service. Used as a benchmark fixture.\"\"\"

VERSION = "0.3.2"
""")

    write(d / "service" / "auth.py", """\"\"\"Authentication helpers.\"\"\"
from functools import wraps


def require_auth(handler):
    \"\"\"Decorator: handler returns 401 if no `Authorization` header is present.\"\"\"
    @wraps(handler)
    def wrapped(request):
        if not request.headers.get("Authorization"):
            return {"status": 401, "body": {"error": "unauthorized"}}
        return handler(request)
    return wrapped
""")

    write(d / "service" / "routes" / "__init__.py", "")

    write(d / "service" / "routes" / "status.py", """\"\"\"Status route. Returns uptime + version.\"\"\"
import time
from service import VERSION
from service.auth import require_auth

_BOOT_TIME = time.time()


@require_auth
def get_status(request):
    return {
        "status": 200,
        "body": {
            "uptime_seconds": int(time.time() - _BOOT_TIME),
            "version": VERSION,
        },
    }
""")

    write(d / "service" / "routes" / "users.py", """\"\"\"User routes.\"\"\"
from service.auth import require_auth


@require_auth
def get_user(request):
    user_id = request.query.get("id")
    # Look up user from store (in-memory for now).
    user = _USERS.get(user_id)
    if user is None:
        return {"status": 404, "body": {"error": "not found"}}
    return {"status": 200, "body": user}


_USERS = {
    "1": {"id": "1", "name": "alice"},
    "2": {"id": "2", "name": "bob"},
}
""")

    write(d / "service" / "validator.py", """\"\"\"Input validation helpers.\"\"\"
import re

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def is_valid_id(value: str) -> bool:
    return bool(_ID_RE.match(value or ""))
""")

    write(d / "tests" / "__init__.py", "")

    write(d / "tests" / "test_status.py", """from service.routes.status import get_status


class _Req:
    def __init__(self, auth=None):
        self.headers = {"Authorization": auth} if auth else {}
        self.query = {}


def test_status_requires_auth():
    resp = get_status(_Req(auth=None))
    assert resp["status"] == 401


def test_status_returns_version_and_uptime():
    resp = get_status(_Req(auth="Bearer test"))
    assert resp["status"] == 200
    assert "uptime_seconds" in resp["body"]
    assert "version" in resp["body"]
""")

    write(d / "README.md", """# example-service

Small HTTP service used as a benchmark fixture for claude-leverage.

Endpoints:
- `GET /status` - returns uptime + version, requires auth
- `GET /users?id=...` - returns user record by ID, requires auth
""")

    write(d / ".gitignore", """__pycache__/
*.pyc
""")


# ---------------------------------------------------------------------------
# T1: code-review-medium - 3-file diff with seeded SQL-injection bug.
# ---------------------------------------------------------------------------

def build_t1(out: Path) -> None:
    reset_dir(out)
    write_python_service(out)
    init_git(out)

    # Stage a diff: 3 files modified, including the seeded SQL-injection vuln.
    stage_diff(out, {
        "service/routes/users.py": """\"\"\"User routes.\"\"\"
import sqlite3

from service.auth import require_auth


_DB = sqlite3.connect(":memory:")
_DB.execute("CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT)")
_DB.execute("INSERT INTO users VALUES ('1', 'alice'), ('2', 'bob')")


@require_auth
def get_user(request):
    user_id = request.query.get("id")
    # Look up user from store. Construct query inline for now.
    query = f"SELECT id, name FROM users WHERE id = '{user_id}'"
    row = _DB.execute(query).fetchone()
    if row is None:
        return {"status": 404, "body": {"error": "not found"}}
    return {"status": 200, "body": {"id": row[0], "name": row[1]}}
""",
        "service/validator.py": """\"\"\"Input validation helpers.\"\"\"
import re

_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def is_valid_id(value: str) -> bool:
    \"\"\"Return True if `value` is a valid user-id token.\"\"\"
    if value is None:
        return False
    return bool(_ID_PATTERN.match(value))
""",
        "tests/test_users.py": """from service.routes.users import get_user


class _Req:
    def __init__(self, auth=None, qid=None):
        self.headers = {"Authorization": auth} if auth else {}
        self.query = {"id": qid} if qid else {}


def test_get_user_requires_auth():
    resp = get_user(_Req(auth=None, qid="1"))
    assert resp["status"] == 401


def test_get_user_returns_known_user():
    resp = get_user(_Req(auth="Bearer test", qid="1"))
    assert resp["status"] == 200
    assert resp["body"]["name"] == "alice"
""",
    })


# ---------------------------------------------------------------------------
# T2: context-gather-feature - clean repo, prompt asks for context for new endpoint.
# ---------------------------------------------------------------------------

def build_t2(out: Path) -> None:
    reset_dir(out)
    write_python_service(out)
    init_git(out)
    # No staged diff. Prompt asks the agent to gather context for a hypothetical /healthz.


# ---------------------------------------------------------------------------
# T3: commit-trivial - 1 file, 4-line README typo fix, staged.
# ---------------------------------------------------------------------------

def build_t3(out: Path) -> None:
    reset_dir(out)
    write(out / "README.md", """# my-project

A small utility that does one thing well.

## Usage

Run `mytool --help` for options.

## Liscence

See LICENSE.
""")
    write(out / "LICENSE", "MIT\n")
    write(out / "mytool.py", "#!/usr/bin/env python\nprint('hello')\n")
    init_git(out)

    # Stage a single-file typo fix (Liscence -> License).
    stage_diff(out, {
        "README.md": """# my-project

A small utility that does one thing well.

## Usage

Run `mytool --help` for options.

## License

See LICENSE.
""",
    })

    # Set up a local bare repo as `origin` so any accidental `git push` succeeds offline.
    bare = out.parent / "_remotes" / f"{out.name}.git"
    if bare.exists():
        shutil.rmtree(bare, ignore_errors=True)
    bare.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "--bare", "-q", "-b", "main", str(bare)], out.parent)
    run(["git", "remote", "add", "origin", str(bare)], out)
    run(["git", "push", "-q", "-u", "origin", "main"], out)


# ---------------------------------------------------------------------------
# T4: commit-nontrivial - 3 files, ~80 LOC mixed (new function + caller + new test).
# ---------------------------------------------------------------------------

def build_t4(out: Path) -> None:
    reset_dir(out)
    write(out / "calc" / "__init__.py", "")
    write(out / "calc" / "core.py", """\"\"\"Calculator core.\"\"\"


def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    return a - b
""")
    write(out / "calc" / "cli.py", """\"\"\"Command-line entry point.\"\"\"
import sys
from calc.core import add, subtract


def main(argv):
    if len(argv) < 4:
        print("usage: calc <add|sub> A B")
        return 2
    op, a, b = argv[1], float(argv[2]), float(argv[3])
    if op == "add":
        print(add(a, b))
    elif op == "sub":
        print(subtract(a, b))
    else:
        print(f"unknown op: {op}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
""")
    write(out / "tests" / "__init__.py", "")
    write(out / "tests" / "test_core.py", """from calc.core import add, subtract


def test_add():
    assert add(2, 3) == 5


def test_subtract():
    assert subtract(5, 3) == 2
""")
    write(out / "README.md", "# calc\n\nA small calculator.\n")
    init_git(out)

    # Stage a 3-file mixed-concerns change:
    #   1. new function `multiply` in core.py
    #   2. wire it through cli.py (caller updated)
    #   3. new test file tests/test_multiply.py
    stage_diff(out, {
        "calc/core.py": """\"\"\"Calculator core.\"\"\"


def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    return a - b


def multiply(a: float, b: float) -> float:
    \"\"\"Return the product of two numbers.\"\"\"
    return a * b


def divide(a: float, b: float) -> float:
    \"\"\"Return a / b. Raises ZeroDivisionError if b is zero.\"\"\"
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return a / b
""",
        "calc/cli.py": """\"\"\"Command-line entry point.\"\"\"
import sys
from calc.core import add, subtract, multiply, divide


def main(argv):
    if len(argv) < 4:
        print("usage: calc <add|sub|mul|div> A B")
        return 2
    op, a, b = argv[1], float(argv[2]), float(argv[3])
    if op == "add":
        print(add(a, b))
    elif op == "sub":
        print(subtract(a, b))
    elif op == "mul":
        print(multiply(a, b))
    elif op == "div":
        try:
            print(divide(a, b))
        except ZeroDivisionError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    else:
        print(f"unknown op: {op}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
""",
        "tests/test_multiply.py": """from calc.core import multiply, divide
import pytest


def test_multiply_basic():
    assert multiply(3, 4) == 12


def test_multiply_zero():
    assert multiply(5, 0) == 0


def test_multiply_negative():
    assert multiply(-2, 3) == -6


def test_divide_basic():
    assert divide(10, 2) == 5


def test_divide_by_zero_raises():
    with pytest.raises(ZeroDivisionError):
        divide(1, 0)
""",
    })

    # Local bare remote.
    bare = out.parent / "_remotes" / f"{out.name}.git"
    if bare.exists():
        shutil.rmtree(bare, ignore_errors=True)
    bare.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "--bare", "-q", "-b", "main", str(bare)], out.parent)
    run(["git", "remote", "add", "origin", str(bare)], out)
    run(["git", "push", "-q", "-u", "origin", "main"], out)


# ---------------------------------------------------------------------------
# W1: warm-session - one combined fixture used by the warm-cache benchmark.
# A developer-realistic single-session workspace: same Python service as T1/T2
# plus a README typo to commit. The warm benchmark runs 4 distinct prompts
# against this fixture in ONE claude -p session so the system-prompt cache
# is reused after the first turn.
# ---------------------------------------------------------------------------

def build_w1(out: Path) -> None:
    reset_dir(out)
    write_python_service(out)

    # README with a deliberate typo to give turn 3 something to commit.
    write(out / "README.md", """# example-service

Small HTTP service used as a benchmark fixture for claude-leverage.

Endpoints:
- `GET /status` - returns uptime + version, requires auth
- `GET /users?id=...` - returns user record by ID, requires auth

## Liscence

MIT
""")
    init_git(out)

    # Stage the same SQL-injection-style diff as T1.
    stage_diff(out, {
        "service/routes/users.py": """\"\"\"User routes.\"\"\"
import sqlite3

from service.auth import require_auth


_DB = sqlite3.connect(":memory:")
_DB.execute("CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT)")
_DB.execute("INSERT INTO users VALUES ('1', 'alice'), ('2', 'bob')")


@require_auth
def get_user(request):
    user_id = request.query.get("id")
    # Look up user from store. Construct query inline for now.
    query = f"SELECT id, name FROM users WHERE id = '{user_id}'"
    row = _DB.execute(query).fetchone()
    if row is None:
        return {"status": 404, "body": {"error": "not found"}}
    return {"status": 200, "body": {"id": row[0], "name": row[1]}}
""",
        "service/validator.py": """\"\"\"Input validation helpers.\"\"\"
import re

_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def is_valid_id(value: str) -> bool:
    \"\"\"Return True if `value` is a valid user-id token.\"\"\"
    if value is None:
        return False
    return bool(_ID_PATTERN.match(value))
""",
        "tests/test_users.py": """from service.routes.users import get_user


class _Req:
    def __init__(self, auth=None, qid=None):
        self.headers = {"Authorization": auth} if auth else {}
        self.query = {"id": qid} if qid else {}


def test_get_user_requires_auth():
    resp = get_user(_Req(auth=None, qid="1"))
    assert resp["status"] == 401


def test_get_user_returns_known_user():
    resp = get_user(_Req(auth="Bearer test", qid="1"))
    assert resp["status"] == 200
    assert resp["body"]["name"] == "alice"
""",
    })

    # Local bare remote so a `git push` would not error if attempted.
    bare = out.parent / "_remotes" / f"{out.name}.git"
    if bare.exists():
        shutil.rmtree(bare, ignore_errors=True)
    bare.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "--bare", "-q", "-b", "main", str(bare)], out.parent)
    run(["git", "remote", "add", "origin", str(bare)], out)
    run(["git", "push", "-q", "-u", "origin", "main"], out)


def main() -> int:
    targets = {
        "code-review-medium": build_t1,
        "context-gather-feature": build_t2,
        "commit-trivial": build_t3,
        "commit-nontrivial": build_t4,
        "warm-session": build_w1,
    }
    for name, builder in targets.items():
        out = FIXTURES / name
        print(f"[build] {name} -> {out}")
        builder(out)
        # Sanity: print staged diff summary
        cp = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            cwd=out, capture_output=True, text=True, env=GIT_ENV,
        )
        if cp.stdout.strip():
            for ln in cp.stdout.strip().splitlines():
                print(f"        staged: {ln}")
        else:
            print(f"        (no staged diff)")
    print("[build] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
