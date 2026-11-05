# Deliberately vulnerable test project

This folder exists only so the self-test can prove each scanner catches a planted problem.
Nothing here is real. Do not install it, run it, or copy code from it.

| Planted problem | File | Scanner that must catch it |
|---|---|---|
| A private key committed to code (fake, random bytes) | `deploy-key.pem` | Gitleaks |
| SQL query built from user input | `app.js` | Opengrep |
| Known-vulnerable package: `lodash@4.17.15` | `package-lock.json` | OSV-Scanner |
| Known-malicious package: `flatmap-stream@0.1.1` | `package-lock.json` | OSV-Scanner (malicious-packages feed) |
| GPL-licensed package: `@ckeditor/ckeditor5-core@41.0.0` | `package-lock.json` | OSV-Scanner license check |
| Supabase secret key in browser code | `next/admin-panel.tsx` | MGE rule `mge-supabase-service-role-in-browser-code` |
| Secret exposed through a `NEXT_PUBLIC_` name | `next/session.ts` | MGE rule `mge-next-public-secret` |
| `getSession()` trusted on the server | `next/session.ts` | MGE rule `mge-supabase-getsession-on-server` |

TruffleHog only reports keys it can prove are live. A real live key can't be planted safely,
so the self-test only checks that TruffleHog ran without errors.
