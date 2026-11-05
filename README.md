# MGE Security

A security tester you can switch on for any MGE Group project. It has two parts:

- **Pull-request scan:** checks the code on every pull request, in about 1 to 2 minutes.
- **Weekly scan:** checks a running **test** deployment once a week. It refuses to run against
  any address you list as production.

Each run writes one plain-English report (job summary plus a downloadable copy). Serious
findings turn the check red and open a GitHub issue, and the issue closes itself once a later
scan no longer finds the problem. Why things are built this way: [docs/DECISIONS.md](docs/DECISIONS.md).
What's next: [docs/ROADMAP.md](docs/ROADMAP.md).

## What the pull-request scan checks

| Check | Tool | Turns the check red when |
|---|---|---|
| Passwords and API keys in code, now or in the PR's commits | [Gitleaks](https://github.com/gitleaks/gitleaks) 8.30.1 | always |
| Keys confirmed to still work | [TruffleHog](https://github.com/trufflesecurity/trufflehog) 3.99.3 | always |
| Packages with a published vulnerability | [OSV-Scanner](https://github.com/google/osv-scanner) 2.7.0 | high or critical advisory |
| Packages reported as malicious (OpenSSF feed) | OSV-Scanner 2.7.0 | always |
| Licenses that can force you to publish your code | OSV-Scanner 2.7.0 with [deps.dev](https://deps.dev) data | GPL, AGPL, SSPL and similar |
| Risky code patterns | [Opengrep](https://github.com/opengrep/opengrep) 1.31.0, community rules | rule marked ERROR |
| Next.js and Supabase mistakes (MGE rules, see below) | Opengrep 1.31.0, [rules/mge.yaml](rules/mge.yaml) | secret key reachable from the browser |
| List of every package (SBOM) | OSV-Scanner 2.7.0 | never (attached to the run as `sbom.cdx.json`) |

MGE rules:
- `mge-next-public-secret`: a `NEXT_PUBLIC_` variable whose name says it's a secret.
- `mge-supabase-service-role-in-browser-code`: the Supabase secret key used in a `"use client"` file.
- `mge-supabase-getsession-on-server`: `getSession()` trusted on the server (reported, doesn't block).

## What the weekly scan checks

| Check | Tool | Notes |
|---|---|---|
| Cross-tenant access: can tenant A's user read or change tenant B's data, through the app's routes? | MGE access test ([scripts/access_test.py](scripts/access_test.py)) | Only the routes you list. Routes in `app/` that no test covers are listed in the report. |
| Role access: can a member do what only an admin may? | MGE access test | Same |
| Database leaks: can a user read another tenant's rows in Supabase directly? | MGE access test | Every table with a `tenant_id` column, as each test user and as a logged-out visitor |
| Problems visible from outside (missing protections, unsafe settings) | [ZAP](https://www.zaproxy.org/) 2.17.0 | `baseline` only looks. `full` also attacks, so test data may change. |
| Known flaws and exposed files | [Nuclei](https://github.com/projectdiscovery/nuclei) 3.11.1, templates 10.5.0 | Denial-of-service and fuzzing templates are excluded |
| HTTPS certificate and encryption | [testssl.sh](https://github.com/testssl/testssl.sh) 3.2.4 | On a `vercel.app` address this tests Vercel's settings, not your domain's |
| Database security settings | Supabase security advisor ([API](https://supabase.com/docs/reference/api/v1-get-security-advisors)) | Needs a token (see setup). Supabase marks this API "experimental". |
| Subdomains listed in public sources | [Subfinder](https://github.com/projectdiscovery/subfinder) 2.17.0 | Information only. It reads public lists and sends nothing to your servers. |

If any check crashes or can't log in, the run says "Could not finish". A broken scan is never a pass.

## What it does NOT check

A green check means these tools found nothing. It does not mean the software is secure.

- **Production.** The weekly scan only scans the test address you give it.
- **Untested routes and unwritten rules.** The access test proves exactly what it tests and
  nothing more. Business rules nobody wrote down can't be tested.
- **Logged-in pages, for ZAP and Nuclei.** They scan as a logged-out visitor. The access test
  is what checks the logged-in side.
- **Logic mistakes in general.** Code rules only know common patterns.
- **New or unpublished problems.** Vulnerabilities and malicious packages are only caught once reported.
- **Packages without a lockfile**, and **outdated packages** (Dependabot handles those, see below).
- **Secrets in unusual formats.** TruffleHog only reports keys it proved are live.
- **Legal advice.** License results come from deps.dev and can be wrong.

## Setup, once for the organization

1. Open https://github.com/The-MGE-Group/MGE-security/settings/actions
2. Scroll to the bottom, to the box titled **Access**.
3. Click **Accessible from repositories in the 'The-MGE-Group' organization**.
4. Click **Save**.

This only works for **private** repositories ([GitHub docs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository#allowing-access-to-components-in-a-private-repository)).

## Switching on the pull-request scan in a project

1. Copy [templates/mge-security.yml](templates/mge-security.yml) to `.github/workflows/mge-security.yml` in the project.
2. Merge it. Each pull request then shows a check called **security / Security scan**. Click
   **Details**, then **Summary**, to read the report.

To make GitHub refuse merges while the check is red, private repositories need GitHub Team or
Enterprise ([GitHub docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)).
On the free plan the check still turns red, but merging is not stopped.

Settings (under `with:`): `block-on` (`critical`, `high` default, `medium`, `none`), `path`
(folder to scan, default `.`), `allowed-licenses`, `create-issues` (default `true`).

## Switching on Dependabot in a project (outdated packages)

1. Copy [templates/dependabot.yml](templates/dependabot.yml) to `.github/dependabot.yml` in the project.
2. In the project, go to **Settings**, then **Advanced Security** (called **Code security** on some
   accounts), and click **Enable** next to **Dependabot security updates**.

Dependabot then opens pull requests for old packages, waiting 14 days after each release.
Security fixes come straight away ([GitHub docs](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference)).

## Switching on the weekly scan in a project

You need a test deployment that never holds real customer data: a Vercel preview for a
staging branch, and a separate test Supabase project.

1. Copy [templates/mge-security-weekly.yml](templates/mge-security-weekly.yml) to
   `.github/workflows/mge-security-weekly.yml` and fill in the lines marked `CHANGE`.
2. Copy [templates/access-test.json](templates/access-test.json) to `.mge-security/access-test.json`
   and fill it in: the two test tenants, the test users, and the routes to try. For tenant
   reads, put a unique word in each tenant's test data and list it as `marker`. That lets the
   test prove the other tenant's data came back.
3. Add the secrets below to the project (**Settings**, **Secrets and variables**, **Actions**,
   **New repository secret**). Only the owner adds secrets.

| Secret | What it is |
|---|---|
| `VERCEL_AUTOMATION_BYPASS_SECRET` | Lets the scan past Vercel's preview protection. In Vercel: the project, **Settings**, **Deployment Protection**, **Protection Bypass for Automation** ([Vercel docs](https://vercel.com/docs/deployment-protection/methods-to-bypass-deployment-protection/protection-bypass-automation)) |
| `SUPABASE_ADVISOR_TOKEN` | A Supabase access token. If Supabase offers permission choices, give it only "advisors read" |
| `MGE_TEST_SUPABASE_ANON_KEY` | The **test** Supabase project's public (anon or publishable) key |
| `MGE_TEST_..._EMAIL`, `MGE_TEST_..._PASSWORD` | One pair per test user named in `access-test.json` |

Rules for the access test:
- Use test users and test data only. A `DELETE` or `POST` check that wrongly succeeds really
  changes the test data.
- Each test user needs at least one `"expect": "allowed"` check. If that fails, the login is
  broken and the run says "Could not finish" instead of passing.

## When a finding is a false alarm

- Gitleaks: add the line shown in the report to `.gitleaksignore` in the project.
- Opengrep: add a `// nosemgrep` comment on the flagged line.
- OSV-Scanner: add the advisory to `osv-scanner.toml` next to the lockfile, with a reason
  ([how](https://google.github.io/osv-scanner/configuration/)).
- Then close the GitHub issue. A closed issue is never reopened for the same finding.

## How we know it works

The [Self-test](.github/workflows/self-test.yml) runs on every change here and fails unless
every planted problem is found and the clean versions pass:

- [fixtures/vulnerable](fixtures/vulnerable) and [fixtures/clean](fixtures/clean) test the pull-request scan.
- [fixtures/live](fixtures/live) is a small fake app and fake Supabase. It is started with planted
  problems and then locked down, to test the weekly scan.
- The production guard is tested separately.
- The Supabase advisor can't run without a real project, so only its report handling is tested,
  using sample output.

## Files

- `.github/workflows/pr-scan.yml` and `weekly-scan.yml` are what projects call. Blocks between
  `>>> BEGIN` and `<<< END` lines are copied in from `scripts/` and `rules/`: edit those files,
  then run `python3 scripts/build.py`.
- `templates/` holds the files a project copies.
- `fixtures/` holds the test projects.
