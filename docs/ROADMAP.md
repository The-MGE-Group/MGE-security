# Roadmap

## Step 1: every pull request (built)

Secrets (Gitleaks, TruffleHog), vulnerable and malicious packages and licenses (OSV-Scanner),
risky code patterns (Opengrep). Plain-English report, red check on critical or high findings,
GitHub issues on pushes to `main`. Target: under 5 minutes. See the [README](../README.md).

## Step 2: nightly (not built)

- Deeper versions of the step 1 scans, for example the full git history with TruffleHog on every
  branch, and Opengrep rules that are too slow or too noisy for pull requests.
- AI code review and triage with
  [`anthropics/claude-code-action`](https://github.com/anthropics/claude-code-action), pinned to an
  exact commit. It reads the code and the step 1 findings, removes likely false alarms, and looks
  for logic problems the rules can't see (for example a query that forgets `tenant_id`).
  Every AI finding must still point to an exact file and line, or it is not reported.
- Needs: an `ANTHROPIC_API_KEY` secret, which the owner adds.
- Honest limit: AI review misses things and sometimes invents them. It is a second opinion, not
  proof.

## Step 3: weekly, against a preview or test deployment only (not built)

Never against production.

- DAST (testing the running app from outside): [ZAP](https://www.zaproxy.org/) and
  [Nuclei](https://github.com/projectdiscovery/nuclei).
- API fuzzing: [Schemathesis](https://github.com/schemathesis/schemathesis). Needs an OpenAPI
  description of the API, or one written for it.
- TLS and security headers: [testssl.sh](https://github.com/testssl/testssl.sh).
- AI pentest stage, guided by the results above.
- Cross-tenant test for multi-tenant apps such as MGE Insights: log in as a tenant A test user and
  try every route against tenant B's data. Any success is a critical finding with the exact
  request as proof.
- Needs: a test deployment URL, two test tenants with test users, and their logins stored as
  secrets by the owner.

## Open question for the owner

The owner will send their own list of the exact tests they want. Each item will be marked as
(a) solid with a free tool, (b) possible with AI help but with limits, or (c) not possible or not
worth it. No item is dropped without the owner deciding.
