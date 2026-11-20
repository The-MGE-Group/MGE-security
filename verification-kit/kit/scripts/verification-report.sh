#!/usr/bin/env bash
# Are the checks catching what matters? Reads git history only.
#   scripts/verification-report.sh [number-of-commits]   (default 500)
# Shows how commits were verified, and which reverted commits had been verified.
set -euo pipefail
n="${1:-500}"

echo "== How the last $n commits were verified (Verified-by trailer) =="
git log -n "$n" --format='%(trailers:key=Verified-by,valueonly,separator=%x2C)' \
  | sed 's/ (.*//; s/^$/(no trailer: human or pre-kit)/' | sort | uniq -c | sort -rn

echo
echo "== Reverted commits and how they had been verified =="
found=0
while IFS= read -r line; do
  revert="${line%% *}"
  target="$(git log -1 --format=%B "$revert" | grep -oE 'This reverts commit [0-9a-f]{7,40}' | awk '{print $4}' || true)"
  [ -n "$target" ] || continue
  found=1
  by="$(git log -1 --format='%(trailers:key=Verified-by,valueonly)' "$target" 2>/dev/null | head -n1)"
  subj="$(git log -1 --format=%s "$target" 2>/dev/null || echo '?')"
  printf '%s  verified-by=%-14s %s\n' "${target:0:9}" "${by:-none/unknown}" "$subj"
done < <(git log -n "$n" --grep='^Revert' --format='%H %s')
[ "$found" = 1 ] || echo "(no reverts found)"

echo
echo "== Gate log (observe mode: what would have been blocked) =="
log=".claude/verification/state/gate.log"
if [ -f "$log" ]; then
  python3 - "$log" <<'PY'
import collections, json, sys
c = collections.Counter(json.loads(l).get("event") for l in open(sys.argv[1]) if l.strip())
for k, v in c.most_common():
    print(f"{v:6d}  {k}")
PY
else
  echo "(no gate log on this machine yet)"
fi
echo
echo "A verified commit that got reverted is a miss: run /learn-from-miss on it."
