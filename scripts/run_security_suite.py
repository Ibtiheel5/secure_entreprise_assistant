#!/usr/bin/env python
"""Exécute la suite pytest marquée `security` et écrit un rapport JSON + Markdown (chiffres réels du run).
Usage (depuis la racine) : python scripts/run_security_suite.py"""
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "docs" / "security" / "security_report.json"
OUT_MD = ROOT / "docs" / "security" / "SECURITY_REPORT.md"


def main() -> int:
    junit = Path(tempfile.mkdtemp()) / "junit.xml"
    proc = subprocess.run([sys.executable, "-m", "pytest", "-m", "security", "-q", f"--junitxml={junit}"],
                          cwd=ROOT / "backend", capture_output=True, text=True)
    tests = []
    for case in ET.parse(junit).getroot().iter("testcase"):
        outcome = "failed" if case.find("failure") is not None or case.find("error") is not None else \
                  "skipped" if case.find("skipped") is not None else "passed"
        tests.append({"name": case.get("name"), "outcome": outcome})
    passed = sum(t["outcome"] == "passed" for t in tests)
    inj = [t for t in tests if "prompt_injection" in t["name"] or "injection" in t["name"]]
    report = {
        "ran_at": datetime.now(timezone.utc).isoformat(), "total": len(tests), "passed": passed,
        "failed": sum(t["outcome"] == "failed" for t in tests),
        "pass_rate": round(passed / len(tests), 4) if tests else 0.0,
        "prompt_injection": {"total": len(inj), "passed": sum(t["outcome"] == "passed" for t in inj)},
        "tests": tests,
    }
    OUT_JSON.write_text(json.dumps(report, indent=2))
    lines = ["# Security evaluation report", "", f"Generated: {report['ran_at']}", "",
             f"- Tests run: **{report['total']}** — passed **{report['passed']}** — failed **{report['failed']}** "
             f"(pass rate {report['pass_rate']:.1%})",
             f"- Prompt-injection tests: {report['prompt_injection']['passed']}/{report['prompt_injection']['total']} passed",
             "", "| Test | Result |", "|---|---|"] + [f"| `{t['name']}` | {t['outcome']} |" for t in tests] + [
             "", "## Scope and limits", "",
             "- Tests use a deterministic hash embedder and a scripted LLM: they prove that **unauthorized content never reaches "
             "results, reranker candidates, LLM prompts, citations or MCP outputs**, independent of model behavior.",
             "- They do **not** measure how a real LLM resists jailbreaks; the design avoids relying on that "
             "(the LLM never receives unauthorized text).",
             "- A passing suite is evidence, not proof of security. Rate limiting, TLS, secrets management and a "
             "penetration test are outside this suite."]
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"{passed}/{len(tests)} security tests passed -> {OUT_MD}")
    return 0 if report["failed"] == 0 and tests else 1


if __name__ == "__main__":
    sys.exit(main())
