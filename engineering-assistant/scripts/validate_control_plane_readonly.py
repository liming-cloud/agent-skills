#!/usr/bin/env python3
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from control_runtime import read_json, validate_target_project_root

def git_lines(args, cwd: Path):
    result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode not in (0, 1):
        if "not a git repository" in result.stderr:
            return []
        if "ambiguous argument" in result.stderr or "bad revision" in result.stderr or "unknown revision" in result.stderr:
            return []
        raise SystemExit(result.stderr.strip())
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]

def fingerprint(items: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(items)).encode("utf-8")).hexdigest()

def current_changed_files(root: Path, base: str) -> list[str]:
    unstaged = git_lines(["git", "diff", "--name-only", base], root)
    staged = git_lines(["git", "diff", "--cached", "--name-only", base], root)
    untracked = git_lines(["git", "ls-files", "--others", "--exclude-standard"], root)
    return sorted(set(unstaged + staged + untracked))

def main():
    parser = argparse.ArgumentParser(description="Read-only freshness check for changed-files control-plane evidence.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--changed-files-report", default="artifacts/_control/changed-files-report.json")
    args = parser.parse_args()
    root = validate_target_project_root(Path(args.root))
    report_path = root / args.changed_files_report
    report = read_json(report_path, None)
    findings = []
    if report is None:
        findings.append({"severity": "blocker", "reason": "missing changed-files report", "artifact": args.changed_files_report})
        changed = current_changed_files(root, args.base)
        current_fingerprint = fingerprint(changed)
    else:
        changed = current_changed_files(root, report.get("base") or args.base)
        current_fingerprint = fingerprint(changed)
        recorded_fingerprint = report.get("workspace_fingerprint")
        recorded_files = sorted(report.get("changed_files", []))
        if recorded_fingerprint and recorded_fingerprint != current_fingerprint:
            findings.append({"severity": "blocker", "reason": "stale changed-files report fingerprint", "artifact": args.changed_files_report, "recorded": recorded_fingerprint, "current": current_fingerprint})
        elif not recorded_fingerprint and recorded_files != changed:
            findings.append({"severity": "blocker", "reason": "stale changed-files report file list", "artifact": args.changed_files_report, "recorded_files": recorded_files, "current_files": changed})
        elif not recorded_fingerprint:
            findings.append({"severity": "major", "reason": "changed-files report has no workspace_fingerprint", "artifact": args.changed_files_report})
    status = "pass" if not any(item["severity"] == "blocker" for item in findings) else "block"
    payload = {"status": status, "changed_files": changed, "workspace_fingerprint": current_fingerprint, "findings": findings}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if status == "block":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
