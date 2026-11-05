"""Copy scripts/ and rules/ files into the workflow files that use them.

Other repositories that call these workflows can't download files from this private repository,
so each workflow carries its own copy, between "# >>> BEGIN <file>" and "# <<< END <file>" lines.
Run `python3 scripts/build.py` after editing a source file; `--check` fails if a copy is stale.
"""
import re
import sys
from pathlib import Path

WORKFLOWS = [Path(".github/workflows/pr-scan.yml"), Path(".github/workflows/weekly-scan.yml")]
BLOCK = re.compile(r"^( *)(#|//) >>> BEGIN (\S+)([^\n]*)\n.*?^\1\2 <<< END \3\n", re.M | re.S)


def render(m):
    indent, comment, src, note = m.group(1), m.group(2), m.group(3), m.group(4)
    body = Path(src).read_text().rstrip("\n").split("\n")
    if comment == "#":  # shell step: write the file to $RUNNER_TEMP with a quoted heredoc
        body = [f'cat > "$RUNNER_TEMP/{Path(src).name}" <<\'MGE_EOF\''] + body + ["MGE_EOF"]
    lines = [f"{indent}{comment} >>> BEGIN {src}{note}"]
    lines += [(indent + l) if l.strip() else "" for l in body]
    lines += [f"{indent}{comment} <<< END {src}"]
    return "\n".join(lines) + "\n"


stale = []
for wf in WORKFLOWS:
    if not wf.exists():
        continue
    old = wf.read_text()
    new = BLOCK.sub(render, old)
    if new != old:
        stale.append(str(wf))
        if "--check" not in sys.argv:
            wf.write_text(new)
if "--check" in sys.argv and stale:
    sys.exit(f"Out of date: {', '.join(stale)}. Run: python3 scripts/build.py")
print("updated: " + ", ".join(stale) if stale else "up to date")
