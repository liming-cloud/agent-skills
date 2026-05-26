#!/usr/bin/env python3
"""Build task-scoped rule indexes from project documentation.

The script keeps long-form docs as source of truth, then generates compact
machine-readable rule packs for agents and reviewers. HTML files are excluded
by design because they are human-only mirrors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable


RULE_MODAL_RE = re.compile(
    r"(必须|不得|禁止|只允许|不允许|需要|应当|应|默认|优先|红线|门禁|blocker|must|should|shall|forbid|forbidden)",
    re.IGNORECASE,
)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
LIST_RE = re.compile(r"^\s*[-*]\s+(?:\[[ xX]\]\s*)?(?P<text>.+?)\s*$")
TABLE_RE = re.compile(r"^\s*\|(.+)\|\s*$")
WORD_RE = re.compile(r"[\w\u4e00-\u9fff]+")

EXCLUDED_DIR_PARTS = {
    ".git",
    "node_modules",
    "target",
    "dist",
    "build",
    "docs/human-readable",
    "docs/human-review",
    "artifacts/rule-governance",
    "artifacts/_control",
}

SCAN_SUFFIXES = {".md", ".yaml", ".yml", ".sql"}
NOISE_TOKENS = {
    "forbidden",
    "blocker",
    "blockers",
    "severity",
    "required_action",
    "required_actions",
    "code_generation",
}
TABLE_HEADER_WORDS = {
    "层",
    "职责",
    "禁止",
    "模式",
    "适用场景",
    "对象",
    "要求",
    "类型",
    "用途",
    "维度",
    "合格标准",
    "不合格表现",
}

TAG_KEYWORDS = {
    "document-governance": ["文档", "artifact-index", "human-readable", "human-review", "html", "留存", "索引"],
    "rule-governance": ["规则", "规范", "rule", "规则包", "检索", "去重", "压缩"],
    "requirement": ["需求", "requirement", "验收标准", "范围"],
    "architecture": ["架构", "bounded context", "context", "DDD", "领域", "聚合", "port", "adapter"],
    "identity-access": ["租户", "用户", "角色", "权限", "Sa-Token", "RBAC", "鉴权", "认证", "tenant", "permission"],
    "spring-ai": ["Spring AI", "ChatClient", "Advisor", "RAG", "Tool", "Embedding", "VectorStore", "prompt", "模型"],
    "database": ["数据库", "PostgreSQL", "MyBatis", "DDL", "索引", "迁移", "pgvector", "事务"],
    "redis": ["Redis", "缓存", "TTL", "key", "SETNX"],
    "mq": ["MQ", "RocketMQ", "topic", "consumer", "message", "死信", "重试"],
    "frontend": ["前端", "React", "组件", "页面", "TanStack", "Zustand", "E2E"],
    "code-quality": ["代码", "质量", "JDK", "TDD", "测试", "review", "lint", "设计模式"],
    "security": ["安全", "密钥", "token", "凭据", "脱敏", "审计", "越权"],
    "deploy": ["deploy", "部署", "Docker", "环境", "验收", "真实依赖"],
    "observability": ["trace", "日志", "指标", "可观测", "Micrometer", "Actuator"],
}

TASK_TAGS = {
    "requirement-intake": {"requirement", "document-governance", "rule-governance"},
    "repo-context-miner": {"architecture", "database", "redis", "mq", "frontend", "spring-ai", "identity-access"},
    "high-level-design": {"architecture", "database", "redis", "mq", "frontend", "spring-ai", "identity-access", "deploy"},
    "detailed-design": {"architecture", "identity-access", "spring-ai", "database", "redis", "mq", "frontend", "code-quality"},
    "database-design": {"database", "security", "deploy"},
    "redis-design": {"redis", "identity-access", "security"},
    "mq-design": {"mq", "security", "observability"},
    "frontend-design": {"frontend", "identity-access", "security", "observability"},
    "design-review": set(TAG_KEYWORDS.keys()),
    "code-development": {"code-quality", "architecture", "identity-access", "spring-ai", "database", "redis", "mq", "security", "observability"},
    "frontend-development": {"frontend", "code-quality", "identity-access", "security", "observability"},
    "code-quality-governor": {"code-quality", "architecture", "identity-access", "spring-ai", "database", "redis", "mq", "security", "observability", "rule-governance"},
    "code-review": {"code-quality", "architecture", "identity-access", "spring-ai", "database", "redis", "mq", "frontend", "security", "observability", "rule-governance"},
    "self-test": {"code-quality", "database", "redis", "mq", "frontend", "spring-ai", "identity-access", "deploy"},
    "deploy-verification": {"deploy", "database", "redis", "mq", "frontend", "spring-ai", "observability", "security"},
    "release-readiness": {"deploy", "code-quality", "document-governance", "rule-governance", "security"},
}


@dataclass(frozen=True)
class Rule:
    rule_id: str
    text: str
    severity: str
    category: str
    tags: list[str]
    source_path: str
    line: int
    section: str
    fingerprint: str


def rel_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def should_skip(root: Path, path: Path) -> bool:
    rel = rel_path(root, path)
    if path.suffix.lower() not in SCAN_SUFFIXES:
        return True
    rel_parts = set(Path(rel).parts)
    if rel_parts & {".git", "node_modules", "target", "dist", "build"}:
        return True
    return any(rel == part or rel.startswith(part + "/") for part in EXCLUDED_DIR_PARTS)


def normalize_text(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    words = WORD_RE.findall(text.lower())
    return "".join(words)


def fingerprint(text: str) -> str:
    normalized = normalize_text(text)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def classify_tags(text: str, source_path: str, section: str) -> list[str]:
    haystack = f"{source_path}\n{section}\n{text}".lower()
    tags = []
    for tag, keywords in TAG_KEYWORDS.items():
        if any(keyword.lower() in haystack for keyword in keywords):
            tags.append(tag)
    return sorted(set(tags or ["general"]))


def classify_severity(text: str) -> str:
    if re.search(r"(禁止|不得|不允许|只允许|红线|blocker|forbid|forbidden|must)", text, re.IGNORECASE):
        return "blocker"
    if re.search(r"(必须|需要|shall)", text, re.IGNORECASE):
        return "major"
    if re.search(r"(应当|应|优先|should|建议)", text, re.IGNORECASE):
        return "minor"
    return "info"


def category_from_tags(tags: list[str], section: str) -> str:
    if tags:
        return tags[0]
    return section or "general"


def iter_rule_candidates(root: Path, path: Path) -> Iterable[tuple[int, str, str]]:
    section = ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return
    for line_no, raw in enumerate(lines, start=1):
        heading = HEADING_RE.match(raw)
        if heading:
            section = heading.group(2).strip()
            continue

        list_match = LIST_RE.match(raw)
        if list_match and RULE_MODAL_RE.search(list_match.group("text")):
            yield line_no, section, list_match.group("text").strip()
            continue

        table_match = TABLE_RE.match(raw)
        if table_match and RULE_MODAL_RE.search(raw) and "---" not in raw:
            cells = [cell.strip() for cell in table_match.group(1).split("|")]
            cells = [cell for cell in cells if cell]
            if cells and all(cell in TABLE_HEADER_WORDS for cell in cells):
                continue
            if cells:
                yield line_no, section, " | ".join(cells)
            continue

        if path.suffix.lower() in {".yaml", ".yml", ".sql"} and RULE_MODAL_RE.search(raw):
            cleaned = raw.strip().rstrip(",")
            token = cleaned.strip().strip(":").strip("\"'").lower()
            if token in NOISE_TOKENS or (cleaned.endswith(":") and " " not in cleaned and len(cleaned) < 24):
                continue
            if len(normalize_text(cleaned)) < 8:
                continue
            if cleaned:
                yield line_no, section, cleaned


def collect_rules(root: Path) -> list[Rule]:
    rules: list[Rule] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or should_skip(root, path):
            continue
        source = rel_path(root, path)
        for line_no, section, text in iter_rule_candidates(root, path):
            fp = fingerprint(f"{source}:{line_no}:{text}")
            tags = classify_tags(text, source, section)
            digest = hashlib.sha1(f"{source}:{line_no}:{normalize_text(text)}".encode("utf-8")).hexdigest()[:10]
            rule_id = f"RG-{digest.upper()}"
            rules.append(
                Rule(
                    rule_id=rule_id,
                    text=text,
                    severity=classify_severity(text),
                    category=category_from_tags(tags, section),
                    tags=tags,
                    source_path=source,
                    line=line_no,
                    section=section,
                    fingerprint=fingerprint(text),
                )
            )
    return rules


def duplicate_report(rules: list[Rule]) -> dict:
    by_fingerprint: dict[str, list[Rule]] = defaultdict(list)
    for rule in rules:
        by_fingerprint[rule.fingerprint].append(rule)

    exact = [
        {
            "fingerprint": fp,
            "rules": [rule.rule_id for rule in grouped],
            "sources": [f"{rule.source_path}:{rule.line}" for rule in grouped],
        }
        for fp, grouped in by_fingerprint.items()
        if len(grouped) > 1
    ]

    near = []
    normalized = [(rule, normalize_text(rule.text)) for rule in rules]
    for i, (left, left_text) in enumerate(normalized):
        if len(left_text) < 18:
            continue
        for right, right_text in normalized[i + 1 :]:
            if left.fingerprint == right.fingerprint:
                continue
            if not set(left.tags).intersection(right.tags):
                continue
            ratio = SequenceMatcher(None, left_text, right_text).ratio()
            if ratio >= 0.9:
                near.append(
                    {
                        "similarity": round(ratio, 3),
                        "rules": [left.rule_id, right.rule_id],
                        "sources": [f"{left.source_path}:{left.line}", f"{right.source_path}:{right.line}"],
                    }
                )
    return {"exact_duplicates": exact, "near_duplicates": near[:200]}


def rule_to_json(rule: Rule) -> dict:
    return {
        "rule_id": rule.rule_id,
        "severity": rule.severity,
        "category": rule.category,
        "tags": rule.tags,
        "text": rule.text,
        "source": {
            "path": rule.source_path,
            "line": rule.line,
            "section": rule.section,
        },
        "fingerprint": rule.fingerprint,
    }


def build_task_packs(rules: list[Rule], max_rules: int) -> dict[str, dict]:
    severity_rank = {"blocker": 0, "major": 1, "minor": 2, "info": 3}
    packs = {}
    for task, tags in TASK_TAGS.items():
        selected = [
            rule
            for rule in rules
            if tags == set(TAG_KEYWORDS.keys()) or set(rule.tags).intersection(tags)
        ]
        selected.sort(key=lambda rule: (severity_rank.get(rule.severity, 9), rule.category, rule.source_path, rule.line))
        selected = selected[:max_rules]
        packs[task] = {
            "task_type": task,
            "generated_by": "build_rule_index.py",
            "selection_policy": {
                "tags": sorted(tags),
                "max_rules": max_rules,
                "priority": ["blocker", "major", "minor", "info"],
                "html_source_policy": "excluded",
            },
            "rule_count": len(selected),
            "rules": [rule_to_json(rule) for rule in selected],
        }
    return packs


def write_digest(output_dir: Path, rules: list[Rule], duplicate_summary: dict) -> None:
    by_category: dict[str, list[Rule]] = defaultdict(list)
    for rule in rules:
        by_category[rule.category].append(rule)

    lines = [
        "# Rule Digest",
        "",
        "document_status: generated",
        "retention_policy: keep_until_regenerated",
        "agent_source: true",
        "",
        "This digest is generated from Markdown/JSON/YAML/SQL sources. HTML files are excluded.",
        "",
        "## Summary",
        "",
        f"- total_rules: {len(rules)}",
        f"- exact_duplicate_groups: {len(duplicate_summary['exact_duplicates'])}",
        f"- near_duplicate_pairs: {len(duplicate_summary['near_duplicates'])}",
        "",
    ]
    severity_rank = {"blocker": 0, "major": 1, "minor": 2, "info": 3}
    for category in sorted(by_category):
        category_rules = sorted(by_category[category], key=lambda rule: (severity_rank.get(rule.severity, 9), rule.source_path, rule.line))
        lines.extend([f"## {category}", ""])
        for rule in category_rules[:25]:
            lines.append(f"- `{rule.rule_id}` [{rule.severity}] {rule.text} ({rule.source_path}:{rule.line})")
        lines.append("")
    (output_dir / "rule-digest.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build rule registry and task-scoped rule packs.")
    parser.add_argument("--root", required=True, help="Target project root.")
    parser.add_argument("--output-dir", default="artifacts/rule-governance", help="Output directory relative to root.")
    parser.add_argument("--max-rules-per-pack", type=int, default=120)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output_dir = (root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    pack_dir = output_dir / "task-rule-packs"
    pack_dir.mkdir(parents=True, exist_ok=True)

    rules = collect_rules(root)
    duplicates = duplicate_report(rules)
    generated_at = datetime.now(timezone.utc).isoformat()

    registry = {
        "document_number": "RUL-AIP-20260520-001",
        "document_status": "generated",
        "retention_policy": "keep_until_regenerated",
        "generated_at": generated_at,
        "source_root": str(root),
        "html_source_policy": "excluded",
        "rule_count": len(rules),
        "rules": [rule_to_json(rule) for rule in rules],
    }
    (output_dir / "rule-registry.json").write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "rule-duplicate-report.json").write_text(json.dumps(duplicates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_digest(output_dir, rules, duplicates)

    packs = build_task_packs(rules, args.max_rules_per_pack)
    for task, pack in packs.items():
        (pack_dir / f"{task}.json").write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pack_index = {
        "document_status": "generated",
        "retention_policy": "keep_until_regenerated",
        "generated_at": generated_at,
        "pack_directory": "artifacts/rule-governance/task-rule-packs",
        "packs": [
            {
                "task_type": task,
                "path": f"artifacts/rule-governance/task-rule-packs/{task}.json",
                "rule_count": pack["rule_count"],
            }
            for task, pack in sorted(packs.items())
        ],
    }
    (output_dir / "rule-pack-index.json").write_text(json.dumps(pack_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "rule_count": len(rules), "pack_count": len(packs)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
