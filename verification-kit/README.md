# Verification kit

A drop-in setup for Claude Code that copies how the Claude Code team verifies its own work, as described in
[How the Claude Code team thinks about verification](https://claude.dev/blog/how-the-claude-code-team-thinks-about-verification/)
(Addy Osmani, Nov 16 2026). Install it into any git project with one command.

```bash
./verification-kit/install.sh /path/to/project            # first install, never overwrites your files
./verification-kit/install.sh /path/to/project --upgrade  # later: refresh the kit's hook code
```

Needs `git` and `python3` (standard library only). Works with any language; the check command is auto-detected
for npm/pnpm/yarn/bun, Python, Rust and Go, and you can set it by hand.

## The workflow in one paragraph

You stop reading every diff and start defining "done" and reviewing evidence. Claude runs the real app and proves
the change works (the `verify` skill). Cheap checks run automatically when Claude finishes, and if they still fail
after three fix rounds, a human is pulled in. A diff-triggered checklist, written by the code owners, adds targeted
checks. The files that judge changes are locked so a change can't edit its own judge. Every commit is stamped with
how it was verified, a new gate starts in observe mode before it blocks anything, and bugs that get through are
turned into new rules (and old rules get pruned).

## Article idea → what the kit installs

| Article practice | Kit file | What it does |
|---|---|---|
| Verification means running the change; a `verify` skill in `.claude/skills/` | `.claude/skills/verify/SKILL.md` | Cheap checks, start the app, drive the flows the diff touches, collect screenshots and responses, report a VERIFIED block |
| Feature map as guide and grading rubric | `.claude/verification/feature-map.md` | User flows with paths, selectors and expected results |
| Claude runs tests, build, lint before a PR; a hook runs tests when Claude finishes | `.claude/hooks/run_checks.py` (Stop hook) | Runs `check_command`; on failure, sends the output back to Claude and keeps it working. Skips if nothing changed |
| Failing after three rounds → bring in a human | same hook, `max_fix_rounds: 3` | Third failure stops the loop and shows you a warning |
| Reliability checks trigger on the diff (their checklist has 39 items) | `.claude/verification/checklist.md` | Trigger / check / source table. Seeded with 7 generic starters to replace |
| One reviewer, multiple rounds; REVIEW.md says what to focus on | `REVIEW.md` | For Claude Code Review on PRs: what Important means, Pre-existing, build on earlier rounds, cap nits, pulls in the checklist |
| Changes can't modify their own checks | `.claude/hooks/protect_checks.py`, `.github/workflows/verification-integrity.yml`, `.github/CODEOWNERS.verification` | Blocks Claude's edits to the judging files; CI fails a PR that changes them without a `verification-change` label, reading the protected list from the **base** branch |
| Start a new gate in observe mode; off / observe / enforce; stamp every commit, including "none" | `.claude/hooks/commit_gate.py`, git `prepare-commit-msg` | Blocks `git commit` if the session never ran `/verify` or `/code-review` (enforce), or just logs it (observe). Adds `Verified-by:` trailer. `Unverified: <reason>` in the message is the escape hatch; after 2 blocks the next commit goes through so Claude can't get stuck |
| Test your checks on what matters (reverts, rejected changes) | `scripts/verification-report.sh` | Counts commits by how they were verified, lists reverted commits and whether they had been verified, summarizes the gate log |
| Turn misses into rules; three agents try to disprove a rule; human approves; prune | `.claude/skills/learn-from-miss/SKILL.md`, `.claude/verification/lessons.md` | `/learn-from-miss <PR>` drafts a rule with evidence; `/learn-from-miss prune` proposes removals. You promote rules by hand |
| Flaky tests: no skips, sleeps or retries; delete with a written reason | `CLAUDE.md` block, verify skill, Stop hook message | Stated as a rule in three places Claude reads |
| E2E first, then property and differential tests | `CLAUDE.md` block | Tells Claude which test types to write and when |

## After installing (about 20 minutes)

1. **Fill in the verify skill.** The TODO lines in `.claude/skills/verify/SKILL.md`: how to start the app, how to know
   it's ready, the test login. This is the most valuable 5 minutes in the whole setup. Then ask Claude to run `/verify`
   a few times and make it faster and more reliable, as the article recommends.
2. **Write the feature map.** Your real user flows in `.claude/verification/feature-map.md`.
3. **Check `check_command`** in `.claude/verification/config.json`. Keep it to things that take seconds or a couple of
   minutes. Slow checks get run less, and flaky ones teach Claude to rerun instead of fix.
4. **Lock the judges on GitHub.** Append `.github/CODEOWNERS.verification` to `.github/CODEOWNERS` with your handle,
   then turn on "Require review from Code Owners" in branch protection. Create a `verification-change` label.
5. **Commit and push.** The gate is in `observe` mode.
6. **After 1 to 2 weeks**, run `scripts/verification-report.sh`. If the "would_block" entries are ones you'd really want
   blocked, set `"gate_mode": "enforce"` in a reviewed PR.
7. **Replace the checklist starters** with lessons from your own incidents and reverts as they happen.

## Settings (`.claude/verification/config.json`)

| Key | Default | Meaning |
|---|---|---|
| `gate_mode` | `observe` | `off`, `observe` (log only) or `enforce` (block unverified commits) |
| `check_command` | auto-detected | Shell command for tests, build and lint. Empty means the Stop hook does nothing |
| `max_fix_rounds` | `3` | Failed check rounds before the hook hands off to you |
| `blocks_before_letting_through` | `2` | Blocked commits in one session before the next is allowed (stamped `none`) |
| `verify_markers` | `verify`, `code-review` | Skills whose use in the session counts as verification |
| `protected_paths` | the judging files and the MGE security scan files | Globs Claude may not edit; also used by the CI job (from the base branch). Includes the security workflows, `.mge-security/`, `.gitleaksignore`, `osv-scanner.toml` and `dependabot.yml`, so a change can't switch the scan off or mark its own findings as false alarms |

## Honest limits

- **The Bash protection is best effort.** It catches common write commands (`sed -i`, `>`, `mv`, `cp`, `rm`, `tee`).
  A script that writes files some other way gets past it. The real lock is CODEOWNERS plus the CI job.
- **The gate checks the session, not the specific diff.** Running `/verify` once early in a long session counts for later
  commits too. The article's gate works at session level as well.
- **The `Verified-by` stamp needs the git hook in each clone** (git doesn't share hooks). Run the installer once per clone,
  including in cloud sessions, or commits there won't carry the trailer.
- **It measures reverts, not rejected PRs.** Tracking PRs a maintainer rejected needs the GitHub API; that's not included.
- **REVIEW.md only matters if you use Claude Code Review** on pull requests. Local `/code-review` reads CLAUDE.md, not
  REVIEW.md ([docs](https://code.claude.com/docs/en/code-review-customize)).
- **The article's own gate script and stamp format weren't published.** The gate, stamp trailer and report here are my
  implementation of the behavior it describes, not Anthropic's code.

## Sources

- The article: https://claude.dev/blog/how-the-claude-code-team-thinks-about-verification/
- Hooks reference (event inputs, exit code 2, Stop `decision`/`stop_hook_active`, PreToolUse `permissionDecision`): https://code.claude.com/docs/en/hooks
- Skills (layout, frontmatter, `disable-model-invocation`): https://code.claude.com/docs/en/skills
- REVIEW.md (read from the base branch, `@` includes, nit caps): https://code.claude.com/docs/en/code-review-customize
