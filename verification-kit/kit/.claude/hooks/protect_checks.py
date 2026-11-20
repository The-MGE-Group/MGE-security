#!/usr/bin/env python3
"""PreToolUse hook: a change may not edit the checks that judge it.

Blocks Edit/Write/MultiEdit/NotebookEdit on protected paths, and Bash commands
that look like they write to one. The Bash check is best effort (a determined
script can get around it); CODEOWNERS plus the CI integrity job are the real lock.
"""
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__file__))
from _common import is_protected, load_config, log, read_input, rel_path  # noqa: E402

# Commands that change files. A plain ">" only counts when it points at the protected path.
WRITE_OPS = re.compile(r"(\btee\b|\bsed\s+-i|\bperl\s+-p?i|\bmv\b|\brm\b|\bcp\b|\btruncate\b|\bchmod\b|\bln\b|\bgit\s+(checkout|restore)\b)")


def deny(reason):
    print(reason, file=sys.stderr)
    sys.exit(2)


def main():
    data = read_input()
    tool = data.get("tool_name", "")
    tin = data.get("tool_input") or {}
    patterns = load_config()["protected_paths"]
    msg = ("{path} is part of the verification layer, so a change may not edit it. "
           "If it really needs to change, stop and ask the human to edit it in a separate, reviewed PR.")

    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        target = tin.get("file_path") or tin.get("notebook_path") or ""
        rel = rel_path(target) if target else None
        if rel and is_protected(rel, patterns):
            log("protected_edit_blocked", tool=tool, path=rel, session=data.get("session_id"))
            deny(msg.format(path=rel))

    elif tool == "Bash":
        cmd = tin.get("command", "")
        for pat in patterns:
            literal = pat.split("*")[0].rstrip("/")
            if not literal or literal not in cmd:
                continue
            redirect = re.search(r">>?\s*['\"]?\S*" + re.escape(literal), cmd)
            if redirect or WRITE_OPS.search(cmd):
                    log("protected_bash_blocked", path=pat, command=cmd[:300], session=data.get("session_id"))
                    deny(msg.format(path=pat) + " (Blocked because this shell command seems to write to it.)")
    sys.exit(0)


if __name__ == "__main__":
    main()
