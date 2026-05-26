#!/usr/bin/env python3
import argparse
from pathlib import Path
from control_runtime import ensure_control_dir, now_iso, read_json, update_artifact_index, validate_target_project_root, write_json

RULE_REF_KEYS = {"rule_refs", "rule_id", "rule_ids", "rules"}
FINDING_KEYS = {"findings", "review_comments", "comments"}

def extract_refs(value) -> list[str]:
    refs = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in RULE_REF_KEYS:
                if isinstance(item, str):
                    refs.append(item)
                elif isinstance(item, list):
                    refs.extend(str(entry) for entry in item if entry)
            refs.extend(extract_refs(item))
    elif isinstance(value, list):
        for item in value:
            refs.extend(extract_refs(item))
    return list(dict.fromkeys(refs))

def finding_items(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FINDING_KEYS and isinstance(item, list):
                for entry in item:
                    if isinstance(entry, dict):
                        yield entry
            yield from finding_items(item)
    elif isinstance(value, list):
        for item in value:
            yield from finding_items(item)

def has_direct_rule_ref(item: dict) -> bool:
    return any(item.get(key) for key in RULE_REF_KEYS)

def main():
    parser = argparse.ArgumentParser(description="Validate that stage evidence consumed the task rule pack by rule_id.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--task-type", default="code-development")
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--output", default="artifacts/_control/rule-consumption-report.json")
    args = parser.parse_args()
    root = validate_target_project_root(Path(args.root))
    pack_path = root / "artifacts/rule-governance/task-rule-packs" / f"{args.task_type}.json"
    pack = read_json(pack_path, {})
    valid_ids = {item.get("rule_id") or item.get("id") for item in pack.get("rules", []) if isinstance(item, dict)}
    findings = []
    if not pack_path.exists() or not valid_ids:
        findings.append({"severity": "blocker", "reason": "missing task rule pack", "artifact": str(pack_path.relative_to(root))})
    evidence_refs = []
    if not args.evidence:
        findings.append({"severity": "blocker", "reason": "missing rule consumption evidence"})
    for evidence in args.evidence:
        path = root / evidence
        data = read_json(path, None)
        if data is None:
            findings.append({"severity": "blocker", "reason": "missing rule consumption evidence", "artifact": evidence})
            continue
        evidence_refs.extend(extract_refs(data))
        for item in finding_items(data):
            if not has_direct_rule_ref(item):
                findings.append({"severity": "blocker", "reason": "missing rule_refs", "artifact": evidence, "finding": item.get("id") or item.get("title") or item.get("reason")})
    unknown_refs = sorted({ref for ref in evidence_refs if valid_ids and ref not in valid_ids})
    if unknown_refs:
        findings.append({"severity": "blocker", "reason": "unknown rule_refs", "rule_refs": unknown_refs})
    if args.evidence and not evidence_refs:
        findings.append({"severity": "blocker", "reason": "no consumed rule_id evidence"})
    status = "pass" if not findings else "block"
    output = root / args.output
    ensure_control_dir(root)
    report = {"status": status, "task_type": args.task_type, "rule_pack": str(pack_path.relative_to(root)), "consumed_rule_refs": sorted(set(evidence_refs)), "findings": findings, "generated_at": now_iso()}
    write_json(output, report)
    update_artifact_index(root, output.name, output, "json", "validate_rule_consumption")
    print(output)
    if status == "block":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
