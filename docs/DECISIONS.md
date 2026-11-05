# Decisions

Newest at the bottom. Each one says what was decided and why.

## 1. A reusable GitHub Actions workflow, no database

Projects call `.github/workflows/pr-scan.yml` from one small file. Output is a job summary, an
uploaded report (`report.md` and `findings.json`), and GitHub issues. No server, no database.
GitHub's code-scanning upload (SARIF) is not used because on private repositories it needs paid
GitHub Code Security.

## 2. The report script lives inside the workflow file

When another private repository calls this workflow, its `GITHUB_TOKEN` can only read that
repository, so the workflow can't download extra files from this one. The report script is
therefore copied into `pr-scan.yml`. The source is `scripts/report.py` and
`scripts/pr-scan.template.yml`; `python3 scripts/build.py` rebuilds the workflow, and the
self-test fails if someone forgets.

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

Opengrep runs the [opengrep-rules](https://github.com/opengrep/opengrep-rules) folders for
JavaScript, TypeScript, Python and GitHub Actions workflow files. Rules marked ERROR block,
WARNING is reported, INFO is reported. GitHub Actions workflow rules were added because a
workflow file can leak secrets the same way code can.

Limits: these rules are a 2025 fork of Semgrep's community rules, described by their maintainers
as "intended for research, testing & benchmarking". They are general rules, with nothing specific
to Next.js or Supabase. Their license is LGPL 2.1 with the Commons Clause, which allows using them
to scan our own code but not selling a product built on them. If MGE Security were ever sold as a
service, this needs revisiting.

## 6. "Outdated software" is not checked yet

The plan listed "outdated software" under Trivy. Trivy does not report outdated npm or Python
packages; it reports known vulnerabilities (OSV-Scanner already does that) and end-of-life
operating systems inside container images, which Vercel projects don't have. So no tool in step 1
checks for packages that are simply old. This is left for the owner to decide. Option: GitHub's
own Dependabot version updates, which are free and open pull requests to update old packages.

## 7. Whole project scanned on every pull request

Gitleaks checks the current files plus the pull request's own commits. TruffleHog checks the
current files on pull requests, and the full git history on pushes to `main` and manual runs.
OSV-Scanner and Opengrep check the whole project, not just changed lines. This means problems
that already exist will also turn the check red until they are fixed or marked as false alarms.

## 8. Issues only outside pull requests, never duplicated

GitHub issues are opened for blocking findings on pushes to `main` and manual runs, never on pull
requests (the red check is the signal there; issues per pull request would pile up). Each issue
carries a hidden ID, so the same finding never gets a second issue, even after the first is
closed. At most 20 new issues per run.

## 9. A broken scan is a failed scan

If any scanner fails to run, the check fails and says the project was not checked. Silence from
a tool that crashed must never look like a pass.

## 10. Blocking merges needs a paid plan

The check turns red on its own. Making GitHub refuse the merge needs a ruleset with a required
status check, and on private repositories rulesets need GitHub Team or Enterprise
([GitHub docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)).
