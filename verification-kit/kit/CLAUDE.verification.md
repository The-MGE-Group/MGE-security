<!-- >>> verification-kit (managed block, edit freely) -->
## Verification

How "done" is defined in this repo. A change is done when there is evidence it works, not when the code is written.

- **Run it.** Before every commit, use the `verify` skill: cheap checks, then drive the real app through the flows the diff touches, then report evidence. Running the app end to end matters more than tests.
- **Cheap checks before a PR.** Tests, build and lint must pass before you open a pull request. A Stop hook runs them for you when you finish.
- **Three rounds, then a human.** If a check still fails after three fix attempts, stop and explain what fails, what you tried and your best guess.
- **Never game a check.** Do not skip, weaken or delete tests to get green. No added sleeps, no retry-until-pass. For a flaky test, find the cause; if you can't, propose deleting it and write down why.
- **Don't touch the judges.** Never edit REVIEW.md, `.claude/hooks/`, `.claude/settings.json`, `.claude/verification/config.json` or `checklist.md`. If one is wrong, say so and let the human change it.
- **Diff-triggered checklist.** Apply the items in `.claude/verification/checklist.md` whose trigger matches the diff.
- **Pick tests that are hard to fool.** Prefer end-to-end tests of real user flows. Add property tests (round trip, invariants, idempotency, optimized equals naive) for parsers, money, permissions and migrations. For a rewrite or migration, use a differential test: run old and new on the same inputs and compare, with a written list of approved differences.
- **Unverified commits say so.** If you truly can't verify, put `Unverified: <reason>` in the commit message.
- **Misses become rules.** When a bug gets through, suggest `/learn-from-miss <PR or incident>`.
<!-- <<< verification-kit -->
