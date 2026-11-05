"""Checks report.py on sample output for tools the self-test can't run for real
(the Supabase advisor needs a real project and token). Run: python3 scripts/test_report.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as d:
    raw, out = Path(d, "raw"), Path(d, "out")
    (raw / "status").mkdir(parents=True)
    for t in ("access", "zap", "nuclei", "testssl", "supabase", "subfinder"):
        (raw / "status" / t).write_text("ok")
    # Shape from https://supabase.com/docs/reference/api/v1-get-security-advisors
    (raw / "supabase.json").write_text(json.dumps({"lints": [{
        "name": "rls_disabled_in_public", "title": "RLS Disabled in Public", "level": "ERROR", "facing": "EXTERNAL",
        "categories": ["SECURITY"], "description": "Detects tables in the public schema without row-level security.",
        "detail": "Table `public.invoices` is public, but RLS has not been enabled.",
        "remediation": "https://supabase.com/docs/guides/database/database-linter?lint=0013_rls_disabled_in_public",
        "metadata": {"schema": "public", "name": "invoices", "type": "table"}, "cache_key": "rls_disabled_in_public_public_invoices"}]}))
    env = dict(os.environ, RAW_DIR=str(raw), OUT_DIR=str(out), SCAN_KIND="weekly", TARGET_URL="https://test.example")
    subprocess.run([sys.executable, "scripts/report.py"], env=env, check=True, capture_output=True)
    f = json.loads((out / "findings.json").read_text())["findings"]
    assert len(f) == 1 and f[0]["severity"] == "high" and "public.invoices" in f[0]["title"], f
print("report.py sample checks passed")
