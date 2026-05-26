#!/usr/bin/env python3
import argparse
import re
from pathlib import Path
from control_runtime import ensure_control_dir, now_iso, update_artifact_index, validate_target_project_root, write_json

EXCLUDED_PARTS = {".git", "target", "build", "dist", "node_modules", "artifacts"}

def java_files(root: Path, segment: str) -> list[Path]:
    result = []
    for path in root.rglob("*.java"):
        rel_parts = path.relative_to(root).parts
        if any(part in EXCLUDED_PARTS for part in rel_parts):
            continue
        rel = "/".join(rel_parts)
        if segment in rel:
            result.append(path)
    return result

def read_all(paths: list[Path], root: Path) -> tuple[str, list[str]]:
    chunks = []
    rels = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = str(path.relative_to(root))
        rels.append(rel)
        chunks.append(f"\n# file: {rel}\n{text}")
    return "\n".join(chunks), rels

def has_exception_handler(text: str, exception_name: str) -> bool:
    annotation = rf"@ExceptionHandler\s*\([^)]*{re.escape(exception_name)}\.class"
    return bool(re.search(annotation, text))

def add(findings: list[dict], severity: str, reason: str, **extra):
    item = {"severity": severity, "reason": reason}
    item.update(extra)
    findings.append(item)

def main():
    parser = argparse.ArgumentParser(description="Validate Java/Spring Boot engineering quality patterns that generic adoption scans miss.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", default="artifacts/_control/spring-boot-quality-report.json")
    args = parser.parse_args()
    root = validate_target_project_root(Path(args.root))
    main_files = java_files(root, "src/main/java")
    test_files = java_files(root, "src/test/java")
    main_text, scanned_main = read_all(main_files, root)
    test_text, scanned_tests = read_all(test_files, root)
    findings = []
    if not main_files:
        status = "pass"
    else:
        for exception_name in ["ApplicationException", "DomainException"]:
            if re.search(rf"class\s+{exception_name}\b", main_text) and not has_exception_handler(main_text, exception_name):
                add(findings, "major", "domain/application exception lacks explicit HTTP mapping", exception=exception_name)
        upload_files = []
        for path in main_files:
            rel = str(path.relative_to(root))
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "MultipartFile" in text and ".getBytes()" in text:
                upload_files.append(rel)
        if upload_files:
            add(findings, "major", "MultipartFile.getBytes requires explicit size/error strategy", files=upload_files)
        mapper_like = bool(re.search(r"\b(BaseMapper|@Mapper|LambdaQueryWrapper)\b", main_text))
        repository_tests = bool(re.search(r"\b(Repository|Mapper|Persistence|Adapter)\b", test_text))
        if mapper_like and not repository_tests:
            add(findings, "major", "mapper/repository adapter lacks behavior test evidence")
        status = "pass" if not any(item["severity"] in {"blocker", "major"} for item in findings) else "block"
    output = root / args.output
    ensure_control_dir(root)
    report = {"status": status, "scanned_main_files": scanned_main, "scanned_test_files": scanned_tests, "findings": findings, "generated_at": now_iso()}
    write_json(output, report)
    update_artifact_index(root, output.name, output, "json", "validate_spring_boot_quality")
    print(output)
    if status == "block":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
