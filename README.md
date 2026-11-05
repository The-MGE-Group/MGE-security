# MGE Security

A security tester you can switch on for any MGE Group project. On every pull request it runs
free, well-known scanners and writes one plain-English report. If it finds a serious problem,
the pull request check turns red.

This is step 1 of 3. Steps 2 (nightly) and 3 (weekly, against a test copy of the app) are in
[docs/ROADMAP.md](docs/ROADMAP.md). Why things are built this way: [docs/DECISIONS.md](docs/DECISIONS.md).

## What it checks on every pull request

| Check | Tool | Blocks the merge when |
|---|---|---|
| Passwords and API keys written into code, now or in the PR's commits | [Gitleaks](https://github.com/gitleaks/gitleaks) 8.30.1 | always (any match counts as high) |
| Keys that are confirmed live (it tests them with the provider) | [TruffleHog](https://github.com/trufflesecurity/trufflehog) 3.99.3 | always (critical) |
| Packages with a published vulnerability | [OSV-Scanner](https://github.com/google/osv-scanner) 2.7.0 | the advisory is high or critical |
| Packages reported as malicious (OpenSSF malicious-packages feed, via OSV) | OSV-Scanner 2.7.0 | always (critical) |
| Package licenses that can force you to publish your code (GPL, AGPL, SSPL and similar) | OSV-Scanner 2.7.0, license data from [deps.dev](https://deps.dev) | strong copyleft (high); other unlisted licenses are reported only |
| Risky code patterns, for example SQL built from user input | [Opengrep](https://github.com/opengrep/opengrep) 1.31.0 with the community rules for JavaScript, TypeScript, Python and GitHub Actions files | the rule is marked ERROR (high) |

If any scanner fails to run, the check fails and the report says "Could not finish".
A broken scan is never reported as a pass.

Every finding comes with proof: a link to the exact file and line, or the package name,
version, lockfile and advisory link. Secret values are never shown in the report.

## What it does NOT check

Be clear about this. A green check means these tools found nothing. It does not mean the
software is secure.

- **The running app.** Logins, permissions, and whether one customer can see another
  customer's data. That needs tests against a running test copy (step 3).
- **Logic mistakes.** The code rules only know common, well-known patterns. They have no
  rules specific to Next.js route handlers, Supabase, or `tenant_id` checks yet.
- **New or unpublished problems.** Vulnerabilities and malicious packages are only caught
  once someone has reported them to the public databases.
- **Packages without a lockfile.** OSV-Scanner reads `pnpm-lock.yaml`, `package-lock.json`,
  `yarn.lock`, `requirements.txt` and similar. A `package.json` alone is not checked.
- **Outdated software that has no known vulnerability.** No tool here does this. See
  [docs/DECISIONS.md](docs/DECISIONS.md) (decision 6).
- **Secrets in unusual formats.** Gitleaks matches known key formats. TruffleHog only reports
  keys it could prove are live.
- **Legal advice.** License results come from deps.dev and can be wrong.

## How a project switches it on

You do steps 1 to 4 once. Steps 5 to 8 are done once per project.

**A. Let other repositories use this one** (only once)

1. Open https://github.com/The-MGE-Group/MGE-security/settings/actions
2. Scroll to the bottom, to the box titled **Access**.
3. Click **Accessible from repositories in the 'The-MGE-Group' organization**.
4. Click **Save**.

This only works for **private** repositories in the organization. GitHub does not allow public
repositories to use a private repository's workflows
([GitHub docs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository#allowing-access-to-components-in-a-private-repository)).

**B. Add one file to the project**

5. In the project, create the file `.github/workflows/mge-security.yml` with exactly this:

```yaml
name: MGE Security
on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
  issues: write
jobs:
  security:
    uses: The-MGE-Group/MGE-security/.github/workflows/pr-scan.yml@main
```

6. Merge it. From then on, every pull request shows a check called
   **MGE Security / security / Security scan**. Click **Details**, then **Summary**, to read the report.

**C. Make the red check actually stop merges** (optional, needs a paid GitHub plan for private repositories)

GitHub only enforces required checks on private repositories with GitHub Team or Enterprise
([GitHub docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)).
On the free plan the check still turns red, but someone can merge anyway.

7. In the project, go to **Settings**, then **Rules**, then **Rulesets**, then **New ruleset**, then **New branch ruleset**.
8. Name it `MGE Security`, set **Enforcement status** to **Active**, under **Target branches** click
   **Add target** then **Include default branch**, tick **Require status checks to pass**, click
   **Add checks**, type `Security scan`, pick it, and click **Create**.

### Settings a project can change

Add them under `with:` in the file from step 5.

| Setting | Default | Meaning |
|---|---|---|
| `block-on` | `high` | Lowest level that turns the check red: `critical`, `high`, `medium`, or `none` |
| `path` | `.` | Folder to scan |
| `allowed-licenses` | MIT, ISC, Apache-2.0, BSD and similar | Licenses that are fine to use |
| `create-issues` | `true` | Open one GitHub issue per blocking finding. Only on pushes to `main` and manual runs, never on pull requests |

### When a finding is a false alarm

Each tool has its own way to say "this is fine". Write a short reason next to it.

- Gitleaks: add the line shown in the report to a file called `.gitleaksignore` in the project.
- Opengrep: add a `// nosemgrep` comment on the flagged line.
- OSV-Scanner: add the advisory to an `osv-scanner.toml` file next to the lockfile, with a reason
  ([how](https://google.github.io/osv-scanner/configuration/)).

## How we know it works

The [Self-test](.github/workflows/self-test.yml) runs on every change to this repository. It scans
[fixtures/vulnerable](fixtures/vulnerable) (one planted problem per scanner) and
[fixtures/clean](fixtures/clean), and fails unless every planted problem is found and the clean
project passes with zero findings.

## Files

- `.github/workflows/pr-scan.yml` is what projects call. It is generated: edit
  `scripts/pr-scan.template.yml` or `scripts/report.py`, then run `python3 scripts/build.py`.
- `scripts/report.py` turns scanner output into the plain-English report.
- `fixtures/` holds the test projects.
