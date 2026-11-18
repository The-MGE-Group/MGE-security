"""Checks rules/osv-exceptions.toml: every entry has an id, a reason and an end date at most
90 days away, so nothing is allowed forever. Run: python3 scripts/test_exceptions.py"""
import datetime
import sys
import tomllib

MAX_DAYS = 90
today = datetime.date.today()
entries = tomllib.load(open("rules/osv-exceptions.toml", "rb")).get("IgnoredVulns", [])
bad = []
for e in entries:
    name = e.get("id") or "(no id)"
    until = e.get("ignoreUntil")
    if isinstance(until, datetime.datetime):
        until = until.date()
    if not e.get("id"):
        bad.append(f"{name}: missing id")
    if len((e.get("reason") or "").strip()) < 20:
        bad.append(f"{name}: needs a reason that says why it can't be triggered")
    if not isinstance(until, datetime.date):
        bad.append(f"{name}: needs an end date (ignoreUntil = YYYY-MM-DD)")
    elif (until - today).days > MAX_DAYS:
        bad.append(f"{name}: end date {until} is more than {MAX_DAYS} days away")
if bad:
    sys.exit("rules/osv-exceptions.toml:\n- " + "\n- ".join(bad))
print(f"{len(entries)} allowed advisory(ies), each with a reason and an end date")
