#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

SKILL_ID = "redis-design"
POLICY = {
  "required_sections": [
    "文档头信息",
    "历史版本信息",
    "前言",
    "公共配置",
    "Redis 版本",
    "集群配置",
    "持久化策略",
    "过期淘汰策略",
    "设计项",
    "安全与运维",
    "人工评审项"
  ],
  "item_fields": [
    "特性用途",
    "业务说明",
    "存储设计",
    "库",
    "数据结构",
    "TTL",
    "Key 定义",
    "Value 数据格式",
    "预估数据和容量",
    "多团队协同"
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
    text = read_artifact(payload_path, payload, "redis-design.md")
    if not text:
        return ["缺少 redis-design.md artifact 或文件不可读"]
    for section in POLICY["required_sections"] + POLICY["item_fields"]:
        if section not in text:
            errors.append("redis-design.md 缺少模板章节或字段: " + section)
    if re.search(r"Redis\s*(作为|做|充当).{0,12}事实库", text):
        errors.append("Redis 不得作为事实库")
    if re.search(r"Redis\s*(作为|做|充当).{0,12}消息队列", text):
        errors.append("Redis 不得作为消息队列")
    if not re.search(r"TTL[^\n]*(秒|分钟|小时|天|ms|s|min|hour|day)", text, re.IGNORECASE):
        errors.append("TTL 必须带单位")
    if "降级" not in text:
        errors.append("Redis 不可用必须有降级策略")
    if payload.get("status") == "succeeded" and any(term in text for term in ["版本待确认", "拓扑待确认", "持久化待确认", "淘汰策略待确认"]):
        errors.append("Redis 版本、拓扑、持久化或淘汰策略无法确认时不得 succeeded")
    if payload.get("status") == "succeeded" and any(term in text for term in ["Redis 新 Key", "新增 Key", "新 Key"]):
        errors.append("Redis 新 Key 必须 waiting_for_human_review")
    return errors


payload_path = Path(sys.argv[1])
payload = load_payload(payload_path)
fail(validate_output(payload_path, payload))
