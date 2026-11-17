"""Checks the AI code review without calling Claude: a fake `anthropic` module answers instead.
Run: python3 scripts/test_ai_review.py"""
import json
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, "scripts")
import ai_review

ROUTE = """import { createClient } from '@supabase/supabase-js';

export async function GET(request, { params }) {
  const admin = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY);
  const { data } = await admin.from('invoices').select('*').eq('tenant_id', params.tenantId);
  return Response.json(data);
}
"""


def sh(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", *args],
                   cwd=cwd, check=True, capture_output=True)
    if args[0] == "commit":
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class FakeError(Exception):
    message = "nope"
    status_code = 500


def fake_anthropic(answer, stop_reason="end_turn", error=None, seen=None):
    """A stand-in for the SDK that records the request and returns `answer` as Claude's findings."""
    mod = types.ModuleType("anthropic")
    for name in ("AuthenticationError", "PermissionDeniedError", "RateLimitError", "BadRequestError",
                 "APIStatusError", "APIConnectionError"):
        setattr(mod, name, type(name, (FakeError,), {}))

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_final_message(self):
            return types.SimpleNamespace(
                stop_reason=stop_reason, stop_details=types.SimpleNamespace(category="cyber"), model="claude-opus-5-5",
                usage=types.SimpleNamespace(input_tokens=1, output_tokens=1), id="msg_test",
                content=[types.SimpleNamespace(type="thinking", thinking=""),
                         types.SimpleNamespace(type="text", text=json.dumps({"findings": answer}))])

    class Messages:
        def stream(self, **kw):
            if seen is not None:
                seen.update(kw)
            if error:
                raise getattr(mod, error)()
            return Stream()

    mod.Anthropic = lambda **kw: types.SimpleNamespace(beta=types.SimpleNamespace(messages=Messages()))
    return mod


def run(repo, raw, answer=(), **fake):
    sys.modules["anthropic"] = fake_anthropic(list(answer), **fake)
    here = os.getcwd()
    os.chdir(repo)
    try:
        ai_review.main()
    finally:
        os.chdir(here)
    return (raw / "status" / "ai").read_text(), json.loads((raw / "ai.json").read_text())["findings"]


with tempfile.TemporaryDirectory() as d:
    repo, raw = Path(d, "repo"), Path(d, "raw")
    repo.mkdir()
    sh(repo, "init", "-q")
    (repo / "README.md").write_text("hello\n")
    sh(repo, "add", "-A")
    base = sh(repo, "commit", "-qm", "base")
    (repo / "app/api").mkdir(parents=True)
    (repo / "app/api/route.ts").write_text(ROUTE)
    (repo / "package-lock.json").write_text('{"lockfileVersion": 3}\n')
    (repo / "logo.png").write_bytes(b"\x89PNG\0\0")
    (repo / "big.ts").write_text("x" * (ai_review.MAX_FILE + 1))
    os.symlink("/proc/self/environ", repo / "leak.ts")
    sh(repo, "add", "-A")
    head = sh(repo, "commit", "-qm", "change")
    os.environ.update(RAW_DIR=str(raw), BASE_SHA=base, PROOF_SHA=head, SCAN_PATH=".", AI_REVIEW="true")
    os.environ.pop("AI_REQUIREMENTS", None)
    good = {"file": "app/api/route.ts", "line": 3, "severity": "critical", "title": "Any visitor can read any tenant's invoices",
            "quote": "const admin = createClient(process.env.SUPABASE_URL,   process.env.SUPABASE_SERVICE_ROLE_KEY);",
            "explanation": "No login check, and the secret key skips row-level security.", "fix": "Check the user first."}

    # Skipped, never failed, when it has nothing to run with.
    os.environ.pop("ANTHROPIC_API_KEY", None)
    status, found = run(repo, raw, [good])
    assert status.startswith("skipped (no ANTHROPIC_API_KEY") and not found, status
    os.environ["ANTHROPIC_API_KEY"] = "test-key"
    os.environ["BASE_SHA"] = ""
    assert run(repo, raw, [good])[0].startswith("skipped (it only reads pull requests"), "push runs are skipped"
    os.environ["BASE_SHA"] = base
    os.environ["AI_REVIEW"] = "false"
    assert run(repo, raw, [good])[0].startswith("skipped (switched off"), "ai-review: false switches it off"
    os.environ["AI_REVIEW"] = "true"

    # What Claude is sent: the changed code file, numbered. Not the lockfile, image, oversized file or symlink.
    seen = {}
    made_up = dict(good, line=2, quote="eval(request.body)")           # text that is not in the file
    wrong_file = dict(good, file="package-lock.json", quote="lockfileVersion")  # a file Claude was not given
    drifted = dict(good, line=40, title="Second note", quote="return Response.json(data);")  # right text, wrong line number
    status, found = run(repo, raw, [made_up, wrong_file, good, drifted, dict(good)], seen=seen)
    prompt = seen["messages"][0]["content"]
    assert '<file path="app/api/route.ts">' in prompt and "4: " + ROUTE.split("\n")[3] in prompt, "file is sent with line numbers"
    for absent in ("package-lock.json\">", "logo.png", "leak.ts", "PATH="):
        assert absent not in prompt, f"{absent} must not be sent"
    assert "big.ts" in prompt and '<file path="big.ts">' not in prompt, "an oversized file is named, not sent"
    assert seen["model"] == "claude-opus-5-5" and seen["fallbacks"] == "default"
    assert seen["output_config"]["format"]["type"] == "json_schema" and seen["output_config"]["effort"] == "high"

    # Only notes whose quoted line is really in the file are kept, at the line where the text is.
    assert [(f["path"], f["line"]) for f in found] == [("app/api/route.ts", 4), ("app/api/route.ts", 6)], found
    assert status.startswith("ok (1 changed file read; NOT reviewed because too large: big.ts; 3 note(s) left out"), status

    # A change with no code files is fine and does not call Claude.
    seen = {}
    os.environ["BASE_SHA"] = head
    (repo / "notes.png").write_bytes(b"\0\0")
    sh(repo, "add", "-A")
    os.environ["PROOF_SHA"] = sh(repo, "commit", "-qm", "image only")
    status, found = run(repo, raw, [good], seen=seen)
    assert status.startswith("ok (this pull request changes no code files") and not seen and not found, status
    os.environ.update(BASE_SHA=base, PROOF_SHA=head)

    # Anything going wrong is a "failed" status with no findings, never a crash.
    assert run(repo, raw, [good], stop_reason="refusal")[0].startswith("failed: Claude declined")
    assert run(repo, raw, [good], stop_reason="max_tokens")[0].startswith("failed: Claude's answer was cut off")
    assert run(repo, raw, [good], error="AuthenticationError")[0].startswith("failed: Anthropic did not accept")
    assert run(repo, raw, [good], error="APIConnectionError")[0].startswith("failed: Anthropic could not be reached")
    os.environ["BASE_SHA"] = "0" * 40
    status, found = run(repo, raw, [good])
    assert status.startswith("failed: could not read the pull request's changes") and not found, status
    os.environ["BASE_SHA"] = base

    # The report: an AI note never blocks, even at "critical", and its text cannot add links or HTML.
    out = Path(d, "out")
    for t in ("gitleaks", "trufflehog", "osv", "sbom", "opengrep"):
        (raw / "status" / t).write_text("ok")
    sneaky = dict(good, title="Leak [click](http://evil.example) <img src=x>")
    run(repo, raw, [sneaky])
    env = dict(os.environ, OUT_DIR=str(out), SCAN_KIND="pr", BLOCK_ON="high", GITHUB_REPOSITORY="", PROOF_SHA=head)

    def report():
        printed = subprocess.run([sys.executable, "scripts/report.py"], env=env, check=True, capture_output=True, text=True).stdout
        return printed, json.loads((out / "findings.json").read_text()), (out / "report.md").read_text()

    printed, data, md = report()
    assert "blocking=0" in printed and "failed=0" in printed, printed
    f = data["findings"]
    assert len(f) == 1 and f[0]["tool"] == "ai" and f[0]["severity"] == "critical" and f[0]["blocks"] is False, f
    assert "Passed with notes" in md and "1 of them from the AI review, which never blocks" in md, md[:400]
    assert "](http://evil.example)" not in md and "<img" not in md, "links and HTML from Claude are defused"

    # ... and when the AI review fails, the scan still finishes on the other checks, with a visible warning.
    run(repo, raw, [good], error="RateLimitError")
    printed, data, md = report()
    assert "blocking=0" in printed and "failed=0" in printed, printed
    assert "The AI code review did not run" in md and "⚠️ AI code review" in md, md[:600]
    # A real scanner failing is still a failed scan.
    (raw / "status" / "osv").write_text("failed, see the step log")
    assert "failed=1" in report()[0]
print("AI code review checks passed")
