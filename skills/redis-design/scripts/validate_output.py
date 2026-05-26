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


def validate_detailed(payload_path, payload):
    errors = []
    text = read_artifact(payload_path, payload, "detailed-design.md")
    if not text:
        return ["缺少 detailed-design.md artifact 或文件不可读"]
    normalized_headings = [re.sub(r"\s+", " ", heading).strip(" ：:") for heading in markdown_headings(text)]
    for forbidden in POLICY["forbidden_headings"]:
        if any(heading == forbidden or heading.startswith(forbidden + " ") for heading in normalized_headings):
            errors.append("detailed-design.md 包含禁止标题: " + forbidden)
    if "sequenceDiagram" in text:
        errors.append("detailed-design.md 不得包含 sequenceDiagram")
    if "flowchart" not in text:
        errors.append("detailed-design.md 必须包含 flowchart")
    flow_blocks = list(re.finditer(r"```mermaid\s*\n\s*flowchart[\s\S]*?```", text))
    for index, block in enumerate(flow_blocks, start=1):
        tail = text[block.end(): block.end() + 700]
        if "流程设计说明" not in tail:
            errors.append(f"第 {index} 个 flowchart 后缺少流程设计说明")
            continue
        for field in POLICY["flow_note_fields"]:
            if field not in tail:
                errors.append(f"第 {index} 个 flowchart 的流程设计说明缺少 {field}")
    if any(term in text for term in POLICY["ddd_terms"]) and "classDiagram" not in text:
        errors.append("出现 DDD/分层/扩展点关键词时必须包含 classDiagram")
    artifacts = artifact_map(payload)
    for doc_name in POLICY["specialty_docs"]:
        if doc_name not in artifacts:
            errors.append("StageRunResult.artifacts 未登记专项文档: " + doc_name)
    status = payload.get("status")
    high_risk_terms = ["DDL", "CREATE TABLE", "ALTER TABLE", "新队列", "新 topic", "新Topic", "Redis 新 Key", "新增 Key"]
    if status == "succeeded" and any(term in text for term in high_risk_terms):
        errors.append("存在 DDL、MQ 新队列/topic 或 Redis 新 Key 时状态必须为 waiting_for_human_review")
    return errors


def validate_database(payload_path, payload):
    errors = []
    text = read_artifact(payload_path, payload, "database-design.md")
    if not text:
        return ["缺少 database-design.md artifact 或文件不可读"]
    sections = POLICY["olap_sections"] if any(term in text for term in ["ClickHouse", "MergeTree", "物化视图", "分析宽表"]) else POLICY["oltp_sections"]
    for section in sections:
        if section not in text:
            errors.append("database-design.md 缺少模板章节或字段: " + section)
    for match in re.finditer(r"(?is)\b(update|delete)\b([^;]{0,300});", text):
        if "where" not in match.group(2).lower():
            errors.append("禁止没有 WHERE 的 UPDATE/DELETE")
    final_status = payload.get("document_metadata", {}).get("document_status")
    if final_status in {"approved", "final"}:
        for required in ["库名", "实例", "字符集", "索引名"]:
            if required + "：" not in text and required + ":" not in text:
                errors.append("approved/final 文档必须确认" + required)
    if payload.get("status") == "succeeded" and any(term in text for term in ["CREATE TABLE", "ALTER TABLE", "DROP TABLE", "DDL"]):
        errors.append("包含 DDL 时必须 waiting_for_human_review")
    return errors


def validate_redis(payload_path, payload):
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


def validate_mq(payload_path, payload):
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
validators = {
    "detailed-design": validate_detailed,
    "database-design": validate_database,
    "redis-design": validate_redis,
    "mq-design": validate_mq,
}
fail(validators[SKILL_ID](payload_path, payload))
