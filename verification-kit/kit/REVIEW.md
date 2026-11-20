# Review instructions

Read by Claude Code Review on pull requests, always from the default branch, never from the PR itself.
Rules that apply to local work too belong in CLAUDE.md. Keep this file for pull-request review only.

## What Important means here

A bug a user or an operator would notice: wrong data, data shown to the wrong person, a crash, a lost write,
a broken flow from `.claude/verification/feature-map.md`, or a secret exposed.

## Pre-existing

If the bug was already there before this PR, label it Pre-existing. The author is not held to it.

## Always check

- Run the items in the reliability checklist (included below) whose trigger matches the diff. Name the ones you applied.
- New API routes have an integration test.
- The PR description includes the VERIFIED block from the verify skill. If it is missing, say so.
- The PR does not change tests or checks just to make them pass (deleted assertions, new skips, added sleeps or retries).

## Build on earlier rounds

If this PR was reviewed before, start from the earlier findings: check each was fixed, then look for new problems.
Do not re-report fixed items.

## Cap the nits

Report at most five Nits per review.

## Do not report

Anything CI already enforces: lint, formatting, type errors.

## Reliability checklist

@.claude/verification/checklist.md
