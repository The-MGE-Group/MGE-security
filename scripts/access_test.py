#!/usr/bin/env python3
"""Cross-tenant and role access tests against a running TEST deployment.

Reads the project's config (default .mge-security/access-test.json), logs in as each test
user, and checks two things:
  1. App routes: every listed request must be refused (or allowed) as the config says.
  2. Database: with each user's login, Supabase must return no rows that belong to another
     tenant, for every table that has a tenant column. Logged-out visitors must get none.

Proof is the exact request. Tokens and passwords are never written out.
A check that should be ALLOWED and isn't means the test itself is broken (for example a failed
login), so the whole run is marked as not finished instead of passed.

Writes $RAW_DIR/access.json and $RAW_DIR/status/access.
"""
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAW = Path(os.environ["RAW_DIR"])
TARGET = os.environ["TARGET_URL"].rstrip("/")
CONFIG = Path(os.environ.get("ACCESS_CONFIG", ".mge-security/access-test.json"))
SECRETS = json.loads(os.environ.get("ALL_SECRETS") or "{}")
BYPASS = os.environ.get("BYPASS_SECRET", "")
(RAW / "status").mkdir(parents=True, exist_ok=True)


def done(status, findings=(), uncovered=()):
    (RAW / "access.json").write_text(json.dumps({"findings": list(findings), "uncovered_routes": list(uncovered)}, indent=2))
    (RAW / "status" / "access").write_text(status)
    print(status)
    sys.exit(0)


if not CONFIG.exists():
    done(f"skipped (no {CONFIG} in the project, so no access tests are defined)")

cfg = json.loads(CONFIG.read_text())


def secret(name):
    value = SECRETS.get(name) or os.environ.get(name)
    if not value:
        done(f"failed: the secret {name} named in {CONFIG} is not set in this repository")
    return value


def request(method, url, headers=None, body=None):
    h = dict(headers or {})
    if BYPASS and url.startswith(TARGET):
        h["x-vercel-protection-bypass"] = BYPASS
    data = json.dumps(body).encode() if body is not None else None
    if data:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=h)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=30) as r:
            return r.status, r.read(2_000_000).decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(2_000_000).decode(errors="replace")
    except Exception as e:  # network problem: the test cannot judge this request
        return None, str(e)


# ---------- Log in every test user (Supabase email + password) ----------
supa = cfg.get("supabase_url", "").rstrip("/")
# The public (anon or publishable) key is public by design, so it may be written in the config.
anon_key = cfg.get("supabase_anon_key") or (secret(cfg["supabase_anon_key_secret"]) if cfg.get("supabase_anon_key_secret") else "")
sessions, users = {}, cfg.get("users", {})
for label, u in users.items():
    code, body = request("POST", f"{supa}/auth/v1/token?grant_type=password",
                         {"apikey": anon_key},
                         {"email": u.get("email") or secret(u["email_secret"]), "password": secret(u["password_secret"])})
    if code != 200:
        done(f"failed: could not log in test user '{label}' (HTTP {code})")
    sessions[label] = json.loads(body)


def auth_headers(label):
    """How the app expects the login: a bearer header, or the cookie @supabase/ssr sets."""
    if label is None:
        return {}
    sess = sessions[label]
    send = cfg.get("send_token_as", "bearer")
    if send == "bearer":
        return {"Authorization": f"Bearer {sess['access_token']}"}
    name = send["cookie"]
    value = "base64-" + base64.urlsafe_b64encode(json.dumps(sess).encode()).decode().rstrip("=")
    chunks = [value[i:i + 3180] for i in range(0, len(value), 3180)]
    cookie = (f"{name}={chunks[0]}" if len(chunks) == 1
              else "; ".join(f"{name}.{i}={c}" for i, c in enumerate(chunks)))
    return {"Cookie": cookie}


def who(label):
    if label is None:
        return "a logged-out visitor"
    u = users[label]
    return f"test user `{label}` (tenant {u.get('tenant', '?')}, role {u.get('role', '?')})"


findings, broken = [], []
tenants = cfg.get("tenants", {})

# ---------- Every tenant route found in the code, tried as the wrong tenant ----------
auto = []
tr = cfg.get("tenant_routes")
if tr:
    param = tr.get("param", ":tenantId")
    found = set()
    route_rx = re.compile(r"\.(get|post|put|patch|delete)\(\s*[\"'`](/[^\"'`]*" + re.escape(param) + r"[^\"'`]*)[\"'`]", re.I)
    for folder in tr.get("files", []):
        for f in sorted(Path(folder).rglob("*")):
            if f.suffix not in (".ts", ".js", ".mjs") or ".test." in f.name or not f.is_file():
                continue
            for method, path in route_rx.findall(f.read_text(errors="replace")):
                found.add((method.upper(), path))
    if not found:
        done(f"failed: tenant_routes found no routes containing {param} in {tr.get('files')}; check the config")
    order = {"GET": 0, "POST": 1, "PUT": 1, "PATCH": 1, "DELETE": 2}  # reads first, deletes last
    victim = tenants[tr["against"]]["id"]
    for method, path in sorted(found, key=lambda m: (order.get(m[0], 1), m[1])):
        concrete = re.sub(r":[A-Za-z_]\w*", lambda m: victim if m.group(0) == param else "00000000-0000-4000-8000-000000000000", path)
        auto.append({"as": tr["as"], "method": method, "path": tr.get("prefix", "") + concrete,
                     "against": tr["against"], "expect": "denied", "strict": True,
                     "body": None if method == "GET" else {}})

# ---------- 1. App routes ----------
for c in cfg.get("checks", []) + auto:
    label, method, path = c.get("as"), c.get("method", "GET").upper(), c["path"]
    against = c.get("against")
    marker = (tenants.get(against) or {}).get("marker") if against else None
    code, body = request(method, TARGET + path, auth_headers(label), c.get("body"))
    allowed = code is not None and 200 <= code < 300
    denied = code is not None and 300 <= code < 500  # any refusal or redirect (for example to the login page)
    req = f"`{method} {path}` as {who(label)}"
    if c.get("expect") == "allowed":
        if not allowed:
            broken.append(f"{req} should work but got HTTP {code}")
        continue
    if code is None or code >= 500:
        findings.append({"kind": "access", "severity": "medium", "key": f"route|{label}|{method}|{path}|error",
                         "title": f"Server error on a request that should be refused: {method} {path}",
                         "where": f"`{TARGET}{path}`",
                         "proof": f"Sent {req}; got {'no answer' if code is None else f'HTTP {code}'} instead of a refusal.",
                         "fix": "Make this route refuse the request cleanly (401, 403 or 404). A crash can hide a "
                                "missing check and can't be judged by this test."})
        continue
    same_tenant = against is None or bool(label and users[label].get("tenant") == against)
    # For cross-tenant reads, a marker proves the other tenant's data came back (an empty 200 is not a leak).
    # For role checks inside one tenant, any success is the problem.
    leaked = allowed and (same_tenant or c.get("strict") or marker is None or marker in body)
    if leaked:
        sev = "high" if same_tenant else "critical"
        what = (f"tenant {against}'s data" if not same_tenant else "an action this role should not be allowed")
        findings.append({"kind": "access", "severity": sev, "key": f"route|{label}|{method}|{path}",
                         "title": f"{'Cross-tenant access' if not same_tenant else 'Role check missing'}: "
                                  f"{who(label).split(' (')[0]} got {what} via {method} {path}",
                         "where": f"`{TARGET}{path}`",
                         "proof": f"Sent {req}; got HTTP {code}"
                                  + (f" and the response contains tenant {against}'s marker text `{marker}`." if marker else ".")
                                  + " Expected a refusal or a redirect to the login page. To reproduce: log in as that user on the "
                                    f"test deployment and repeat the same request.",
                         "fix": "Check in this route's code that the logged-in user belongs to the tenant (and has the "
                                "role) for the record before reading or changing it. Also check the Supabase row-level "
                                "security policy for the table behind it."})
    elif not denied and not allowed:
        broken.append(f"{req} gave HTTP {code}, which is neither allowed nor refused")

# ---------- 2. Database (Supabase REST API, row-level security) ----------
col = cfg.get("tenant_column", "tenant_id")
tables = list(cfg.get("tables", []))
if cfg.get("database_check", True) and supa:
    if not tables:
        code, body = request("GET", f"{supa}/rest/v1/", {"apikey": anon_key})
        try:
            defs = json.loads(body).get("definitions", {}) if code == 200 else {}
            tables = sorted(t for t, d in defs.items() if col in (d.get("properties") or {}))
        except json.JSONDecodeError:
            tables = []
        if not tables:
            broken.append(f"could not list database tables automatically (HTTP {code}); add a \"tables\" list to {CONFIG}")
    readers = [None] + list(users)
    for table in tables:
        for label in readers:
            mine = users[label].get("tenant") if label else None
            others = [t for t in tenants if t != mine]
            for other in others:
                tid = tenants[other]["id"]
                q = urllib.parse.urlencode({"select": col, col: f"eq.{tid}", "limit": "1"})
                h = {"apikey": anon_key}
                if label:
                    h["Authorization"] = f"Bearer {sessions[label]['access_token']}"
                code, body = request("GET", f"{supa}/rest/v1/{table}?{q}", h)
                try:
                    rows = json.loads(body) if code == 200 else []
                except json.JSONDecodeError:
                    rows = []
                if isinstance(rows, list) and rows:
                    findings.append({
                        "kind": "access", "severity": "critical", "key": f"db|{table}|{label}|{other}",
                        "title": f"Database leak: {who(label).split(' (')[0]} can read tenant {other}'s rows in `{table}`",
                        "where": f"Supabase table `{table}`",
                        "proof": f"As {who(label)}, `GET /rest/v1/{table}?{q}` returned rows belonging to tenant {other}.",
                        "fix": f"Turn on row-level security for `{table}` and add a policy that only returns rows whose "
                               f"`{col}` matches the user's own tenant."})
                elif code not in (200, 401, 403, 404):
                    broken.append(f"database check on `{table}` as {who(label)} got HTTP {code}")

# ---------- Which Next.js routes have no test ----------
uncovered = []
routes_dir = cfg.get("routes_dir")
if routes_dir and Path(routes_dir).is_dir():
    tested = [c["path"].split("?")[0] for c in cfg.get("checks", [])]
    for f in sorted(Path(routes_dir).rglob("*")):
        if not re.fullmatch(r"(page|route)\.(t|j)sx?", f.name):
            continue
        parts = [p for p in f.parent.relative_to(routes_dir).parts
                 if not (p.startswith("(") and p.endswith(")")) and not p.startswith("@")]
        if any(p.startswith("_") for p in parts):
            continue
        template = "/" + "/".join(parts)
        rx = "/" + "/".join(".*" if p.startswith("[[...") else ".+" if p.startswith("[...")
                            else "[^/]+" if p.startswith("[") else re.escape(p) for p in parts)
        if not any(re.fullmatch(rx.rstrip("/") or "/", t.rstrip("/") or "/") for t in tested):
            uncovered.append(template)

if broken:
    done("failed: the test itself did not work, so nothing is proven: " + "; ".join(broken[:5]), findings, uncovered)
done("ok" + (f" ({len(auto)} tenant routes tried automatically)" if auto else ""), findings, uncovered)
