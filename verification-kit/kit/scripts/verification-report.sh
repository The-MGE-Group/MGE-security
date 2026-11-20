#!/usr/bin/env bash
# Are the checks catching what matters? Reads git history only.
#   scripts/verification-report.sh [number-of-commits]   (default 500)
# Shows how commits were verified, and which reverted commits had been verified.
#
# "Verified-by:" lines are read from anywhere in a commit message, because a
# squash merge keeps each original commit's message (and its Verified-by line)
# inside the merged message, where git's trailer parser doesn't look.
set -euo pipefail
n="${1:-500}"

git log -n "$n" -z --format='%H%x1f%s%x1f%B' | python3 -c '
import collections, re, subprocess, sys

STAMP = re.compile(r"^\s*Verified-by:\s*(.+?)\s*$", re.M | re.I)
REVERTS = re.compile(r"This reverts commit ([0-9a-f]{7,40})")

def kind(values):
    """One label per commit: verified, partly, none, or no stamp."""
    if not values:
        return "no stamp (human or pre-kit)"
    unverified = [v for v in values if v.lower().startswith("none")]
    if not unverified:
        return "verified (" + ", ".join(sorted(set(values))) + ")"
    if len(unverified) == len(values):
        return "none"
    return "partly verified"

commits = []
for rec in sys.stdin.read().split("\0"):
    if rec.strip():
        sha, subject, body = rec.lstrip("\n").split("\x1f", 2)
        commits.append((sha, subject, STAMP.findall(body), REVERTS.findall(body)))

print(f"== How the last {len(commits)} commits were verified ==")
counts = collections.Counter(kind(stamps) for _, _, stamps, _ in commits)
for label, count in counts.most_common():
    print(f"{count:6d}  {label}")

print()
print("== Reverted commits and how they had been verified ==")
found = False
for _, _, _, targets in commits:
    for target in targets:
        found = True
        res = subprocess.run(["git", "log", "-1", "--format=%s%x1f%B", target], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"{target[:9]}  (not in this clone; fetch more history)")
            continue
        subject, body = res.stdout.split("\x1f", 1)
        print(f"{target[:9]}  {kind(STAMP.findall(body)):<30} {subject}")
if not found:
    print("(no reverts found)")
print()
print("A verified commit that got reverted is a miss: run /learn-from-miss on it.")
'

echo
echo "== Gate log on this machine (observe mode: what would have been blocked) =="
log=".claude/verification/state/gate.log"
if [ -f "$log" ]; then
  python3 - "$log" <<'PY'
import collections, json, sys
c = collections.Counter(json.loads(l).get("event") for l in open(sys.argv[1]) if l.strip())
for k, v in c.most_common():
    print(f"{v:6d}  {k}")
PY
else
  echo "(none here: the log lives in the session's own machine, so cloud sessions lose it; the Verified-by counts above are the lasting record)"
fi
