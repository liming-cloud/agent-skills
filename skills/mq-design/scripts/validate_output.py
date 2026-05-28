#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

SKILL_ID = "mq-design"
POLICY = {
  "producer_fields": [
    "业务用途",
    "场景应用",
    "业务消息 key",
    "消息类型",
    "消息体内容",
    "优先等级",
    "消息 TTL",
    "持久化",
    "目的交换机",
    "路由 key",
    "消息预估大小",
    "生产服务或模块名称",
    "软件需求号或 bug 号",
    "设计日期",
    "设计者",
    "备注"
  ],
  "consumer_fields": [
    "队列名称",
    "业务用途",
    "场景应用",
    "单消费节点消费",
    "队列类型",
    "优先队列",
    "是否持久化",
    "自动删除",
    "TTL",
    "消息大小",
    "绑定的 Exchange/routingKey",
    "死信队列 exchange/routeKey",
    "消费服务",
    "消息 key",
    "运维监控",
    "软件需求号或 bug 号",
    "设计日期",
    "设计者",
    "备注"
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
    text = read_artifact(payload_path, payload, "mq-design.md")
    if not text:
        return ["缺少 mq-design.md artifact 或文件不可读"]
    for field in POLICY["producer_fields"]:
        if field not in text:
            errors.append("mq-design.md 生产者表缺少字段: " + field)
    for field in POLICY["consumer_fields"]:
        if field not in text:
            errors.append("mq-design.md 消费者表缺少字段: " + field)
    if "死信" not in text:
        errors.append("MQ 必须设计死信队列")
    if "幂等" not in text:
        errors.append("MQ 必须定义幂等策略")
    for size in re.findall(r"(\d+)\s*KB", text, re.IGNORECASE):
        if int(size) > 10 and payload.get("status") == "succeeded":
            errors.append("消息体超过 10KB 必须 waiting_for_human_review")
    if payload.get("status") == "succeeded" and any(term in text for term in ["回放生产消息", "删除队列", "重命名队列", "删除 topic", "重命名 topic", "删除Topic", "重命名Topic"]):
        errors.append("生产消息回放或删除/重命名 topic/queue 必须 waiting_for_human_review")
    return errors


payload_path = Path(sys.argv[1])
payload = load_payload(payload_path)
fail(validate_output(payload_path, payload))
