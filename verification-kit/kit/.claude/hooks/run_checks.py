#!/usr/bin/env python3
"""Stop hook: run the cheap checks (tests, build, lint) when Claude finishes.

- Skips when check_command is empty, or when nothing changed since the last pass.
- On failure, blocks Claude from stopping and hands it the output (exit 2).
- After max_fix_rounds failures in a row (default 3) it stops trying and tells
  the human, because a check that keeps failing needs a person.
"""
import hashlib
import json
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__file__))
from _common import PROJECT_DIR, git, load_config, load_state, log, read_input, save_state  # noqa: E402


def fingerprint():
    head = git("rev-parse", "HEAD")
    if head is None:
        return None  # not a git repo: always run
    h = hashlib.sha256(head.encode())
    h.update((git("diff", "HEAD") or "").encode())
    for name in (git("ls-files", "--others", "--exclude-standard") or "").splitlines():
        if name.startswith(".claude/verification/state/"):
            continue
        try:
            h.update(name.encode() + (PROJECT_DIR / name).read_bytes())
        except Exception:
            h.update(name.encode())
    return h.hexdigest()


def main():
    data = read_input()
    cfg = load_config()
    cmd = (cfg.get("check_command") or "").strip()
    if not cmd:
        sys.exit(0)

    session = data.get("session_id", "")
    state = load_state(session)
    fp = fingerprint()
    if fp and fp == state.get("last_pass"):
        sys.exit(0)

    # Exception approved by the owner (2026-11-20): the command is the project's own check
    # command from config.json, which Claude may not edit and CI guards (protected_paths).
    # nosemgrep: subprocess-shell-true, dangerous-subprocess-use-audit -- runs the protected check_command
    res = subprocess.run(cmd, shell=True, cwd=PROJECT_DIR, capture_output=True, text=True)
    if res.returncode == 0:
        state.update(last_pass=fp, fail_rounds=0)
        save_state(session, state)
        log("checks_passed", session=session)
        sys.exit(0)

    rounds = state.get("fail_rounds", 0) + 1
    tail = (res.stdout + "\n" + res.stderr).strip()[-4000:]
    limit = cfg["max_fix_rounds"]

    if rounds >= limit:
        state["fail_rounds"] = 0  # the next turn, after the human weighs in, gets fresh rounds
        save_state(session, state)
        log("checks_gave_up", rounds=rounds, session=session)
        print(json.dumps({
            "systemMessage": f"Checks still fail after {rounds} fix rounds. A human needs to look: `{cmd}`",
            "hookSpecificOutput": {
                "hookEventName": "Stop",
                "additionalContext": (
                    f"`{cmd}` still fails after {rounds} rounds. Stop fixing. Tell the user what fails, "
                    "what you tried, and your best guess at the cause.\n\n" + tail),
            },
        }))
        sys.exit(0)

    state["fail_rounds"] = rounds
    save_state(session, state)
    log("checks_failed", round=rounds, session=session)
    print(
        f"Checks failed (round {rounds} of {limit}): `{cmd}`\n"
        "Fix the code, not the test. Do not skip tests, add sleeps, or retry until green.\n\n" + tail,
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
