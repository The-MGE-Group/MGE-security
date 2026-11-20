# Roadmap

Ratings from the owner's list: (a) solid with a free tool, (b) possible with AI help but with
limits, (c) not possible or not worth it right now.

## Built

| # | Item | Rating | Where |
|---|---|---|---|
| 1 | Dependency scanning (CVEs) | a | PR scan, OSV-Scanner |
| 2 | Package list (SBOM) | a | PR scan, `sbom.cdx.json` |
| 3 | Malicious packages | a | PR scan, OSV-Scanner |
| 4 | Code scanning | a | PR scan, Opengrep |
| 5 | Custom code rules (simple patterns) | a | `rules/mge.yaml` |
| 6 | Secrets | a | PR scan, Gitleaks + TruffleHog |
| 7 | License risk | a | PR scan, OSV-Scanner |
| 8 | Outdated software | a | `templates/dependabot.yml` |
| 10 | Scanning the running site (ZAP, Nuclei) | a | Weekly scan |
| 12 | Attack surface (public subdomain list, exposed files) | a | Weekly scan, Subfinder + Nuclei |
| 13 | SSL and headers | a | Weekly scan, testssl.sh + ZAP |
| 14 | Supabase security advisor | a | Weekly scan |
| 22 | Role and cross-tenant access | a | Weekly scan, access test |
| 23 | Retesting | a | Issues close themselves when a later full scan no longer finds them |

## Not built yet, waiting for the owner's decision

| # | Item | Rating | Notes |
|---|---|---|---|
| 5 | Custom rules for tenant checks | b | Rules can spot a query without `tenant_id`, but can't prove the filter is right |
| 9 | Server-setup files and containers (Checkov) | c for now | Almost none exist; add if Docker or Terraform appear |
| 11 | API fuzzing (Schemathesis) | b | Needs an OpenAPI file; AI can draft one, but may miss routes |
| 15 | Vercel settings checks | b | No off-the-shelf tool; would be a checklist script against Vercel's API |
| 16 | Prowler | c | No AWS, Azure or Google Cloud in use |
| 17 | AI code review | b | Needs an `ANTHROPIC_API_KEY` secret |
| 18 | AI auto-triage | b | AI may label "likely false alarm", never remove or unblock |
| 19 | AI auto-fix | b | AI opens a fix PR for review; Dependabot already covers package upgrades |
| 20 | AI pentest stage | b, c for "equal to a human pentest" | |
| 21 | Business-logic tests | b | Needs the rules written down in plain English |

## Known gaps in what's built

- ZAP and Nuclei log in as one test user (`scan_as`), so pages only other roles see are not scanned by them.
- The `@supabase/ssr` login cookie has only been tested against the fake app. MGE Insights uses
  the bearer header, which has been tested against its real test deployment.
