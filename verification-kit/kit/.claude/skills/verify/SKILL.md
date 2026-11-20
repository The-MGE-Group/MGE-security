---
name: verify
description: Prove the current change works by running the real app end to end and collecting evidence. Use before every commit, before opening a pull request, and whenever the user asks to verify, test or check a change.
---

# Verify

Goal: show evidence that the change works for a real user. Tests passing is step one, not the finish line.

## 1. Cheap checks first

Run the project's check command (in `.claude/verification/config.json`, key `check_command`). If it fails, fix the code and rerun. Do not move on with red checks.

## 2. Start the app

<!-- FILL IN for this project, then delete this comment. Keep it fast and reliable. -->
- Start: `TODO e.g. npm run dev`
- Ready when: `TODO e.g. curl -sf http://localhost:3000/api/health`
- Test login: `TODO e.g. user test@example.com, password in $TEST_PASSWORD`
- Stop: `TODO`

## 3. Drive what the diff touches

1. Read the diff (`git diff HEAD` plus untracked files).
2. Open `.claude/verification/feature-map.md`. Pick every flow the diff could affect.
3. Run each flow the way a user would, with real hands and eyes on the running app:
   - Web: Playwright or the Chrome extension. Take a screenshot at the end of each flow.
   - API or backend: real HTTP calls against the running service. Keep the response bodies.
   - Mobile: the simulator or the mobile MCP. Desktop: computer use.
4. Compare what you see with the "expected" column. A flow that "probably works" is not verified.

## 4. Diff-triggered checklist

Open `.claude/verification/checklist.md`. Run only the items whose trigger matches this diff (usually a handful). Say which ones you ran and why the others don't apply.

## 5. Report

End with this block so the human can review evidence instead of the diff:

```
VERIFIED: <one line on what was proven>
Ran: <commands and flows>
Evidence: <screenshot paths, response snippets, log lines>
Checklist items applied: <ids or "none matched">
NOT verified: <anything you could not check, and why>
```

## Rules

- Three rounds. If the same check still fails after three fix attempts, stop and tell the human what fails, what you tried, and your best guess.
- Flaky tests: never skip them, add sleeps, or retry until green. Find the cause. If you cannot, propose deleting the test and write down why.
- Never edit a protected file (REVIEW.md, `.claude/hooks/`, `.claude/verification/config.json`, `checklist.md`) to make a check pass.
- If this skill itself is slow or unreliable, say so and propose a fix to it. It is the smoke-test harness and must stay fast.
