# Test web app for the weekly scan

`server.py` is a tiny fake app plus a fake Supabase, used only by the self-test.
Started with `--leaky` it has planted problems; without it, the same app is locked down.

| Planted problem (leaky mode) | Must be caught by |
|---|---|
| Tenant A can read tenant B's report at `/api/reports/2` | Access tests (route) |
| A tenant A member (not admin) can delete a report | Access tests (role) |
| Tenant A can read tenant B's rows in the `invoices` table | Access tests (database) |
| Tenant A can list and delete tenant B's reports through `/api/v1/tenants/<B>/reports` | Access tests (routes found in `api-src/` by themselves) |
| No security headers on the home page | ZAP |
| `/.git/config` is downloadable, but only when logged in | Nuclei, logged in as `scan_as` |
| HTTPS certificate is self-signed | testssl.sh |

The `app/` folder only exists so the access test can list routes nobody tests
(`/settings` is deliberately left untested).
Fake logins: the passwords are set by the self-test and are not real anywhere.
