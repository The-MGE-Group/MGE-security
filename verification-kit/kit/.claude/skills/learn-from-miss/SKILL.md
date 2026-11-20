---
name: learn-from-miss
description: Turn a bug that got through (a revert, an incident, a reviewer's comment) into a candidate rule, or prune rules that no longer earn their keep.
disable-model-invocation: true
argument-hint: "<PR, commit, incident or 'prune'>"
---

# Learn from a miss

Input: $ARGUMENTS

## If the input is "prune"

Go through `.claude/verification/checklist.md`, `REVIEW.md`, `CLAUDE.md` and the test suite. List items that are duplicated, that no recent diff has triggered, or that guard code that no longer exists. Propose removals in `.claude/verification/lessons.md` under "Prune proposals". Do not delete anything yourself.

## Otherwise

1. **Find the bug.** Read the PR, commit or incident. Write the bug in one sentence (this is the answer key).
2. **Was it detectable?** Check out the parent of the fix. Run three independent reviewers (subagents with no knowledge of the answer key) on the original diff. If two or more find it, it was detectable and the reviewer needs better focus. If none find it on a small diff, that gap is worth a rule.
3. **Draft a rule** with three parts:
   - Trigger: something visible in a diff (a file path, an API, a type changing).
   - Check: the question to ask when the trigger fires.
   - Source: this PR or incident.
4. **Try to break it.** It only qualifies if the pattern shows up in at least two PRs and can be spotted from a diff. Run three subagents that each try to disprove the rule (show it would be noisy, wrong, or already covered). Record their answers.
5. **Write it up** in `.claude/verification/lessons.md` as a candidate, with the evidence. A human promotes it to `checklist.md` or `REVIEW.md` in a reviewed PR. You never edit those two files.

If the miss was a repeat behavior of Claude (for example, logging user data), also propose a one-line rule for `CLAUDE.md` or a hook.
