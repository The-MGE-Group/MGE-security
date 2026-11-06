#!/usr/bin/env python3
"""Fake app + fake Supabase for the weekly-scan self-test. Not real; never deploy.

python3 server.py [--leaky]   serves http://localhost:8080 and https://localhost:8443
"""
import base64
import json
import ssl
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LEAKY = "--leaky" in sys.argv
A, B = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
USERS = {  # email -> (token, tenant, role)
    "a-admin@fixture.test": ("tok-a-admin", A, "admin"),
    "a-member@fixture.test": ("tok-a-member", A, "member"),
    "b-admin@fixture.test": ("tok-b-admin", B, "admin"),
}
PASSWORD = "fixture-password-not-real"
REPORTS = {"1": (A, "ZZ-TENANT-A-REPORT"), "2": (B, "ZZ-TENANT-B-REPORT")}
TABLES = {
    "invoices": [{"tenant_id": A, "total": 10}, {"tenant_id": B, "total": 20}],
    "reports": [{"tenant_id": A}, {"tenant_id": B}],
}
SAFE_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'; form-action 'self'",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store",
}


class App(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if not LEAKY:
            for k, v in SAFE_HEADERS.items():
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def user(self):
        token = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        for part in (self.headers.get("Cookie") or "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == "sb-fixture-auth-token" and value.startswith("base64-"):
                raw = value[7:] + "=" * (-len(value[7:]) % 4)
                token = json.loads(base64.urlsafe_b64decode(raw))["access_token"]
        return next((u for u in USERS.values() if u[0] == token), None)

    def do_POST(self):
        if self.path.startswith("/auth/v1/token"):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            u = USERS.get(body.get("email"))
            if not u or body.get("password") != PASSWORD:
                return self.send(400, {"error": "invalid_grant"})
            return self.send(200, {"access_token": u[0], "token_type": "bearer", "expires_in": 3600,
                                   "refresh_token": "r-" + u[0], "user": {"email": body["email"]}})
        self.send(404, {"error": "not found"})

    def do_DELETE(self):
        u = self.user()
        if self.path.startswith("/api/v1/tenants/"):
            tid = self.path.split("/")[4]
            if not u or (tid != u[1] and not LEAKY):
                return self.send(404, {"error": "not found"})
            return self.send(200, {"deleted": True})
        rid = self.path.rsplit("/", 1)[-1]
        if not self.path.startswith("/api/reports/") or rid not in REPORTS:
            return self.send(404, {"error": "not found"})
        if not u or REPORTS[rid][0] != u[1]:
            return self.send(404, {"error": "not found"})
        if u[2] != "admin" and not LEAKY:
            return self.send(403, {"error": "admins only"})
        self.send(200, {"deleted": rid})

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/":
            return self.send(200, "<html><head><title>Fixture</title></head><body><h1>Fixture app</h1>"
                                  "<a href='/about'>About</a></body></html>", "text/html")
        if url.path == "/about":
            return self.send(200, "<html><head><title>About</title></head><body>About</body></html>", "text/html")
        if url.path == "/.git/config" and LEAKY:
            return self.send(200, "[core]\n\trepositoryformatversion = 0\n", "text/plain")
        if url.path.startswith("/api/v1/tenants/"):
            u, tid = self.user(), url.path.split("/")[4]
            if not u or (tid != u[1] and not LEAKY):
                return self.send(404, {"error": "not found"})
            return self.send(200, [{"title": t[1]} for t in REPORTS.values() if t[0] == tid])
        if url.path.startswith("/api/reports/"):
            u, rid = self.user(), url.path.rsplit("/", 1)[-1]
            if rid not in REPORTS or not u or (REPORTS[rid][0] != u[1] and not LEAKY):
                return self.send(404, {"error": "not found"})
            return self.send(200, {"id": rid, "title": REPORTS[rid][1]})
        if url.path == "/rest/v1/":
            return self.send(200, {"definitions": {t: {"properties": {"tenant_id": {}}} for t in TABLES}})
        if url.path.startswith("/rest/v1/"):
            table = url.path.split("/")[3]
            u = self.user()
            want = urllib.parse.parse_qs(url.query).get("tenant_id", ["eq."])[0].removeprefix("eq.")
            rows = [r for r in TABLES.get(table, []) if r["tenant_id"] == want]
            if not u:
                rows = []
            elif not (LEAKY and table == "invoices"):
                rows = [r for r in rows if r["tenant_id"] == u[1]]
            return self.send(200, rows)
        self.send(404, "<html><body>Not found</body></html>", "text/html")


http_server = ThreadingHTTPServer(("127.0.0.1", 8080), App)
https_server = ThreadingHTTPServer(("127.0.0.1", 8443), App)
here = Path(__file__).parent
if (here / "cert.pem").exists():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(here / "cert.pem", here / "key.pem")
    https_server.socket = ctx.wrap_socket(https_server.socket, server_side=True)
    threading.Thread(target=https_server.serve_forever, daemon=True).start()
print(f"fixture app running (leaky={LEAKY})", flush=True)
http_server.serve_forever()
