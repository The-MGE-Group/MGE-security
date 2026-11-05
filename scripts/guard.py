#!/usr/bin/env python3
"""Refuse to scan production. Usage: guard.py <target-url> "<comma-separated production hosts>"
Exits 1 (and prints why) if the target is not a valid address, the list is empty, or the
target's host is on the list. Comparison ignores letter case, ports, paths and a trailing dot."""
import sys
import urllib.parse


def check(target, production):
    host = (urllib.parse.urlparse(target.strip()).hostname or "").rstrip(".").lower()
    prod = {h.strip().rstrip(".").lower() for h in production.split(",") if h.strip()}
    if not host:
        return f"target-url '{target}' is not a valid address"
    if not prod:
        return "production-hosts must list your production host names"
    if host in prod:
        return f"refusing to scan {host}: it is listed as production"
    return None


if __name__ == "__main__":
    problem = check(sys.argv[1], sys.argv[2])
    if problem:
        print(f"::error::{problem}")
        sys.exit(1)
    print("Target is not on the production list. Continuing.")
