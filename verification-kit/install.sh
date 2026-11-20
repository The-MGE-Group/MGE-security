#!/usr/bin/env bash
# Installs the verification kit into a project.
#   ./install.sh /path/to/project            first install (never overwrites your files)
#   ./install.sh /path/to/project --upgrade  also refreshes the kit's own code (hooks, report script)
# Needs: bash, git, python3.
set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/kit" && pwd)"
TARGET="${1:-}"
UPGRADE="${2:-}"
[ -n "$TARGET" ] && [ -d "$TARGET" ] || { echo "usage: $0 /path/to/project [--upgrade]"; exit 1; }
TARGET="$(cd "$TARGET" && pwd)"
command -v python3 >/dev/null || { echo "python3 is required (the hooks are Python, standard library only)"; exit 1; }

echo "Installing verification kit into $TARGET"

# 1. Copy files. Existing files are kept unless they are kit code and --upgrade was given.
KIT_CODE='^\.claude/hooks/|^scripts/verification-report\.sh$'
while IFS= read -r -d '' src; do
  rel="${src#"$KIT"/}"
  case "$rel" in
    .claude/settings.hooks.json|CLAUDE.verification.md) continue ;;
  esac
  dst="$TARGET/$rel"
  if [ -e "$dst" ]; then
    if [ "$UPGRADE" = "--upgrade" ] && [[ "$rel" =~ $KIT_CODE ]]; then
      cp "$src" "$dst"; echo "  updated  $rel"
    else
      echo "  kept     $rel (already exists)"
    fi
  else
    mkdir -p "$(dirname "$dst")"; cp "$src" "$dst"; echo "  added    $rel"
  fi
done < <(find "$KIT" -type f -print0)
chmod +x "$TARGET"/.claude/hooks/*.py "$TARGET/.claude/hooks/prepare-commit-msg" "$TARGET/scripts/verification-report.sh"

# 2. CLAUDE.md block
if grep -qs '>>> verification-kit' "$TARGET/CLAUDE.md"; then
  echo "  kept     CLAUDE.md block (already there)"
else
  { [ -s "$TARGET/CLAUDE.md" ] && echo; cat "$KIT/CLAUDE.verification.md"; } >> "$TARGET/CLAUDE.md"
  echo "  added    verification block to CLAUDE.md"
fi

# 3. Merge hooks into .claude/settings.json, and detect the check command
python3 - "$KIT/.claude/settings.hooks.json" "$TARGET" <<'PY'
import json, os, sys
from pathlib import Path
kit_hooks = json.load(open(sys.argv[1]))["hooks"]
root = Path(sys.argv[2])
sp = root / ".claude" / "settings.json"
settings = json.loads(sp.read_text()) if sp.exists() else {}
hooks = settings.setdefault("hooks", {})
added = 0
for event, groups in kit_hooks.items():
    existing = hooks.setdefault(event, [])
    have = {h.get("command") for g in existing for h in g.get("hooks", [])}
    for g in groups:
        if not any(h["command"] in have for h in g["hooks"]):
            existing.append(g); added += 1
sp.parent.mkdir(parents=True, exist_ok=True)
sp.write_text(json.dumps(settings, indent=2) + "\n")
print(f"  {'merged ' if added else 'kept    '} hooks into .claude/settings.json ({added} added)")

cp = root / ".claude" / "verification" / "config.json"
cfg = json.loads(cp.read_text())
if not cfg.get("check_command"):
    cmd = ""
    pkg = root / "package.json"
    if pkg.exists():
        scripts = json.loads(pkg.read_text()).get("scripts", {})
        pm = "pnpm" if (root / "pnpm-lock.yaml").exists() else "yarn" if (root / "yarn.lock").exists() \
            else "bun" if (root / "bun.lockb").exists() or (root / "bun.lock").exists() else "npm"
        parts = [f"{pm} run {s}" for s in ("lint", "typecheck", "test", "build") if s in scripts]
        cmd = " && ".join(parts)
    elif (root / "pyproject.toml").exists() or (root / "pytest.ini").exists():
        cmd = "python3 -m pytest -q"
    elif (root / "Cargo.toml").exists():
        cmd = "cargo test --quiet"
    elif (root / "go.mod").exists():
        cmd = "go vet ./... && go test ./..."
    if cmd:
        cfg["check_command"] = cmd
        cp.write_text(json.dumps(cfg, indent=2) + "\n")
        print(f"  detected check_command: {cmd}")
    else:
        print("  !! could not detect a check command: set check_command in .claude/verification/config.json")
PY

# 4. Keep per-machine state out of git
if ! grep -qsx '.claude/verification/state/' "$TARGET/.gitignore"; then
  echo '.claude/verification/state/' >> "$TARGET/.gitignore"; echo "  added    .claude/verification/state/ to .gitignore"
fi

# 5. Git hook that stamps Claude's commits with Verified-by (also reinstalled at every session start)
if git -C "$TARGET" rev-parse --git-dir >/dev/null 2>&1; then
  chmod +x "$TARGET/.claude/hooks/prepare-commit-msg"
  CLAUDE_PROJECT_DIR="$TARGET" python3 "$TARGET/.claude/hooks/session_start.py" && echo "  added    git prepare-commit-msg hook"
else
  echo "  !! not a git repo: skipped the commit-stamp hook"
fi

cat <<'EOF'

Done. Next steps:
  1. Fill in the TODO lines in .claude/skills/verify/SKILL.md (how to start and log into the app).
  2. Fill in .claude/verification/feature-map.md with your real user flows.
  3. Check check_command in .claude/verification/config.json.
  4. Append .github/CODEOWNERS.verification to .github/CODEOWNERS (then delete it), and turn on
     "Require review from Code Owners" in branch protection.
  5. Commit. The commit gate starts in "observe" mode. After a week or two, run
     scripts/verification-report.sh, and if the would-block list looks right set gate_mode to "enforce".
EOF
