"""Shared helpers for the verification hooks. Standard library only."""
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
VERIFY_DIR = PROJECT_DIR / ".claude" / "verification"
STATE_DIR = VERIFY_DIR / "state"

DEFAULT_CONFIG = {
    "gate_mode": "observe",
    "check_command": "",
    "max_fix_rounds": 3,
    "blocks_before_letting_through": 2,
    "verify_markers": ["verify", "code-review"],
    "protected_paths": [
        "REVIEW.md",
        ".claude/settings.json",
        ".claude/hooks/*",
        ".claude/verification/config.json",
        ".claude/verification/checklist.md",
        ".github/workflows/verification-integrity.yml",
    ],
}


def read_input():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        cfg.update(json.loads((VERIFY_DIR / "config.json").read_text()))
    except FileNotFoundError:
        pass
    except Exception as exc:  # a broken config must be loud, not silently ignored
        print(f"verification: config.json is not valid JSON ({exc}); using defaults", file=sys.stderr)
    return cfg


def load_state(session_id):
    try:
        return json.loads((STATE_DIR / f"{safe(session_id)}.json").read_text())
    except Exception:
        return {}


def save_state(session_id, state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / f"{safe(session_id)}.json").write_text(json.dumps(state, indent=2))


def log(event, **fields):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_DIR / "gate.log", "a") as fh:
        fh.write(json.dumps({"event": event, **fields}) + "\n")


def safe(text):
    return "".join(c for c in str(text or "no-session") if c.isalnum() or c in "-_")[:80]


def git(*args):
    res = subprocess.run(["git", *args], cwd=PROJECT_DIR, capture_output=True, text=True)
    return res.stdout.strip() if res.returncode == 0 else None


def rel_path(path):
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_DIR / p
    try:
        return p.resolve().relative_to(PROJECT_DIR).as_posix()
    except ValueError:
        return None  # outside the project


def is_protected(rel, patterns):
    return any(fnmatch.fnmatch(rel, pat) for pat in patterns)
