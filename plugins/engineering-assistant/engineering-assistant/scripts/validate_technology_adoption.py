#!/usr/bin/env python3
import argparse
from pathlib import Path
from control_runtime import ensure_control_dir, now_iso, read_json, update_artifact_index, validate_target_project_root, write_json

TEXT_SUFFIXES = {".java", ".kt", ".go", ".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".xml", ".yaml", ".yml", ".json"}
EXCLUDED_PARTS = {".git", "node_modules", "target", "build", "dist", "coverage", "artifacts"}

def collect_text(root: Path) -> tuple[str, list[str]]:
    chunks = []
    files = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        if any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = str(path.relative_to(root))
        chunks.append(f"\n# file: {rel}\n{text}")
        files.append(rel)
    return "\n".join(chunks), files

def indicator_found(text: str, indicator: str) -> bool:
    if indicator in text:
        return True
    tail = indicator.split(".")[-1]
    return bool(tail and tail != indicator and tail in text)

def main():
    parser = argparse.ArgumentParser(description="Validate declared framework and library adoption against source evidence.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--contract", default="artifacts/_control/implementation-contract.json")
    parser.add_argument("--output", default="artifacts/_control/technology-adoption-report.json")
    args = parser.parse_args()
    root = validate_target_project_root(Path(args.root))
    contract = read_json(root / args.contract, {})
    adoption = contract.get("technology_adoption_contract", {})
    text, scanned_files = collect_text(root)
    required = [item for item in adoption.get("required_indicators", []) if isinstance(item, str) and item]
    forbidden = [item for item in adoption.get("forbidden_indicators", []) if isinstance(item, str) and item]
    minimum = int(adoption.get("minimum_required_indicators", 0) or 0)
    required_hits = [item for item in required if indicator_found(text, item)]
    forbidden_hits = [item for item in forbidden if indicator_found(text, item)]
    findings = []
    if len(required_hits) < minimum:
        findings.append({"severity": "blocker", "reason": "not enough required technology indicators", "required": required, "hits": required_hits, "minimum": minimum})
    for item in forbidden_hits:
        findings.append({"severity": "blocker", "reason": "forbidden technology indicator", "indicator": item})
    status = "pass" if not findings else "block"
    output = root / args.output
    report = {"status": status, "contract": adoption, "scanned_files": scanned_files, "required_hits": required_hits, "forbidden_hits": forbidden_hits, "findings": findings, "generated_at": now_iso()}
    ensure_control_dir(root)
    write_json(output, report)
    update_artifact_index(root, output.name, output, "json", "validate_technology_adoption")
    print(output)
    if status == "block":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
