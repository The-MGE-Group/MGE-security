#!/usr/bin/env python3
"""PreToolUse hook on Bash: the commit gate.

Modes (config.json "gate_mode"):
  off      do nothing
  observe  never block; log what WOULD have been blocked to state/gate.log
  enforce  block a `git commit` when this session never ran /verify or /code-review

Escape hatches in enforce mode:
  - put a line "Unverified: <reason>" in the commit message
  - after N blocks in one session (default 2) the next commit is let through,
    so Claude never gets stuck

Every commit is stamped: this hook writes how it was verified to
.git/claude-verified-by and the prepare-commit-msg git hook turns that into a
"Verified-by:" trailer. "none" is a valid stamp, so unverified commits can be queried.
"""
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__file__))
from _common import PROJECT_DIR, git, load_config, load_state, log, read_input, save_state  # noqa: E402

COMMIT = re.compile(r"(^|[;&|(\s])git(\s+-C\s+\S+|\s+-c\s+\S+)*\s+commit\b")
UNVERIFIED = re.compile(r"Unverified:\s*([^\n\"']+)", re.I)


def evidence(transcript_path, markers):
    """Return the first verification marker found in this session's transcript."""
    try:
        text = Path(transcript_path).read_text(errors="ignore")
    except Exception:
        return None
    for m in markers:
        name = re.escape(m)
        pats = [
            rf'"skill"\s*:\s*"(?:[\w-]+:)?{name}"',          # Claude invoked the skill
            rf"<command-name>/?(?:[\w-]+:)?{name}</command-name>",  # user typed /name
        ]
        if any(re.search(p, text) for p in pats):
            return m
    return None


def stamp(value):
    path = git("rev-parse", "--git-path", "claude-verified-by")
    if path:
        p = Path(path)
        if not p.is_absolute():
            p = PROJECT_DIR / p
        p.write_text(value + "\n")


def main():
    data = read_input()
    if data.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = (data.get("tool_input") or {}).get("command", "")
    if not COMMIT.search(cmd):
        sys.exit(0)

    cfg = load_config()
    mode = cfg.get("gate_mode", "observe")
    if mode == "off":
        sys.exit(0)

    session = data.get("session_id", "")
    found = evidence(data.get("transcript_path", ""), cfg["verify_markers"])
    reason = UNVERIFIED.search(cmd)

    if found:
        stamp(found)
        log("commit_verified", mode=mode, by=found, session=session)
        sys.exit(0)

    if reason:
        stamp(f"none ({reason.group(1).strip()[:120]})")
        log("commit_unverified_explained", mode=mode, reason=reason.group(1).strip(), session=session)
        sys.exit(0)

    if mode == "observe":
        stamp("none")
        log("would_block", mode=mode, command=cmd[:300], session=session)
        sys.exit(0)

    # enforce
    state = load_state(session)
    blocks = state.get("commit_blocks", 0)
    if blocks >= cfg["blocks_before_letting_through"]:
        stamp("none (let through after repeated blocks)")
        log("let_through", blocks=blocks, session=session)
        state["commit_blocks"] = 0
        save_state(session, state)
        sys.exit(0)

    state["commit_blocks"] = blocks + 1
    save_state(session, state)
    log("blocked", blocks=blocks + 1, command=cmd[:300], session=session)
    print(
        "Commit blocked: this session has not run /verify or /code-review. "
        "Run the verify skill on this change first. If it truly cannot be verified, "
        "add a line 'Unverified: <reason>' to the commit message.",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
