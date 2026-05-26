#!/usr/bin/env python3
"""Validate generated rule-governance artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_PACKS = {
    "design-review",
    "code-development",
    "code-quality-governor",
    "code-review",
    "self-test",
    "deploy-verification",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate rule-governance output.")
    parser.add_argument("root", help="Target project root.")
    parser.add_argument("--dir", default="artifacts/rule-governance", help="Rule-governance directory relative to root.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    base = root / args.dir
    registry_path = base / "rule-registry.json"
    duplicate_path = base / "rule-duplicate-report.json"
    digest_path = base / "rule-digest.md"
    pack_index_path = base / "rule-pack-index.json"
    pack_dir = base / "task-rule-packs"

    for path in [registry_path, duplicate_path, digest_path, pack_index_path]:
        if not path.exists():
            return fail(f"missing required artifact: {path}")

    registry = load_json(registry_path)
    rules = registry.get("rules", [])
    if not rules:
        return fail("rule registry has no rules")
    if registry.get("html_source_policy") != "excluded":
        return fail("registry must explicitly exclude HTML as source")

    ids = [rule.get("rule_id") for rule in rules]
    if len(ids) != len(set(ids)):
        return fail("rule ids are not unique")

    for rule in rules:
        source = rule.get("source", {})
        path = source.get("path", "")
        if path.endswith(".html") or "/human-readable/" in path or "/human-review/" in path:
            return fail(f"HTML source leaked into registry: {rule.get('rule_id')}")
        if rule.get("severity") in {"blocker", "major"} and not rule.get("text"):
            return fail(f"strong rule has empty text: {rule.get('rule_id')}")
        if not source.get("path") or not source.get("line"):
            return fail(f"rule missing source path/line: {rule.get('rule_id')}")

    pack_index = load_json(pack_index_path)
    packs = {item.get("task_type"): item for item in pack_index.get("packs", [])}
    missing = REQUIRED_PACKS.difference(packs)
    if missing:
        return fail(f"missing required task packs: {', '.join(sorted(missing))}")

    for task, item in packs.items():
        pack_path = root / item.get("path", "")
        if not pack_path.exists():
            return fail(f"pack listed but missing: {pack_path}")
        pack = load_json(pack_path)
        if pack.get("task_type") != task:
            return fail(f"pack task_type mismatch: {pack_path}")
        if pack.get("rule_count", 0) <= 0:
            return fail(f"pack has no rules: {pack_path}")
        if pack.get("selection_policy", {}).get("html_source_policy") != "excluded":
            return fail(f"pack does not exclude HTML source: {pack_path}")

    duplicate_report = load_json(duplicate_path)
    if "exact_duplicates" not in duplicate_report or "near_duplicates" not in duplicate_report:
        return fail("duplicate report schema is incomplete")

    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
