#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

ALLOWED_SUFFIXES = {".json", ".md", ".yaml", ".yml", ".sql", ".txt"}
FORBIDDEN_SUFFIXES = {".html", ".htm", ".png", ".jpg", ".jpeg", ".gif"}


def safe_project_path(root: Path, rel: str):
    if Path(rel).is_absolute():
        return None
    root_resolved = root.resolve()
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None
    return candidate


def add_source(root: Path, sources: list[dict], forbidden: list[str], rel: str, kind: str) -> bool:
    path = safe_project_path(root, rel)
    if path is None:
        forbidden.append(rel)
        return False
    suffix = path.suffix.lower()
    if suffix in FORBIDDEN_SUFFIXES or "/docs/human-review/" in str(path).replace("\\", "/"):
        forbidden.append(rel)
        return False
    if suffix not in ALLOWED_SUFFIXES and path.name != "Makefile":
        forbidden.append(rel)
        return False
    if path.exists():
        sources.append({"path": rel, "kind": kind, "bytes": path.stat().st_size})
        return True
    return False


def build_pack(root: Path, skill_id: str, task_id: str) -> dict:
    sources = []
    forbidden = []
    missing_required_sources = []
    required = [
        ("artifacts/workflow-orchestrator/artifact-index.json", "workflow_artifact_index"),
        ("artifacts/workflow-orchestrator/workflow-summary.md", "workflow_summary"),
        ("artifacts/_control/architecture-baseline.json", "architecture_baseline"),
        ("Makefile", "validation_entrypoint"),
    ]
    for rel, kind in required:
        if not add_source(root, sources, forbidden, rel, kind):
            missing_required_sources.append(rel)
    index_path = root / "artifacts/workflow-orchestrator/artifact-index.json"
    if index_path.exists():
        data = json.loads(index_path.read_text(encoding="utf-8"))
        for rel in data.get("stage_results", [])[:40]:
            add_source(root, sources, forbidden, rel, "stage_run_result")
        for rel in data.get("document_control_artifacts", [])[:30]:
            add_source(root, sources, forbidden, rel, "document_control")
        for rel in data.get("human_review_packets", []):
            add_source(root, sources, forbidden, rel, "forbidden_human_html")
    status = "pass" if not missing_required_sources else "block"
    return {"root": str(root), "skill_id": skill_id, "task_id": task_id, "status": status, "sources": sources, "forbidden_sources": forbidden, "missing_required_sources": missing_required_sources}


def main():
    parser = argparse.ArgumentParser(description="Build a minimal context pack from machine-readable project artifacts.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--skill-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    pack = build_pack(Path(args.root), args.skill_id, args.task_id)
    text = json.dumps(pack, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    if pack["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
