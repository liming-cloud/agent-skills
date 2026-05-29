#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

SKILL_ID = "high-level-design"
POLICY = {
  "required_sections": [
    "1. 版本变更记录",
    "2. 平台概述",
    "3. 系统设计",
    "3.1 系统逻辑视图",
    "3.1.1 系统设计原则",
    "3.3 研发视图",
    "3.4 研发结构定义",
    "4. 核心功能",
    "5.中间件设计",
    "6.数据视图"
  ],
  "forbidden_headings": [
    "证据",
    "Findings",
    "必须补充信息",
    "门禁决策"
  ]
}


def load_payload(path):
    schema = json.loads(Path(__file__).parents[1].joinpath("output.schema.json").read_text(encoding="utf-8"))
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [field for field in schema.get("required", []) if field not in payload]
    if missing:
        raise SystemExit(f"缺少必填字段: {missing}")
    if payload.get("skill_id") != schema["properties"]["skill_id"]["const"]:
        raise SystemExit("skill_id 不匹配")
    if payload.get("status") not in schema["properties"]["status"]["enum"]:
        raise SystemExit("status 不合法")
    return payload


def artifact_map(payload):
    return {item.get("name"): item for item in payload.get("artifacts", [])}


def resolve_artifact(payload_path, item):
    raw = item.get("path") if item else ""
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute():
        return path
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path
    return Path(payload_path).parent / path


def read_artifact(payload_path, payload, name):
    item = artifact_map(payload).get(name)
    path = resolve_artifact(payload_path, item)
    if path and path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def markdown_headings(text):
    return [match.group(1).strip() for match in re.finditer(r"(?m)^#{1,6}\s*(?:\d+(?:\.\d+)*\s*)?(.+?)\s*$", text)]


def fail(errors):
    if errors:
        raise SystemExit("\n".join(errors))
    print("ok")


def validate_output(payload_path, payload):
    errors = []
    text = read_artifact(payload_path, payload, "high-level-design.md")
    if not text:
        return ["缺少 high-level-design.md artifact 或文件不可读"]
    for section in POLICY["required_sections"]:
        if section not in text:
            errors.append("high-level-design.md 缺少团队概要设计模板章节: " + section)
    section_positions = []
    for section in POLICY["required_sections"]:
        index = text.find(section)
        if index >= 0:
            section_positions.append(index)
    if section_positions != sorted(section_positions):
        errors.append("high-level-design.md 章节顺序必须与团队概要设计模板一致")
    normalized_headings = [re.sub(r"\s+", " ", heading).strip(" ：:") for heading in markdown_headings(text)]
    for forbidden in POLICY["forbidden_headings"]:
        if any(heading == forbidden or heading.startswith(forbidden + " ") for heading in normalized_headings):
            errors.append("high-level-design.md 不得使用通用产物模板标题: " + forbidden)
    for required in ["系统逻辑视图", "系统设计原则", "研发视图", "研发结构定义", "中间件设计", "数据视图"]:
        if required not in text:
            errors.append("high-level-design.md 缺少概要设计核心内容: " + required)
    return errors


payload_path = Path(sys.argv[1])
payload = load_payload(payload_path)
fail(validate_output(payload_path, payload))
