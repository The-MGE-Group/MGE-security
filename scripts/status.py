#!/usr/bin/env python3
"""Check every project in projects.yml: are both scans switched on, and did their last runs pass?

Usage:  python3 scripts/status.py            (all projects)
        python3 scripts/status.py owner/repo (one project, listed or not)

Needs the GitHub CLI (`gh`), logged in as someone who can read each repository. Run it on your
own computer after `gh auth login` and it sees every organization you belong to. In a Claude Code
cloud session it only sees repositories attached to the session.

Exit code 1 if anything needs attention, so it can also run on a schedule.
"""
import base64
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import yaml

HOME_ORG = "the-mge-group"
PR_REF = "MGE-security/.github/workflows/pr-scan.yml"
WEEKLY_REF = "MGE-security/.github/workflows/weekly-scan.yml"
STALE_DAYS = 8  # a weekly scan older than this has missed its Monday


def gh(path):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return json.loads(r.stdout)


def last_run(repo, wf_path):
    """Newest finished run of one workflow file: (conclusion, date, event) or None."""
    runs = gh(f"repos/{repo}/actions/workflows/{Path(wf_path).name}/runs?per_page=10&status=completed")
    for run in (runs or {}).get("workflow_runs", []):
        return run["conclusion"], run["created_at"][:10], run["event"]
    return None


def check(entry):
    repo, wants_weekly = entry["repo"], entry.get("weekly", True)
    outside = repo.split("/")[0].lower() != HOME_ORG
    todo = []
    if gh(f"repos/{repo}") is None:
        return [f"can't read {repo}: wrong name, or this login can't see it"], {}

    files = gh(f"repos/{repo}/contents/.github/workflows") or []
    found = {}
    for f in files if isinstance(files, list) else []:
        if not f["name"].endswith((".yml", ".yaml")):
            continue
        body = base64.b64decode((gh(f"repos/{repo}/contents/{f['path']}") or {}).get("content", "")).decode()
        if PR_REF in body:
            found["pr"] = (f["path"], body)
        if WEEKLY_REF in body:
            found["weekly"] = (f["path"], body)

    info = {}
    # Pull-request scan
    if "pr" not in found:
        todo.append("PR scan not switched on (add templates/mge-security.yml)")
    else:
        run = last_run(repo, found["pr"][0])
        info["pr"] = run
        if run and run[0] not in ("success", "skipped"):
            todo.append(f"PR scan: last run {run[0]} on {run[1]}")

    # Weekly scan
    if not wants_weekly:
        info["weekly"] = "not needed"
    elif "weekly" not in found:
        todo.append("weekly scan not switched on (needs a test deployment, see docs/ADD-A-PROJECT.md)")
    else:
        path, body = found["weekly"]
        if outside and "secrets: inherit" in body:
            todo.append("weekly scan uses `secrets: inherit`, which GitHub ignores across organizations: "
                        "use templates/mge-security-weekly-outside.yml")
        if "CHANGE" in body:
            todo.append("weekly scan file still has CHANGE placeholders")
        run = last_run(repo, path)
        info["weekly"] = run
        if not run:
            todo.append("weekly scan has never finished a run (start it once: Actions, MGE Security weekly, Run workflow)")
        else:
            if run[0] != "success":
                todo.append(f"weekly scan: last run {run[0]} on {run[1]}")
            age = (dt.date.today() - dt.date.fromisoformat(run[1])).days
            if age > STALE_DAYS:
                todo.append(f"weekly scan last ran {age} days ago (schedule not firing?)")
        if gh(f"repos/{repo}/contents/.mge-security/access-test.json") is None:
            info["access"] = "none"
            if entry.get("access_test", True):
                todo.append("no access test (.mge-security/access-test.json): the logged-in side is not tested. "
                            "If the site has no logins, set access_test: false in projects.yml")
    return todo, info


def fmt(run):
    if run is None:
        return "never ran"
    if isinstance(run, str):
        return run
    return f"{run[0]} {run[1]}"


def main():
    if len(sys.argv) > 1:
        entries = [{"repo": sys.argv[1]}]
    else:
        entries = yaml.safe_load(Path(__file__).resolve().parent.parent.joinpath("projects.yml").read_text())["projects"]
    problems = 0
    for e in entries:
        todo, info = check(e)
        mark = "OK  " if not todo else "TODO"
        print(f"{mark} {e['repo']}   PR: {fmt(info.get('pr', '-'))}   weekly: {fmt(info.get('weekly', '-'))}")
        for t in todo:
            print(f"       - {t}")
        problems += bool(todo)
    print(f"\n{len(entries) - problems} of {len(entries)} projects fully covered.")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
