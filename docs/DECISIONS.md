# Decisions

Newest at the bottom. Each one says what was decided and why.

## 1. A reusable GitHub Actions workflow, no database

Projects call `.github/workflows/pr-scan.yml` from one small file. Output is a job summary, an
uploaded report (`report.md` and `findings.json`), and GitHub issues. No server, no database.
GitHub's code-scanning upload (SARIF) is not used because on private repositories it needs paid
GitHub Code Security.

## 2. Helper scripts are copied into the workflow files

When another private repository calls these workflows, its `GITHUB_TOKEN` can only read that
repository, so the workflows can't download extra files from this one. Each workflow therefore
carries copies of the files it needs, between `>>> BEGIN <file>` and `<<< END <file>` lines.
`python3 scripts/build.py` refreshes the copies, and the self-test fails if one is stale. The
workflow files themselves are the source for everything else, so Dependabot can update the
pinned actions in them directly.

## 3. Every tool pinned, and checked before it runs

- Scanners are downloaded from their official GitHub release pages at one exact version, and
  the SHA-256 checksum is checked before running. The checksums for Gitleaks, TruffleHog and
  OSV-Scanner were compared against the publishers' own checksum files. Opengrep publishes a
  cosign signature instead of a checksum file; that signature was not checked, so the Opengrep
  checksum only proves the file hasn't changed since it was chosen on 2026-11-05.
- GitHub actions are pinned to a full commit hash, not a version tag. Tags can be moved: in
  March 2026 an attacker moved 76 of 77 tags of `aquasecurity/trivy-action` to malicious code
  that stole CI secrets ([Aqua](https://www.aquasec.com/blog/trivy-supply-chain-attack-what-you-need-to-know),
  [Socket](https://socket.dev/blog/trivy-under-attack-again-github-actions-compromise),
  CVE-2026-33634).
- Only versions at least about two weeks old were chosen (on 2026-11-05), so a hijacked release
  has time to be noticed first. Chosen: Gitleaks 8.30.1, TruffleHog 3.99.3, OSV-Scanner 2.7.0,
  Opengrep 1.31.0, opengrep-rules commit `f1d2b562`, actions/checkout 7.0.1,
  actions/upload-artifact 7.0.2, actions/download-artifact 8.0.2, actions/github-script 9.0.0.

## 4. Licenses: OSV-Scanner instead of Trivy

The plan named Trivy for license risk. Trivy only finds JavaScript package licenses by reading an
installed `node_modules` folder ([Trivy docs](https://trivy.dev/latest/docs/coverage/language/nodejs/)),
and installing a project's packages in the scan would add time and run more third-party code.
OSV-Scanner's `--licenses` reads licenses for the exact versions in the lockfile from deps.dev
without installing anything ([OSV-Scanner docs](https://google.github.io/osv-scanner/usage/license-scanning/)).
Strong copyleft licenses (GPL, AGPL, SSPL and similar) block; other licenses not on the allowed
list are reported without blocking. MPL-2.0 and LGPL are reported, not blocked: they usually
only require sharing changes to that package itself.

## 5. Opengrep rules: the community rule set, four languages

Opengrep runs the `security` rules from the [opengrep-rules](https://github.com/opengrep/opengrep-rules)
folders for JavaScript, TypeScript, Python and GitHub Actions workflow files. Style and correctness
rules are left out: on MGE Insights' first scan they made 546 of the 588 findings (for example 378
"text not translated" notes) and one blocking finding that was not about security. Rules marked ERROR block,
WARNING is reported, INFO is reported. GitHub Actions workflow rules were added because a
workflow file can leak secrets the same way code can.

Limits: these rules are a 2025 fork of Semgrep's community rules, described by their maintainers
as "intended for research, testing & benchmarking". They are general rules, with nothing specific
to Next.js or Supabase. Their license is LGPL 2.1 with the Commons Clause, which allows using them
to scan our own code but not selling a product built on them. If MGE Security were ever sold as a
service, this needs revisiting.

## 6. Outdated software: Dependabot, not a scanner

Trivy does not report outdated npm or Python packages; it reports known vulnerabilities
(OSV-Scanner already does that) and end-of-life operating systems in container images, which
Vercel projects don't have. GitHub's Dependabot is free, opens pull requests to update old packages,
and can wait 14 days after each release (`cooldown`) so a hijacked release has time to be noticed.
Security fixes are not delayed ([GitHub docs](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference)).
Projects copy `templates/dependabot.yml`; this repository uses it for its own actions.

## 7. Whole project scanned on every pull request

Gitleaks checks the current files plus the pull request's own commits. TruffleHog checks the
current files on pull requests, and the full git history on pushes to `main` and manual runs.
OSV-Scanner and Opengrep check the whole project, not just changed lines. This means problems
that already exist will also turn the check red until they are fixed or marked as false alarms.

## 8. Issues: opened once, closed when fixed

GitHub issues are opened for blocking findings on pushes to `main`, manual runs and weekly scans,
never on pull requests (the red check is the signal there). Each issue carries a hidden ID, so a
finding never gets a second issue, even after the first is closed by hand. At most 20 new issues
per run.

Retesting: when a later full scan no longer finds an issue's problem, the issue gets a comment and
is closed. This only happens when the tool that found it ran cleanly in that scan, so a crashed or
skipped tool can never close an issue, and pull-request scan issues only close after a scan of the
whole project.

## 9. A broken scan is a failed scan

If any scanner fails to run, the check fails and says the project was not checked. Silence from
a tool that crashed must never look like a pass.

## 10. Blocking merges needs a paid plan

The check turns red on its own. Making GitHub refuse the merge needs a ruleset with a required
status check, and on private repositories rulesets need GitHub Team or Enterprise
([GitHub docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)).

## 11. Weekly scan: one reusable workflow, test deployments only

`weekly-scan.yml` takes the test address and a required list of production host names. Its first
step refuses to run if the address uses one of those names (letter case, ports and paths don't
matter), and no scanner step runs unless that check passed. While building this, the scanner steps
were first written to run even after a refusal; the self-test caught that a refused run would
still have scanned, and it was fixed before anything used it. Each scanner can be skipped
(for example no Supabase project given); skipped checks are shown in the report, never hidden.

## 12. The access test is our own script, not an off-the-shelf tool

No free tool knows which tenant a record belongs to, so `scripts/access_test.py` does it, using
only Python's standard library:
- Logs in each test user with Supabase email and password, then sends the login the way the app
  expects: a bearer header, or the cookie `@supabase/ssr` uses (`base64-` plus the session).
- Route checks: a cross-tenant read counts as a leak only if the other tenant's marker text comes
  back, so an empty answer is not reported as a leak. For role checks inside one tenant, any
  success counts.
- Database checks: for every table with a `tenant_id` column (found automatically, or listed in
  the config), each user and a logged-out visitor ask Supabase for another tenant's rows.
- "Allowed" control checks must pass. Otherwise the test is broken (for example a failed login)
  and the run says "Could not finish". Without this, a broken login would make every refusal
  check pass.
- Next.js routes with no test are listed in the report, so gaps are visible.
- Secrets: the step receives the repository's secrets (`toJSON(secrets)`) because the config names
  them; it only reads the names in the config and never prints them. GitHub masks them in logs.

Limit: Supabase may block automatic table listing for the public key. The config's `tables` list
is the fallback, and the run fails, rather than passing, if no tables can be found.

## 13. Weekly scanner choices

- ZAP runs `baseline` by default: it browses and looks, but doesn't attack. `full` is available,
  but it submits forms and can change test data. The Vercel bypass header is only sent to the
  target host.
- Nuclei runs the `http`, `ssl` and `dns` templates of one pinned template release, without
  denial-of-service and fuzzing templates, without its outside callback server (`-ni`), and
  without the two token-guessing templates its own "recommended" profile also leaves out.
- testssl.sh tests whatever host is scanned. On a `vercel.app` address that is Vercel's setup,
  so its findings there say little about your own domain.
- Subfinder only reads public sources. Its list is information, never a finding, because the
  weekly scan never touches production.
- Supabase advisor: Supabase's API accepts fine-grained tokens with only the `advisors_read`
  permission ([Supabase docs](https://supabase.com/docs/reference/api/v1-get-security-advisors)).
  Use one of those, never a full account token. The endpoint is marked experimental.
- Versions (all at least about two weeks old on 2026-11-05): Nuclei 3.11.1, nuclei-templates
  10.5.0, Subfinder 2.17.0, testssl.sh 3.2.4 (3.2.5 was one day old), ZAP 2.17.0 by image digest.
  Nuclei and Subfinder checksums match the publisher's checksum files.

## 14. MGE code rules: three, all simple

`rules/mge.yaml` holds only patterns that are clearly wrong when they match: a secret-named
`NEXT_PUBLIC_` variable, the Supabase secret key in a `"use client"` file (both block), and
`getSession()` used on the server, which Supabase's own server-side guide warns against ([Supabase docs](https://supabase.com/docs/guides/auth/server-side/nextjs)) (reported
only). Checking that every query filters by tenant is not a simple pattern, so it is left to the
access test.

## 15. AI code review: notes only, and the one check allowed to fail quietly

Claude Opus 5.5 reads each pull request's changed files and diff and adds notes to the report.

- **Never blocks, never opens issues.** An AI reviewer can be wrong in both directions, and the
  text it reads is written by whoever opened the pull request, who could try to talk it into or
  out of a finding. So its opinion is shown and nothing more.
- **Exception to decision 9.** If Claude can't be reached (no credit, rate limit, outage, bad
  key), the scan still finishes on the other checks and the report shows a warning. Otherwise
  an outage at Anthropic would turn every pull request in every project red over a check that
  could not have blocked anyway. No key at all means "skipped".
- **A note needs a confirmed line.** Claude must quote the line it means. The note is dropped
  unless that text is in the file, and the report links to where the text really is.
- **Pull requests only, changed files only.** That keeps the cost per run small and known. Each
  changed file is sent in full with line numbers, because a missing login check can only be
  seen with the whole route in view. Nothing is cut short without saying so: a file that
  doesn't fit is named in the report as not reviewed.
- **The pull request's code is never run**, only read from git as text. Symlinks are not
  followed. Claude gets no tools. Its words are stripped of HTML and links before they go into
  the report. The API key is given to that one step only.
- **Claude's own SDK, pinned like every other tool.** `scripts/ai-requirements.txt` lists
  `anthropic` 2.4.0 and its 15 dependencies at exact versions with SHA-256 checksums, and pip
  refuses anything else (`--require-hashes`). Each checksum was compared with PyPI's, and every
  version was at least two weeks old on 2026-11-17. Four packages were held one release back
  to meet that (httpx2, httpcore2, pydantic, jiter). It is installed only when a review will
  really run. Dependabot does not update this list; it is refreshed by hand.
- **If Opus 5.5's safety filter declines** to read security-sensitive code, the request asks
  Anthropic to retry on the model it recommends for that case (`fallbacks: "default"`, a beta
  feature). If that also declines, the report shows the warning above.
- **Not yet proven against the real API.** No key was available while building, so the tests
  use a fake Claude and a local stand-in for the API. The request format follows Anthropic's
  SDK, version 2.4.0.
