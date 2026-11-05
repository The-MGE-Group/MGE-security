import sys
t = open("scripts/pr-scan.template.yml").read()
py = open("scripts/report.py").read().rstrip("\n")
ind = "\n".join(("          " + l) if l.strip() else "" for l in py.split("\n"))
open(".github/workflows/pr-scan.yml", "w").write(t.replace("__REPORT_PY__", ind))
