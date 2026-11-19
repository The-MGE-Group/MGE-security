---
name: add-project
description: Switch on MGE Security (pull-request scan, weekly scan with access test, Dependabot) for one repository, inside or outside The-MGE-Group, and record it in projects.yml. Use when the owner says "add <repo> to security", "set up the scans for <repo>", or types /add-project owner/repo.
---

# Add a project to MGE Security

Argument: `owner/repo`. If none was given, ask for it, and nothing else.

The human checklist is `docs/ADD-A-PROJECT.md`. This skill does the same steps; read that file
first. Do the work, don't explain the system. Finish with one short list of what only the owner
can do, with direct links.

## 1. Get access

- Call `add_repo` with `access: "push"`.
- If refused because the Claude GitHub app isn't on that organization or account: tell the owner
  to install it at https://github.com/apps/claude/installations/select_target (only that
  repository is enough), and offer to continue in paste mode: you write the files into this
  repository's scratchpad and they copy them. Don't retry `add_repo`.
- Note whether the owner is `The-MGE-Group` (inside) or anything else (outside).

## 2. Look before writing

Run `python3 scripts/status.py owner/repo` first. Only add what's missing; never overwrite a
working setup.

From the repository, find out:
- Is there a running site? (Next.js, Vite, an API, `vercel.json`.) Static pages and asset
  repositories get the pull-request scan only (`weekly: false`).
- Does it have logins and more than one customer (tenant)? Find the tenant column (often
  `tenant_id`, `org_id`, `workspace_id`) and the routes with the tenant in the address.
- Supabase: list projects on both Supabase connectors. Find its production project and whether a
  separate **test** project exists. Never point the weekly scan or the access test at production.
- Vercel: `curl https://api.vercel.com/v9/projects?limit=100` (and `?teamId=` for each team from
  `/v2/teams`). Find the production domains and whether a `staging` branch preview exists.
- If something isn't visible from here (an outside Vercel team, an outside Supabase org), ask the
  owner for that one fact: the test address, the production host names, the test Supabase ref.

## 3. Write the files, on a branch in the project

Branch `mge-security-setup`. Add only what's missing:
- `.github/workflows/mge-security.yml` from `templates/mge-security.yml`, unchanged.
- `.github/dependabot.yml` from `templates/dependabot.yml`, if the project has none. Adjust the
  ecosystems to what the repository actually uses.
- If `weekly: true` and a test deployment exists:
  - inside: `templates/mge-security-weekly.yml`; outside: `templates/mge-security-weekly-outside.yml`.
    Fill every `CHANGE`. `production-hosts` lists every production domain and every Vercel
    production alias. Pick a cron minute and hour no other project uses (see projects.yml notes).
  - `.mge-security/access-test.json` from `templates/access-test.json`, if it has logins. Fill
    in what the code shows (tenant column, `tenant_routes.files`, Supabase URL and publishable
    key of the TEST project). Outside, `password_secret` must be `MGE_TEST_PASSWORD`, `_2` or `_3`.
  - Test users and test tenants: if they don't exist, ask the owner before creating any. Create
    them only in the TEST Supabase project, never production.
- If there is no test deployment yet, don't add the weekly file. Tell the owner what's needed
  (a `staging` branch on Vercel and a test Supabase project) and offer to set it up.

Commit, push, and open a pull request in the project titled "Switch on MGE Security scans".
The owner asked for this by running the skill.

## 4. Record it here

Add or update the entry in `projects.yml` (repo, `weekly`, `access_test` if no logins, a note
with the test Supabase project and anything still missing). Commit on this repository's
working branch and push.

## 5. Hand over

One short message:
- The pull request link.
- Outside only, once per organization: the Actions policy step from `docs/ADD-A-PROJECT.md`,
  only if the organization limits actions (say "check" if you can't see it).
- Secrets to add, only the ones that apply, each with its direct link:
  `https://github.com/OWNER/REPO/settings/secrets/actions/new`. Say where each value comes from.
- "After merging and adding secrets: Actions, MGE Security weekly, Run workflow. Then tell me and
  I'll check it." When they come back, run `python3 scripts/status.py owner/repo` and read the
  weekly report's findings with them.
