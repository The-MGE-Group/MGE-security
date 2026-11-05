"""Checks the production guard. Run: python3 scripts/test_guard.py"""
import sys
sys.path.insert(0, "scripts")
from guard import check

prod = "other.example, MGE-Insights.example"
assert check("https://mge-insights.example/dashboard", prod), "same host must be refused"
assert check("https://MGE-INSIGHTS.example:443/x?y=1", prod), "case and port must not matter"
assert check("https://mge-insights.example./", prod), "trailing dot must not matter"
assert check("https://preview.vercel.app", ""), "empty production list must be refused"
assert check("not a url", prod), "invalid target must be refused"
assert check("https://mge-insights-git-staging.vercel.app", prod) is None, "a preview must be allowed"
assert check("http://localhost:8080", prod) is None
print("guard checks passed")
