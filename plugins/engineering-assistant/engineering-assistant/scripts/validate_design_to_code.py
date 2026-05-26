#!/usr/bin/env python3
import argparse
import fnmatch
from pathlib import Path
from control_runtime import ensure_control_dir, now_iso, read_json, update_artifact_index, validate_target_project_root, write_json

def matches_any(path: str, patterns):
    return any(path == pattern or path.startswith(pattern.rstrip("/") + "/") or fnmatch.fnmatch(path, pattern) for pattern in patterns)

def main():
    parser = argparse.ArgumentParser(description="Validate changed files against implementation-contract.json.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--contract", default="artifacts/_control/implementation-contract.json")
    parser.add_argument("--changed-files-report", default="artifacts/_control/changed-files-report.json")
    parser.add_argument("--output", default="artifacts/_control/design-to-code-validation.json")
    parser.add_argument("--allow-major", action="store_true")
    args = parser.parse_args()
    root = validate_target_project_root(Path(args.root))
    contract = read_json(root / args.contract, {})
    changed_report = read_json(root / args.changed_files_report, {"changed_files": []})
    changed = changed_report.get("changed_files", [])
    allowed = contract.get("allowed_modules", [])
    forbidden = contract.get("forbidden_modules", [])
    required = contract.get("required_files_or_patterns", [])
    findings = []
    for item in changed:
        if matches_any(item, forbidden):
            findings.append({"severity": "blocker", "file": item, "reason": "file is in forbidden_modules"})
        if allowed and not matches_any(item, allowed):
            findings.append({"severity": "major", "file": item, "reason": "file is outside allowed_modules"})
    for pattern in required:
        if not any(matches_any(item, [pattern]) for item in changed) and not list(root.glob(pattern)):
            findings.append({"severity": "major", "pattern": pattern, "reason": "required file or pattern not changed/found"})
    blocking_severities = {"blocker"} if args.allow_major else {"blocker", "major"}
    status = "pass" if not any(item["severity"] in blocking_severities for item in findings) else "block"
    result = {"status": status, "blocking_severities": sorted(blocking_severities), "changed_files": changed, "allowed_modules": allowed, "forbidden_modules": forbidden, "findings": findings, "generated_at": now_iso()}
    output = root / args.output
    write_json(output, result)
    ensure_control_dir(root)
    update_artifact_index(root, output.name, output, "json", "validate_design_to_code")
    print(output)
    if status == "block":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
