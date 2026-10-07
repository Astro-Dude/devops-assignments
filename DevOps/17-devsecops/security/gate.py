#!/usr/bin/env python3
"""Security gate for the Session 17 pipeline.

Reads every scanner report produced earlier in the pipeline, applies the
thresholds in gate-policy.toml and exits non-zero if anything is blocking.
The push-image and deploy jobs `need` this job, so a non-zero exit here stops
the image from ever reaching the registry or the cluster.

Usage: gate.py --policy security/gate-policy.toml --reports <dir> [--summary out.md]
Only the Python standard library is used (3.11+ for tomllib).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path

CONF_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


class Check:
    def __init__(self, stage: str, tool: str):
        self.stage, self.tool = stage, tool
        self.total = 0          # all findings reported by the tool
        self.blocking: list[str] = []
        self.note = ""
        self.error = ""

    @property
    def passed(self) -> bool:
        return not self.error and not self.blocking


def load(reports: Path, rel: str):
    path = reports / rel
    if not path.is_file():
        raise FileNotFoundError(f"report missing: {rel}")
    text = path.read_text().strip()
    return json.loads(text) if text else None


def semgrep(data, cfg, c: Check):
    results = data.get("results", [])
    c.total = len(results)
    for r in results:
        sev = r["extra"].get("severity", "")
        if sev in cfg["block_severities"]:
            c.blocking.append(f'{sev} {r["check_id"].split(".")[-1]} at {r["path"]}:{r["start"]["line"]}')
    if data.get("errors"):
        c.note = f'{len(data["errors"])} semgrep parse errors'


def bandit(data, cfg, c: Check):
    results = data.get("results", [])
    c.total = len(results)
    min_conf = CONF_RANK[cfg.get("min_confidence", "LOW")]
    for r in results:
        if r["issue_severity"] in cfg["block_severities"] and CONF_RANK[r["issue_confidence"]] >= min_conf:
            c.blocking.append(
                f'{r["issue_severity"]}/{r["issue_confidence"]} {r["test_id"]} {r["test_name"]} '
                f'at {r["filename"]}:{r["line_number"]}'
            )


def trivy_misconfig(data, cfg, c: Check):
    for res in data.get("Results", []) or []:
        for m in res.get("Misconfigurations", []) or []:
            if m.get("Status", "FAIL") != "FAIL":
                continue
            c.total += 1
            if m["Severity"] in cfg["block_severities"]:
                c.blocking.append(f'{m["Severity"]} {m["ID"]} {m["Title"]} ({res["Target"]})')


def trivy_vulns(data, cfg, c: Check):
    need_fix = cfg.get("require_fix_available", False)
    unfixed = 0
    seen = set()
    by_sev: dict[str, int] = {}
    for res in data.get("Results", []) or []:
        for v in res.get("Vulnerabilities", []) or []:
            key = (v["VulnerabilityID"], v["PkgName"], v.get("InstalledVersion"))
            if key in seen:
                continue
            seen.add(key)
            c.total += 1
            by_sev[v["Severity"]] = by_sev.get(v["Severity"], 0) + 1
            if v["Severity"] not in cfg["block_severities"]:
                continue
            if need_fix and not v.get("FixedVersion"):
                unfixed += 1
                continue
            c.blocking.append(
                f'{v["Severity"]} {v["VulnerabilityID"]} {v["PkgName"]} {v.get("InstalledVersion")}'
                f' -> fixed in {v.get("FixedVersion") or "n/a"}'
            )
    order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]
    notes = [" ".join(f"{s[0]}:{by_sev[s]}" for s in order if s in by_sev)]
    if unfixed:
        notes.append(f"{unfixed} HIGH/CRITICAL have no upstream fix (reported, not blocking)")
    c.note = "; ".join(n for n in notes if n)


def pip_audit(data, cfg, c: Check):
    for dep in data.get("dependencies", []):
        for v in dep.get("vulns", []):
            c.total += 1
            if v.get("fix_versions") or not cfg.get("block_if_fix_available", True):
                fixes = ",".join(v.get("fix_versions", [])) or "n/a"
                c.blocking.append(f'{v["id"]} {dep["name"]} {dep["version"]} -> fix {fixes}')


def gitleaks(data, cfg, c: Check):
    findings = data or []
    c.total = len(findings)
    if c.total > cfg.get("max_findings", 0):
        for f in findings:
            c.blocking.append(
                f'{f["RuleID"]} in {f["File"]}:{f["StartLine"]} (commit {f.get("Commit", "")[:7]})'
            )


HANDLERS = {
    ("sast", "semgrep"): semgrep,
    ("sast", "bandit"): bandit,
    ("sast", "trivy_config"): trivy_misconfig,
    ("sca", "pip_audit"): pip_audit,
    ("sca", "trivy_fs"): trivy_vulns,
    ("secrets", "gitleaks"): gitleaks,
    ("image", "trivy"): trivy_vulns,
}
STAGE_NAMES = {"sast": "SAST", "sca": "SCA", "secrets": "Secret scan", "image": "Image scan"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True, type=Path)
    ap.add_argument("--reports", required=True, type=Path)
    ap.add_argument("--summary", type=Path, help="write markdown summary here")
    args = ap.parse_args()

    policy = tomllib.loads(args.policy.read_text())
    checks: list[Check] = []
    for stage, tools in policy.items():
        for tool, cfg in tools.items():
            c = Check(STAGE_NAMES.get(stage, stage), tool)
            try:
                data = load(args.reports, cfg["report"])
                HANDLERS[(stage, tool)](data, cfg, c)
            except Exception as exc:  # fail closed: unreadable/missing report blocks
                c.error = f"{type(exc).__name__}: {exc}"
            checks.append(c)

    failed = [c for c in checks if not c.passed]
    lines = [
        "## Security gate: " + ("FAILED - push and deploy are blocked" if failed else "PASSED"),
        "",
        "| Stage | Tool | Findings | Blocking | Result | Note |",
        "|---|---|---:|---:|---|---|",
    ]
    for c in checks:
        result = "PASS" if c.passed else "FAIL"
        note = c.error or c.note
        lines.append(f"| {c.stage} | {c.tool} | {c.total} | {len(c.blocking)} | {result} | {note} |")
    for c in failed:
        if c.blocking:
            lines += ["", f"### Blocking findings: {c.stage} / {c.tool}", ""]
            lines += [f"- {b}" for b in c.blocking[:50]]
            if len(c.blocking) > 50:
                lines.append(f"- ... and {len(c.blocking) - 50} more")
    md = "\n".join(lines) + "\n"

    print(md)
    if args.summary:
        args.summary.write_text(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(md)
    (args.reports / "gate-result.json").write_text(json.dumps(
        {"passed": not failed,
         "checks": [{"stage": c.stage, "tool": c.tool, "findings": c.total,
                     "blocking": c.blocking, "error": c.error, "note": c.note} for c in checks]},
        indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
