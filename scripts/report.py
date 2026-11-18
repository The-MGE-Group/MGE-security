#!/usr/bin/env python3
"""Turn the raw scanner output into one plain-English report.

Reads:   $RAW_DIR/*.json      raw output from each scanner
         $RAW_DIR/status/*    "ok" or a failure message, one file per scanner
Writes:  $OUT_DIR/report.md     the human report (also used as the job summary)
         $OUT_DIR/findings.json machine-readable list (used by the self-test and issue creation)
Prints:  blocking=<n> and failed=<n> lines for $GITHUB_OUTPUT

Rule: a finding is only reported when the scanner gives proof (a file and line,
or a package name, version and lockfile). Secrets are never written out.
"""
import hashlib
import json
import os
import re
import sys
import tomllib
from pathlib import Path

RAW = Path(os.environ["RAW_DIR"])
OUT = Path(os.environ["OUT_DIR"])
BLOCK_ON = os.environ.get("BLOCK_ON", "high").lower()
SCAN_PATH = os.environ.get("SCAN_PATH", ".")
SERVER = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
SHA = os.environ.get("PROOF_SHA", os.environ.get("GITHUB_SHA", ""))

ORDER = ["critical", "high", "medium", "low", "unknown"]
BLOCK_LEVELS = {
    "critical": {"critical"},
    "high": {"critical", "high"},
    "medium": {"critical", "high", "medium"},
    "none": set(),
}[BLOCK_ON]

# Licenses that can force you to publish your own source code.
STRONG_COPYLEFT = re.compile(r"\b(AGPL|GPL|SSPL|EUPL|OSL|CPAL|RPL|BUSL|Commons-Clause|CC-BY-NC|CC-BY-SA)", re.I)

KIND = os.environ.get("SCAN_KIND", "pr")
TARGET = os.environ.get("TARGET_URL", "")
TOOLS = {
    "pr": {
        "gitleaks": "Gitleaks (passwords and keys in code and git history)",
        "trufflehog": "TruffleHog (keys that are confirmed live)",
        "osv": "OSV-Scanner (known-vulnerable or malicious packages, and licenses)",
        "sbom": "Package list (SBOM, CycloneDX format, attached to this run)",
        "opengrep": "Opengrep (risky code patterns, community rules plus MGE rules)",
    },
    "weekly": {
        "access": "Access tests (cross-tenant and role checks, app routes and database)",
        "zap": "ZAP (scans the running site from outside)",
        "nuclei": "Nuclei (known flaws and exposed files on the running site)",
        "testssl": "testssl.sh (HTTPS certificate and encryption settings)",
        "supabase": "Supabase security advisor (database security settings)",
        "subfinder": "Subfinder (public list of your subdomains, information only)",
    },
}[KIND]


def load(name, lines=False):
    p = RAW / name
    if not p.exists() or p.stat().st_size == 0:
        return None
    text = p.read_text(errors="replace").strip()
    if lines:  # TruffleHog prints one JSON object per line.
        return [json.loads(x) for x in text.splitlines() if x.strip().startswith("{")]
    return json.loads(text)


def is_ok(s):
    return s.startswith("ok")


def is_skipped(s):
    return s.startswith("skipped")


def status(tool):
    p = RAW / "status" / tool
    return p.read_text().strip() if p.exists() else "did not run"


def link(path, line=None):
    """Clickable link to the exact file and line in the scanned commit."""
    if not REPO or not SHA:
        return f"`{path}`" + (f" line {line}" if line else "")
    anchor = f"#L{line}" if line else ""
    label = f"{path}" + (f" line {line}" if line else "")
    return f"[{label}]({SERVER}/{REPO}/blob/{SHA}/{path}{anchor})"


def rel(path):
    """Paths from the scanners, made relative to the repository root."""
    p = str(path)
    for prefix in (os.environ.get("GITHUB_WORKSPACE", "") + "/", "./"):
        if prefix != "/" and p.startswith(prefix):
            p = p[len(prefix):]
    return p


def vkey(v):
    """Rough version order: 4.17.19 > 4.17.5. Good enough to pick an upgrade target."""
    return [int(x) if x.isdigit() else -1 for x in re.split(r"[.+-]", str(v))]


findings = []


def add(tool, kind, severity, title, where, proof, fix, key):
    findings.append({
        "tool": tool, "kind": kind, "severity": severity, "title": title,
        "where": where, "proof": proof, "fix": fix,
        "id": hashlib.sha256(f"{tool}|{key}".encode()).hexdigest()[:16],
    })


# ---------- Gitleaks ----------
seen = set()
for name in ("gitleaks-files.json", "gitleaks-history.json"):
    for f in load(name) or []:
        path, line = rel(f.get("File", "")), f.get("StartLine")
        key = (f.get("RuleID"), path, line, f.get("Commit", ""))
        if (f.get("RuleID"), path, line) in seen:
            continue
        seen.add((f.get("RuleID"), path, line))
        commit = f.get("Commit")
        where = link(path, line) + (f", added in commit `{commit[:12]}`" if commit else "")
        add("gitleaks", "secret", "high",
            f"Possible secret in code: {f.get('Description') or f.get('RuleID')}",
            where,
            f"Gitleaks rule `{f.get('RuleID')}` matched at {path} line {line}. The value is hidden in this report.",
            "If it is a real key: revoke it at the provider first (deleting it from code is not enough, it stays in git history), "
            "then move it to an environment secret. If it is not a secret, add this line to a `.gitleaksignore` file "
            f"in the project: `{f.get('Fingerprint', '')}`",
            "|".join(map(str, key)))

# ---------- TruffleHog (verified only) ----------
for f in load("trufflehog.json", lines=True) or []:
    data = (f.get("SourceMetadata") or {}).get("Data") or {}
    meta = data.get("Filesystem") or data.get("Git") or {}
    path, line, commit = rel(meta.get("file", "")), meta.get("line"), meta.get("commit")
    detector = f.get("DetectorName", "unknown")
    where = link(path, line) + (f", in commit `{commit[:12]}`" if commit else "")
    add("trufflehog", "secret", "critical",
        f"LIVE {detector} key found (TruffleHog confirmed it works)",
        where,
        f"TruffleHog tested this {detector} credential against {detector} and it was accepted. The value is hidden in this report.",
        f"Revoke this {detector} key now at the provider, then check the provider's logs for use you don't recognise. "
        "Removing it from code does not make it safe; it is still in git history.",
        f"{detector}|{path}|{line}|{commit}")

# ---------- OSV-Scanner: vulnerabilities, malware, licenses ----------
osv = load("osv.json") or {}
for result in osv.get("results", []) if isinstance(osv, dict) else []:
    lockfile = rel((result.get("source") or {}).get("path", ""))
    for pkg in result.get("packages", []):
        p = pkg.get("package", {})
        name, version, eco = p.get("name"), p.get("version"), p.get("ecosystem")
        vulns = {v["id"]: v for v in pkg.get("vulnerabilities", [])}
        advisories = []  # one entry per group of duplicate advisories
        for g in pkg.get("groups", []):
            ids = g.get("ids", [])
            members = [vulns[i] for i in ids if i in vulns]
            all_ids = sorted(set(ids) | set(g.get("aliases", [])))
            malicious = any(i.startswith("MAL-") for i in all_ids) or any(
                "malicious" in (m.get("summary") or "").lower() for m in members)
            sev = "unknown"
            try:
                score = float(g.get("max_severity") or "")
                sev = "critical" if score >= 9 else "high" if score >= 7 else "medium" if score >= 4 else "low"
            except ValueError:
                words = [(m.get("database_specific") or {}).get("severity", "").lower() for m in members]
                words = ["medium" if w == "moderate" else w for w in words]
                sev = next((lvl for lvl in ORDER if lvl in words), "unknown")
            fixed = [ev["fixed"] for m in members for a in m.get("affected", [])
                     if (a.get("package") or {}).get("name") == name
                     for r in a.get("ranges", []) for ev in r.get("events", []) if "fixed" in ev]
            later = [f for f in fixed if vkey(f) > vkey(version)]
            advisories.append({
                "id": next((i for i in all_ids if i.startswith(("GHSA-", "MAL-"))), all_ids[0] if all_ids else "?"),
                "sev": sev, "malicious": malicious,
                "summary": next((m.get("summary") for m in members if m.get("summary")), ""),
                "fixed": min(later, key=vkey) if later else None})
        if not advisories:
            pass
        elif any(a["malicious"] for a in advisories):
            ids = sorted({a["id"] for a in advisories})
            add("osv", "malicious-package", "critical", f"Malicious package: {name}@{version}",
                link(lockfile),
                f"`{name}@{version}` ({eco}) is listed in {link(lockfile)} and is reported as malicious: "
                + ", ".join(f"[{i}](https://osv.dev/vulnerability/{i})" for i in ids) + ".",
                f"Remove `{name}` now. Treat any computer or server that installed it as compromised: "
                "rotate keys that were present there.",
                f"{lockfile}|{name}|{version}|malicious")
        else:
            advisories.sort(key=lambda a: ORDER.index(a["sev"]))
            sev = advisories[0]["sev"]
            lines = "; ".join(f"[{a['id']}](https://osv.dev/vulnerability/{a['id']}) ({a['sev']}) {a['summary']}".strip()
                              for a in advisories[:10])
            needs = [a["fixed"] for a in advisories]
            if all(needs):
                fix = f"Upgrade `{name}` to version {max(needs, key=vkey)} or later, which fixes all of these."
            else:
                fix = (f"At least one of these has no fixed version yet. Upgrade where possible, consider replacing "
                       f"`{name}`, or record why it is acceptable in `osv-scanner.toml`.")
            n = len(advisories)
            add("osv", "vulnerable-dependency", sev,
                f"{name}@{version} has {n} known vulnerabilit{'y' if n == 1 else 'ies'}"
                + (f": {advisories[0]['summary']}" if n == 1 and advisories[0]["summary"] else ""),
                link(lockfile),
                f"`{name}@{version}` ({eco}) is listed in {link(lockfile)} and matches: {lines}.",
                fix, f"{lockfile}|{name}|{version}|vulnerable")
        bad = pkg.get("license_violations") or []
        if bad:
            strong = any(STRONG_COPYLEFT.search(b) for b in bad)
            add("osv", "license", "high" if strong else "medium",
                f"License risk: {name}@{version} uses {', '.join(bad)}",
                link(lockfile),
                f"`{name}@{version}` in {link(lockfile)} is licensed {', '.join(bad)} according to deps.dev, "
                "which is not on the allowed list.",
                ("This license can require you to publish your own source code. Replace the package, or get "
                 "legal advice before keeping it." if strong else
                 "Check the license terms. If it is acceptable, add it to the `allowed-licenses` setting."),
                f"{lockfile}|{name}|{version}|license")

# ---------- Opengrep ----------
og = load("opengrep.json") or {}
SEV = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}
for r in og.get("results", []) if isinstance(og, dict) else []:
    path, line = rel(r.get("path", "")), (r.get("start") or {}).get("line")
    extra = r.get("extra", {})
    rule = r.get("check_id", "")
    short = rule.split(".")[-1]
    add("opengrep", "code", SEV.get(extra.get("severity", "").upper(), "unknown"),
        f"Risky code pattern: {short}",
        link(path, line),
        f"Rule `{short}` matched at {path} line {line}: {extra.get('message', '').strip()}",
        "Read the rule message above and change the code. If it is a false alarm, put "
        f"`// nosemgrep: {short} -- <reason>` on that line or the line above. The rule name must come first: "
        "words after the colon are read as rule names.",
        f"{rule}|{path}|{line}")


# ---------- Access tests (written by access_test.py, already in finding form) ----------
access = load("access.json") or {}
for f in access.get("findings", []):
    add("access", f["kind"], f["severity"], f["title"], f["where"], f["proof"], f["fix"], f["key"])
inventory = {"Routes in the code that no access test covers": access.get("uncovered_routes", [])}

# Advisories OSV-Scanner was told to allow, so they stay visible in every report.
if (RAW / "osv-config.toml").exists():
    try:
        allowed = tomllib.loads((RAW / "osv-config.toml").read_text()).get("IgnoredVulns", [])
    except tomllib.TOMLDecodeError as e:
        allowed = [{"id": "osv-scanner.toml could not be read", "reason": str(e)}]
    inventory["Advisories allowed for now (not blocking)"] = [
        f"{e.get('id')} until {e.get('ignoreUntil', 'no end date')}: {e.get('reason', 'no reason given')}"
        for e in allowed]

# ---------- ZAP ----------
zap = load("zap.json") or {}
RISK = {"3": "high", "2": "medium", "1": "low"}
for site in zap.get("site", []) if isinstance(zap, dict) else []:
    for a in site.get("alerts", []):
        sev = RISK.get(str(a.get("riskcode")))
        if not sev or str(a.get("confidence")) == "0":  # informational or marked false positive
            continue
        inst = a.get("instances", [])
        shown = "; ".join(f"`{i.get('method', 'GET')} {i.get('uri')}`" + (f" ({i['param']})" if i.get("param") else "")
                          for i in inst[:5])
        evidence = next((i.get("evidence") for i in inst if i.get("evidence")), "")
        add("zap", "running-site", sev, f"{a.get('alert') or a.get('name')} (seen on {len(inst)} address(es))",
            shown or site.get("@name", TARGET),
            f"ZAP rule {a.get('pluginid')} flagged these requests: {shown}."
            + (f" Evidence: `{evidence[:200]}`." if evidence else "")
            + " " + re.sub(r"<[^>]+>", "", a.get("desc", ""))[:400],
            re.sub(r"<[^>]+>", "", a.get("solution", "")).strip()[:600] or "See the ZAP rule description.",
            f"{a.get('pluginid')}|{a.get('alert')}")

# ---------- Nuclei ----------
NSEV = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}
for r in load("nuclei.jsonl", lines=True) or []:
    info = r.get("info", {})
    sev = NSEV.get(str(info.get("severity", "")).lower())
    if not sev:
        continue
    where = r.get("matched-at") or r.get("host", "")
    # Never copy the curl command or extracted values: they can contain the bypass secret or leaked data.
    add("nuclei", "running-site", sev, f"{info.get('name', r.get('template-id'))}",
        f"`{where}`",
        f"Nuclei template `{r.get('template-id')}` matched at `{where}`. "
        + (info.get("description") or "").strip()[:400],
        (info.get("remediation") or "Check the address above and remove or protect what it exposes.").strip()[:600],
        f"{r.get('template-id')}|{where}")

# ---------- testssl.sh ----------
TSEV = {"CRITICAL": "critical", "HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
ts = load("testssl.json") or []
ciphers = {}
for r in ts if isinstance(ts, list) else ts.get("scanResult", []):
    sev, rid = TSEV.get(str(r.get("severity", "")).upper()), str(r.get("id", ""))
    if not sev or rid == "overall_grade":  # the grade only repeats the findings below
        continue
    host = f"{r.get('ip', '')}:{r.get('port', '')}".strip(":")
    if rid.startswith("cipher-") or rid.startswith("cipher_"):  # one finding for all old ciphers
        ciphers.setdefault((host, sev), []).append(f"{r.get('finding')}")
        continue
    add("testssl", "tls", sev, f"HTTPS setting: {rid}", f"`{host}`",
        f"testssl.sh check `{rid}` on `{host}` reported: {r.get('finding')}",
        "If the site is hosted on Vercel, Vercel controls these settings; check it is a real problem on your "
        "own domain before acting. Otherwise fix the server's HTTPS configuration.",
        f"{rid}|{host}")
for (host, sev), found in ciphers.items():
    add("testssl", "tls", sev, f"HTTPS: {len(found)} old encryption cipher(s) still offered", f"`{host}`",
        f"testssl.sh on `{host}` found: " + "; ".join(found[:10]),
        "Turn off these ciphers in the server's HTTPS settings (on Vercel, Vercel controls this).",
        f"ciphers|{host}|{sev}")

# ---------- Supabase security advisor ----------
LEVEL = {"ERROR": "high", "WARN": "medium", "INFO": "low"}
for l in (load("supabase.json") or {}).get("lints", []):
    sev = LEVEL.get(str(l.get("level", "")).upper(), "unknown")
    meta = l.get("metadata") or {}
    obj = ".".join(x for x in (meta.get("schema"), meta.get("name")) if x)
    add("supabase", "database", sev, f"Supabase advisor: {l.get('title') or l.get('name')}" + (f" on `{obj}`" if obj else ""),
        f"Supabase project, object `{obj or 'project'}`",
        f"Supabase lint `{l.get('name')}`: {l.get('detail') or l.get('description', '')}",
        f"{l.get('description', '').strip()} How to fix: {l.get('remediation', '')}".strip(),
        l.get("cache_key") or f"{l.get('name')}|{obj}")

# ---------- Subfinder (information only, never a finding) ----------
subs = sorted({r.get("host") for r in load("subfinder.jsonl", lines=True) or [] if r.get("host")})
inventory["Subdomains listed in public sources (not scanned)"] = subs

# ---------- Write the report ----------
findings.sort(key=lambda f: (ORDER.index(f["severity"]), f["tool"], f["title"]))
counts = {s: sum(f["severity"] == s for f in findings) for s in ORDER}
for f in findings:
    f["blocks"] = f["severity"] in BLOCK_LEVELS
blocking = [f for f in findings if f["blocks"]]
failed = {t: status(t) for t in TOOLS if not is_ok(status(t)) and not is_skipped(status(t))}
skipped = [t for t in TOOLS if is_skipped(status(t))]
gate = "merging" if KIND == "pr" else "this scan passes"

if failed:
    verdict = "**Could not finish.** One or more checks did not run, so this project has NOT been checked. See below."
elif blocking:
    verdict = f"**Blocked.** {len(blocking)} problem(s) at or above the \"{BLOCK_ON}\" level must be fixed before {gate}."
elif findings:
    verdict = f"**Passed with notes.** No problem at or above the \"{BLOCK_ON}\" level. {len(findings)} lower-level note(s) below."
else:
    verdict = "**Passed.** None of the checks that ran found a problem."
if skipped and not failed:
    verdict += f" {len(skipped)} check(s) were skipped; see below."

title = "pull-request scan" if KIND == "pr" else "weekly scan of a test deployment"
scope = (f"Scanned: `{SCAN_PATH}` at commit `{SHA[:12]}`." if KIND == "pr"
         else f"Scanned: `{TARGET}` (a test deployment, never production).")
md = [f"# MGE Security: {title}", "", verdict, "",
      f"{scope} Blocks at: {BLOCK_ON}.", "",
      "| Level | Count |", "|---|---|"] + [f"| {s} | {counts[s]} |" for s in ORDER] + [""]

md += ["## Checks", ""]
for t, label in TOOLS.items():
    s = status(t)
    icon = "✅" if is_ok(s) else "⏭️" if is_skipped(s) else "❌"
    extra = "" if s == "ok" else f" ({s[2:].strip(' ()')})" if is_ok(s) else f": **{s}**"
    md.append(f"- {icon} {label}{extra}")
md.append("")

if findings:
    md += ["## What was found", ""]
    for n, f in enumerate(findings[:100], 1):
        md += [f"### {n}. [{f['severity'].upper()}] {f['title']}", "",
               f"- **Where:** {f['where']}",
               f"- **Proof:** {f['proof']}",
               f"- **What to do:** {f['fix']}", ""]
    if len(findings) > 100:
        md += [f"_{len(findings) - 100} more in the `findings.json` file attached to this run._", ""]

for heading, items in inventory.items():
    if items:
        md += [f"## {heading}", ""] + [f"- `{i}`" for i in items[:200]]
        md += ([f"- _{len(items) - 200} more in `findings.json`_"] if len(items) > 200 else []) + [""]

NOT_CHECKED = {
    "pr": [
        "- Whether the running app is safe (logins, permissions, one customer seeing another customer's data). "
        "The weekly scan covers that against a test deployment.",
        "- Logic mistakes and new kinds of attack. The code rules only know common, well-known patterns.",
        "- Vulnerabilities nobody has published yet, and malicious packages not yet reported.",
        "- Packages not pinned in a lockfile (for example a `package.json` without `pnpm-lock.yaml`).",
        "- Secrets that don't match a known format. TruffleHog only reports keys it could prove are live.",
        "- License results are a warning, not legal advice. They come from deps.dev and can be wrong.",
    ],
    "weekly": [
        "- Production. Only the test deployment above was scanned.",
        "- Routes and tables the access tests don't list. They only prove what they test; see any "
        "\"not covered\" list above.",
        "- Without `scan_as` in the access config, ZAP and Nuclei scan as a logged-out visitor. With it they log in, "
        "but ZAP's quick scan still only follows links on pages, not the API calls a page makes; Nuclei is given every API "
        "address the user may read.",
        "- Business rules nobody wrote down, and new kinds of attack.",
        "- HTTPS on your own domain, if the test deployment uses a Vercel address: then testssl.sh is testing Vercel's settings.",
    ],
}[KIND]
md += ["## What this scan does NOT check", ""] + NOT_CHECKED + [
       "", "A pass means these tools found nothing. It does not mean the software is secure.", ""]

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "report.md").write_text("\n".join(md))
(OUT / "findings.json").write_text(json.dumps(
    {"kind": KIND, "block_on": BLOCK_ON, "counts": counts, "blocking": len(blocking),
     "tools": {t: status(t) for t in TOOLS}, "inventory": inventory, "findings": findings}, indent=2))
print(f"blocking={len(blocking)}")
print(f"failed={len(failed)}")
