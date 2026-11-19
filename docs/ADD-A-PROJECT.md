# Adding a project

Every project gets two things:

1. **Pull-request scan**: checks the code on every pull request. Every repository gets this.
2. **Weekly scan**: attacks a running **test** copy of the site once a week, including logging
   in as one customer and trying to read another customer's data. Only for projects with a
   running site.

The fast way: open Claude Code on this repository and type `/add-project owner/repo`. Claude
does everything below that it can and tells you the few clicks only you can do. This page is
the same steps by hand.

Check where everything stands at any time:

```bash
python3 scripts/status.py
```

Run it on your own computer after `gh auth login`, so it can see every organization you're in.

## Once per organization or account outside The-MGE-Group

Skip this for repositories inside The-MGE-Group.

1. **Allow the scan workflows.** In that organization: **Settings**, **Actions**, **General**,
   **Policies** ([GitHub docs](https://docs.github.com/en/organizations/managing-organization-settings/disabling-or-limiting-github-actions-for-your-organization)).
   If it says "Allow all actions and reusable workflows", nothing to do. If it limits them, tick
   "Allow actions created by GitHub" and add these two lines to the allowed list:
   ```
   The-MGE-Group/MGE-security/.github/workflows/pr-scan.yml@*, The-MGE-Group/MGE-security/.github/workflows/weekly-scan.yml@*
   ```
   For a repository under a personal account, the same setting is in the repository's own
   **Settings**, **Actions**, **General**.
2. **Let Claude in (optional, saves you the copying).** Install the Claude GitHub app on that
   organization or account: https://github.com/apps/claude/installations/select_target. Pick
   only the repositories you want scanned. Without it, Claude gives you the files to paste.
3. **Actions minutes.** On a free plan, private repositories get a monthly allowance of Actions
   minutes ([GitHub docs](https://docs.github.com/en/billing/concepts/product-billing/github-actions)).
   A pull-request scan takes 1 to 2 minutes; the weekly scans of MGE projects took 5 to 6 minutes in November 2026 (more with ZAP `full` mode).

## Steps for each project

1. Add it to [projects.yml](../projects.yml).
2. **Pull-request scan:** copy [templates/mge-security.yml](../templates/mge-security.yml) to
   `.github/workflows/mge-security.yml`. Same file inside and outside the organization.
3. **Dependabot:** copy [templates/dependabot.yml](../templates/dependabot.yml) to
   `.github/dependabot.yml`, unless the project already has one.
4. **Weekly scan** (skip if there's no running site):
   - You need a test copy that never holds real customer data: a Vercel preview of a `staging`
     branch, and a separate test Supabase project.
   - Copy the weekly file to `.github/workflows/mge-security-weekly.yml` and fill in the `CHANGE`
     lines:
     - inside The-MGE-Group: [templates/mge-security-weekly.yml](../templates/mge-security-weekly.yml)
     - **outside: [templates/mge-security-weekly-outside.yml](../templates/mge-security-weekly-outside.yml)**.
       GitHub won't hand secrets to another organization's workflow with `secrets: inherit`
       ([GitHub docs](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)),
       so this version names each one.
   - If the site has logins, copy [templates/access-test.json](../templates/access-test.json) to
     `.mge-security/access-test.json` and fill it in (README, "Switching on the weekly scan").
     Outside the organization, each `password_secret` must be `MGE_TEST_PASSWORD`,
     `MGE_TEST_PASSWORD_2` or `MGE_TEST_PASSWORD_3`.
5. **Secrets.** In the project: **Settings**, **Secrets and variables**, **Actions**, **New
   repository secret**. Only add the ones that apply:

   | Secret | When |
   |---|---|
   | `VERCEL_AUTOMATION_BYPASS_SECRET` | the test site is on Vercel with deployment protection on |
   | `SUPABASE_ADVISOR_TOKEN` | you filled in `supabase-project-ref` |
   | `MGE_TEST_PASSWORD` (and `_2`, `_3`) | the access test logs in |

6. Merge. Then start the weekly scan once by hand: **Actions**, **MGE Security weekly**, **Run
   workflow**. Read its report (the run's **Summary**).
7. Run `python3 scripts/status.py owner/repo`. It should say `OK`.
