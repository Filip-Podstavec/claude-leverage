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


# ---------------------------------------------------------------------------
# T5: code-review-large - 500+ LOC staged diff across multiple files,
# meaningful refactor with seeded issues. Built to test whether subagent
# delegation wins at scale (theoretical break-even ~11k task tokens).
# ---------------------------------------------------------------------------

def build_t5(out: Path) -> None:
    reset_dir(out)
    # Base: a small "task tracker" service with users, tasks, projects, notifications.
    # ~6 modules, ~250 LOC of Python.
    write(out / "tasker" / "__init__.py", '"""Task tracker service."""\n\nVERSION = "1.0.0"\n')
    write(out / "tasker" / "models.py", """\"\"\"Data models.\"\"\"
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    id: str
    email: str
    name: str
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Project:
    id: str
    name: str
    owner_id: str
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Task:
    id: str
    project_id: str
    title: str
    status: str = "open"
    assignee_id: Optional[str] = None
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
""")
    write(out / "tasker" / "db.py", """\"\"\"Database connection helpers.\"\"\"
import sqlite3
from contextlib import contextmanager


_CONN = None


def get_conn(db_path=":memory:"):
    global _CONN
    if _CONN is None:
        _CONN = sqlite3.connect(db_path)
        _CONN.row_factory = sqlite3.Row
        _init_schema(_CONN)
    return _CONN


def _init_schema(conn):
    conn.executescript(\"\"\"
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            assignee_id TEXT,
            description TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (assignee_id) REFERENCES users(id)
        );
    \"\"\")


@contextmanager
def transaction():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
""")
    write(out / "tasker" / "users.py", """\"\"\"User CRUD.\"\"\"
import uuid
from datetime import datetime
from tasker.db import get_conn


def create_user(email, name):
    user_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (id, email, name, created_at) VALUES (?, ?, ?, ?)",
            (user_id, email, name, datetime.now().isoformat()),
        )
    return user_id


def get_user(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def find_by_email(email):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None
""")
    write(out / "tasker" / "projects.py", """\"\"\"Project CRUD.\"\"\"
import uuid
from datetime import datetime
from tasker.db import get_conn


def create_project(name, owner_id, description=""):
    project_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, owner_id, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, name, owner_id, description, datetime.now().isoformat()),
        )
    return project_id


def list_projects_for_user(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM projects WHERE owner_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]
""")
    write(out / "tasker" / "tasks.py", """\"\"\"Task CRUD.\"\"\"
import uuid
from datetime import datetime
from tasker.db import get_conn


def create_task(project_id, title, description="", assignee_id=None):
    task_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO tasks (id, project_id, title, status, assignee_id, description, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (task_id, project_id, title, "open", assignee_id, description, datetime.now().isoformat()),
        )
    return task_id


def list_tasks(project_id, status=None):
    conn = get_conn()
    if status:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE project_id = ? AND status = ? ORDER BY created_at",
            (project_id, status),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE project_id = ? ORDER BY created_at",
            (project_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_status(task_id, new_status):
    valid = {"open", "in_progress", "done", "cancelled"}
    if new_status not in valid:
        raise ValueError(f"invalid status: {new_status}")
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET status = ? WHERE id = ?",
            (new_status, task_id),
        )
""")
    write(out / "tasker" / "api.py", """\"\"\"HTTP API surface (mock).\"\"\"
from tasker import users, projects, tasks


def handle_create_user(request):
    body = request.get("body", {})
    if not body.get("email") or not body.get("name"):
        return {"status": 400, "body": {"error": "email and name required"}}
    user_id = users.create_user(body["email"], body["name"])
    return {"status": 201, "body": {"id": user_id}}


def handle_create_project(request):
    body = request.get("body", {})
    owner_id = request.get("auth", {}).get("user_id")
    if not owner_id:
        return {"status": 401, "body": {"error": "not authenticated"}}
    if not body.get("name"):
        return {"status": 400, "body": {"error": "name required"}}
    project_id = projects.create_project(body["name"], owner_id, body.get("description", ""))
    return {"status": 201, "body": {"id": project_id}}


def handle_create_task(request):
    body = request.get("body", {})
    if not body.get("project_id") or not body.get("title"):
        return {"status": 400, "body": {"error": "project_id and title required"}}
    task_id = tasks.create_task(
        body["project_id"], body["title"],
        body.get("description", ""),
        body.get("assignee_id"),
    )
    return {"status": 201, "body": {"id": task_id}}
""")
    write(out / "tests" / "__init__.py", "")
    write(out / "tests" / "test_users.py", """from tasker.users import create_user, get_user, find_by_email


def test_create_and_get_user():
    uid = create_user("alice@example.com", "Alice")
    user = get_user(uid)
    assert user["email"] == "alice@example.com"


def test_find_by_email():
    create_user("bob@example.com", "Bob")
    u = find_by_email("bob@example.com")
    assert u["name"] == "Bob"
""")
    write(out / "tests" / "test_tasks.py", """from tasker.users import create_user
from tasker.projects import create_project
from tasker.tasks import create_task, list_tasks, update_status


def test_create_task():
    uid = create_user("charlie@example.com", "Charlie")
    pid = create_project("Test project", uid)
    tid = create_task(pid, "Do a thing")
    found = list_tasks(pid)
    assert len(found) == 1
    assert found[0]["id"] == tid


def test_update_status():
    uid = create_user("dana@example.com", "Dana")
    pid = create_project("P", uid)
    tid = create_task(pid, "T")
    update_status(tid, "done")
    found = list_tasks(pid, status="done")
    assert len(found) == 1
""")
    write(out / "README.md", "# tasker\n\nSmall task tracker with users, projects, and tasks.\n")
    write(out / ".gitignore", "__pycache__/\n*.pyc\n")
    init_git(out)

    # Now stage a LARGE refactor diff: ~500 LOC of changes across 5+ files.
    # Adds: caching layer, pagination, soft-delete, audit logging.
    # Seeds: SQL injection in tasks.py search, race condition in projects.py,
    #        missing transaction in users.create, unsanitized email log.
    stage_diff(out, {
        "tasker/cache.py": """\"\"\"In-memory cache with TTL and audit logging.\"\"\"
import time
from threading import Lock


_CACHE = {}
_LOCK = Lock()
_DEFAULT_TTL = 300


def get(key):
    with _LOCK:
        entry = _CACHE.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del _CACHE[key]
            return None
        return value


def set(key, value, ttl=_DEFAULT_TTL):
    with _LOCK:
        _CACHE[key] = (value, time.time() + ttl)


def delete(key):
    with _LOCK:
        _CACHE.pop(key, None)


def clear():
    with _LOCK:
        _CACHE.clear()


def stats():
    return {"size": len(_CACHE), "keys": list(_CACHE.keys())}
""",
        "tasker/audit.py": """\"\"\"Audit logging — records who did what.\"\"\"
import json
import os
from datetime import datetime


AUDIT_LOG_PATH = os.environ.get("TASKER_AUDIT_LOG", "/tmp/tasker-audit.log")


def log_action(actor_id, action, target_type, target_id, metadata=None):
    \"\"\"Record an action in the audit log.\"\"\"
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "actor_id": actor_id,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "metadata": metadata or {},
    }
    # SECURITY: log raw email if present in metadata — useful for tracing
    if metadata and "email" in metadata:
        print(f"AUDIT: {actor_id} did {action} on {target_type}/{target_id} (email={metadata['email']})")
    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\\n")


def read_recent(limit=100):
    \"\"\"Read the most recent N audit entries.\"\"\"
    if not os.path.exists(AUDIT_LOG_PATH):
        return []
    entries = []
    with open(AUDIT_LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries[-limit:]
""",
        "tasker/users.py": """\"\"\"User CRUD with soft-delete and audit logging.\"\"\"
import uuid
from datetime import datetime
from tasker.db import get_conn
from tasker import cache, audit


def create_user(email, name, actor_id=None):
    user_id = str(uuid.uuid4())
    # NOTE: no transaction here — if audit log fails after insert, user exists but unaudited
    conn = get_conn()
    conn.execute(
        "INSERT INTO users (id, email, name, created_at) VALUES (?, ?, ?, ?)",
        (user_id, email, name, datetime.now().isoformat()),
    )
    conn.commit()
    audit.log_action(actor_id or user_id, "create", "user", user_id, {"email": email})
    cache.set(f"user:{user_id}", {"id": user_id, "email": email, "name": name})
    return user_id


def get_user(user_id):
    cached = cache.get(f"user:{user_id}")
    if cached is not None:
        return cached
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ? AND deleted_at IS NULL", (user_id,)).fetchone()
    if row:
        result = dict(row)
        cache.set(f"user:{user_id}", result)
        return result
    return None


def find_by_email(email):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ? AND deleted_at IS NULL", (email,)).fetchone()
    return dict(row) if row else None


def soft_delete_user(user_id, actor_id):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET deleted_at = ? WHERE id = ?",
        (datetime.now().isoformat(), user_id),
    )
    conn.commit()
    cache.delete(f"user:{user_id}")
    audit.log_action(actor_id, "delete", "user", user_id)


def list_users(limit=50, offset=0):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM users WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]
""",
        "tasker/projects.py": """\"\"\"Project CRUD with caching, pagination, and soft-delete.\"\"\"
import uuid
from datetime import datetime
from tasker.db import get_conn
from tasker import cache, audit


def create_project(name, owner_id, description="", actor_id=None):
    project_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, owner_id, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, name, owner_id, description, datetime.now().isoformat()),
        )
    audit.log_action(actor_id or owner_id, "create", "project", project_id)
    cache.delete(f"projects:user:{owner_id}")
    return project_id


def list_projects_for_user(user_id, limit=50, offset=0):
    cache_key = f"projects:user:{user_id}:{limit}:{offset}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM projects WHERE owner_id = ? AND deleted_at IS NULL ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (user_id, limit, offset),
    ).fetchall()
    result = [dict(r) for r in rows]
    cache.set(cache_key, result, ttl=60)
    return result


def soft_delete_project(project_id, actor_id):
    # RACE: cache cleared before db update — another reader may repopulate the cache
    # with stale (non-deleted) data between these two lines
    cache.delete(f"project:{project_id}")
    conn = get_conn()
    conn.execute(
        "UPDATE projects SET deleted_at = ? WHERE id = ?",
        (datetime.now().isoformat(), project_id),
    )
    conn.commit()
    audit.log_action(actor_id, "delete", "project", project_id)
""",
        "tasker/tasks.py": """\"\"\"Task CRUD with status transitions, pagination, and search.\"\"\"
import uuid
from datetime import datetime
from tasker.db import get_conn
from tasker import cache, audit


VALID_STATUSES = {"open", "in_progress", "done", "cancelled"}


def create_task(project_id, title, description="", assignee_id=None, actor_id=None):
    task_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO tasks (id, project_id, title, status, assignee_id, description, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (task_id, project_id, title, "open", assignee_id, description, datetime.now().isoformat()),
        )
    audit.log_action(actor_id or assignee_id or "system", "create", "task", task_id)
    cache.delete(f"tasks:project:{project_id}")
    return task_id


def list_tasks(project_id, status=None, limit=50, offset=0):
    cache_key = f"tasks:project:{project_id}:{status or 'all'}:{limit}:{offset}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    conn = get_conn()
    if status:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE project_id = ? AND status = ? AND deleted_at IS NULL ORDER BY created_at LIMIT ? OFFSET ?",
            (project_id, status, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE project_id = ? AND deleted_at IS NULL ORDER BY created_at LIMIT ? OFFSET ?",
            (project_id, limit, offset),
        ).fetchall()
    result = [dict(r) for r in rows]
    cache.set(cache_key, result, ttl=60)
    return result


def search_tasks(project_id, query):
    \"\"\"Search task titles by substring.\"\"\"
    # SECURITY: query is user input; building SQL string with f-string allows injection
    conn = get_conn()
    sql = f"SELECT * FROM tasks WHERE project_id = '{project_id}' AND title LIKE '%{query}%' AND deleted_at IS NULL"
    rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


def update_status(task_id, new_status, actor_id=None):
    if new_status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {new_status}")
    conn = get_conn()
    row = conn.execute("SELECT project_id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        raise ValueError(f"task not found: {task_id}")
    with get_conn() as conn:
        conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
    audit.log_action(actor_id or "system", "status_change", "task", task_id, {"new_status": new_status})
    cache.delete(f"tasks:project:{row['project_id']}")
""",
        "tasker/api.py": """\"\"\"HTTP API surface with auth, pagination, and audit logging.\"\"\"
from tasker import users, projects, tasks, audit


def _require_auth(request):
    auth = request.get("auth", {})
    if not auth.get("user_id"):
        return None
    return auth["user_id"]


def handle_create_user(request):
    actor_id = _require_auth(request)
    body = request.get("body", {})
    if not body.get("email") or not body.get("name"):
        return {"status": 400, "body": {"error": "email and name required"}}
    user_id = users.create_user(body["email"], body["name"], actor_id=actor_id)
    return {"status": 201, "body": {"id": user_id}}


def handle_get_user(request, user_id):
    if not _require_auth(request):
        return {"status": 401, "body": {"error": "not authenticated"}}
    user = users.get_user(user_id)
    if not user:
        return {"status": 404, "body": {"error": "user not found"}}
    return {"status": 200, "body": user}


def handle_create_project(request):
    owner_id = _require_auth(request)
    if not owner_id:
        return {"status": 401, "body": {"error": "not authenticated"}}
    body = request.get("body", {})
    if not body.get("name"):
        return {"status": 400, "body": {"error": "name required"}}
    project_id = projects.create_project(body["name"], owner_id, body.get("description", ""), actor_id=owner_id)
    return {"status": 201, "body": {"id": project_id}}


def handle_list_projects(request):
    user_id = _require_auth(request)
    if not user_id:
        return {"status": 401, "body": {"error": "not authenticated"}}
    qs = request.get("query", {})
    limit = int(qs.get("limit", 50))
    offset = int(qs.get("offset", 0))
    return {"status": 200, "body": projects.list_projects_for_user(user_id, limit=limit, offset=offset)}


def handle_create_task(request):
    actor_id = _require_auth(request)
    if not actor_id:
        return {"status": 401, "body": {"error": "not authenticated"}}
    body = request.get("body", {})
    if not body.get("project_id") or not body.get("title"):
        return {"status": 400, "body": {"error": "project_id and title required"}}
    task_id = tasks.create_task(
        body["project_id"], body["title"],
        body.get("description", ""),
        body.get("assignee_id"),
        actor_id=actor_id,
    )
    return {"status": 201, "body": {"id": task_id}}


def handle_search_tasks(request, project_id):
    if not _require_auth(request):
        return {"status": 401, "body": {"error": "not authenticated"}}
    query = request.get("query", {}).get("q", "")
    return {"status": 200, "body": tasks.search_tasks(project_id, query)}


def handle_audit_log(request):
    actor_id = _require_auth(request)
    if not actor_id:
        return {"status": 401, "body": {"error": "not authenticated"}}
    return {"status": 200, "body": audit.read_recent(limit=100)}
""",
        "tasker/db.py": """\"\"\"Database connection helpers with soft-delete schema.\"\"\"
import sqlite3
from contextlib import contextmanager


_CONN = None


def get_conn(db_path=":memory:"):
    global _CONN
    if _CONN is None:
        _CONN = sqlite3.connect(db_path)
        _CONN.row_factory = sqlite3.Row
        _init_schema(_CONN)
    return _CONN


def _init_schema(conn):
    conn.executescript(\"\"\"
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            deleted_at TEXT
        );
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            deleted_at TEXT,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            assignee_id TEXT,
            description TEXT,
            created_at TEXT NOT NULL,
            deleted_at TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (assignee_id) REFERENCES users(id)
        );
    \"\"\")


@contextmanager
def transaction():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
""",
    })


# ---------------------------------------------------------------------------
# L1: long-session - clean Python service for the 12-turn long-session
# benchmark. No staged diff; the developer-day workflow adds, reviews, fixes,
# and commits over the course of the session.
# ---------------------------------------------------------------------------

def build_l1(out: Path) -> None:
    reset_dir(out)
    write_python_service(out)
    init_git(out)

    # Local bare remote so a `git push` from inside the session does not error.
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
        "long-session": build_l1,
        "code-review-large": build_t5,
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
