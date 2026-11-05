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

TOOLS = {
    "gitleaks": "Gitleaks (passwords and keys in code and git history)",
    "trufflehog": "TruffleHog (keys that are confirmed live)",
    "osv": "OSV-Scanner (known-vulnerable or malicious packages, and licenses)",
    "opengrep": "Opengrep (risky code patterns)",
}


def load(name, lines=False):
    p = RAW / name
    if not p.exists() or p.stat().st_size == 0:
        return None
    text = p.read_text(errors="replace").strip()
    if lines:  # TruffleHog prints one JSON object per line.
        return [json.loads(x) for x in text.splitlines() if x.strip().startswith("{")]
    return json.loads(text)


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
        "Read the rule message above and change the code. If it is a false alarm, add a `// nosemgrep` "
        "comment on that line with a short reason.",
        f"{rule}|{path}|{line}")

# ---------- Write the report ----------
findings.sort(key=lambda f: (ORDER.index(f["severity"]), f["tool"], f["title"]))
counts = {s: sum(f["severity"] == s for f in findings) for s in ORDER}
for f in findings:
    f["blocks"] = f["severity"] in BLOCK_LEVELS
blocking = [f for f in findings if f["blocks"]]
failed = {t: status(t) for t in TOOLS if not status(t).startswith("ok")}

if failed:
    verdict = "**Could not finish.** One or more checks did not run, so this project has NOT been checked. See below."
elif blocking:
    verdict = f"**Blocked.** {len(blocking)} problem(s) at or above the \"{BLOCK_ON}\" level must be fixed before merging."
elif findings:
    verdict = f"**Passed with notes.** No problem at or above the \"{BLOCK_ON}\" level. {len(findings)} lower-level note(s) below."
else:
    verdict = "**Passed.** None of the checks below found a problem."

md = ["# MGE Security: pull-request scan", "", verdict, "",
      f"Scanned: `{SCAN_PATH}` at commit `{SHA[:12]}`. Merge is blocked at: {BLOCK_ON}.", "",
      "| Level | Count |", "|---|---|"] + [f"| {s} | {counts[s]} |" for s in ORDER] + [""]

md += ["## Checks that ran", ""]
for t, label in TOOLS.items():
    s = status(t)
    good = s.startswith("ok")
    md.append(f"- {'✅' if good else '❌'} {label}" + ("" if s == "ok" else f": **{s}**" if not good else f" ({s[2:].strip(' ()')})"))
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

md += ["## What this scan does NOT check", "",
       "- Whether the running app is safe (logins, permissions, one customer seeing another customer's data). "
       "That needs tests against a running test copy, planned for a later step.",
       "- Logic mistakes and new kinds of attack. The code rules only know common, well-known patterns.",
       "- Vulnerabilities nobody has published yet, and malicious packages not yet reported.",
       "- Packages not pinned in a lockfile (for example a `package.json` without `pnpm-lock.yaml`).",
       "- Secrets that don't match a known format. TruffleHog only reports keys it could prove are live.",
       "- License results are a warning, not legal advice. They come from deps.dev and can be wrong.",
       "", "A pass means these tools found nothing. It does not mean the software is secure.", ""]

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "report.md").write_text("\n".join(md))
(OUT / "findings.json").write_text(json.dumps(
    {"block_on": BLOCK_ON, "counts": counts, "blocking": len(blocking),
     "tools": {t: status(t) for t in TOOLS}, "findings": findings}, indent=2))
print(f"blocking={len(blocking)}")
print(f"failed={len(failed)}")
