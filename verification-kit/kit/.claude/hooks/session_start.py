#!/usr/bin/env python3
"""SessionStart hook: install the git hook that stamps Claude's commits.

Git doesn't share hooks, and cloud sessions start from a fresh clone, so this
puts .claude/hooks/prepare-commit-msg into the clone's git hooks folder at the
start of every session. It never replaces a different hook that's already there.
"""
import shutil
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__file__))
from pathlib import Path  # noqa: E402

from _common import PROJECT_DIR, git  # noqa: E402

src = Path(__file__).with_name("prepare-commit-msg")
hooks = git("rev-parse", "--git-path", "hooks")
if hooks and src.exists():
    dst = Path(hooks) if Path(hooks).is_absolute() else PROJECT_DIR / hooks
    dst.mkdir(parents=True, exist_ok=True)
    target = dst / "prepare-commit-msg"
    if not target.exists() or "claude-verified-by" in target.read_text(errors="ignore"):
        shutil.copyfile(src, target)
        target.chmod(0o755)
    else:
        print("verification: a different prepare-commit-msg hook exists; Verified-by stamps are off", file=sys.stderr)
sys.exit(0)
