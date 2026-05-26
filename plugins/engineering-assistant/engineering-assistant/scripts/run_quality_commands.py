#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path
from control_runtime import ensure_control_dir, now_iso, read_json, update_artifact_index, validate_target_project_root, write_json

PLACEHOLDER_TOKENS = ("待 code-development 阶段写入", "待确认", "todo", "tbd", "placeholder")

def is_placeholder(command: str) -> bool:
    lowered = command.lower()
    return any(token.lower() in lowered for token in PLACEHOLDER_TOKENS)

def main():
    parser = argparse.ArgumentParser(description="Run quality commands declared in quality-contract.json.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--contract", default="artifacts/_control/quality-contract.json")
    parser.add_argument("--output", default="artifacts/_control/quality-run-report.json")
    args = parser.parse_args()
    root = validate_target_project_root(Path(args.root))
    contract = read_json(root / args.contract, {})
    commands = contract.get("required_commands", [])
    results = []
    errors = []
    for item in commands:
        command = item.get("command")
        if not command:
            errors.append(f"quality command {item.get('id', '<missing-id>')} is missing command")
            continue
        if is_placeholder(command):
            errors.append(f"quality command {item.get('id', command)} contains placeholder text")
            continue
        run = subprocess.run(command, cwd=root, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        results.append({"id": item.get("id", command), "command": command, "required": item.get("required", True), "returncode": run.returncode, "output": run.stdout[-12000:]})
    status = "pass"
    if not commands:
        errors.append("no required quality commands declared")
        status = "block"
    elif errors:
        status = "block"
    elif any(item["required"] and item["returncode"] != 0 for item in results):
        status = "block"
    report = {"status": status, "errors": errors, "results": results, "generated_at": now_iso()}
    output = root / args.output
    write_json(output, report)
    ensure_control_dir(root)
    update_artifact_index(root, output.name, output, "json", "run_quality_commands")
    print(output)
    if status == "block":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
