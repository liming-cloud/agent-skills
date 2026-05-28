#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

SKILL_ID = "database-design"
POLICY = {
  "oltp_sections": [
    "1. 文档信息",
    "1.1 变更记录",
    "1.2 术语定义",
    "1.3 参考文档",
    "2. 文档定位",
    "2.1 编写目的",
    "2.2 设计对象类型",
    "2.3 与其他文档的关系",
    "2.4 强耦合表组说明",
    "3. 业务语义与生命周期",
    "3.1 表的业务职责",
    "3.2 核心业务场景",
    "3.3 数据生命周期阶段",
    "3.4 状态机",
    "4. 物理结构设计",
    "4.1 建表级环境与约定",
    "4.2 字段定义",
    "4.3 索引设计",
    "4.4 约束与数据库对象",
    "4.5 字段可变性矩阵",
    "4.6 技术实现依赖",
    "5. 数据量与性能设计",
    "5.1 数据量估算",
    "5.2 读写 QPS 与延迟 SLA",
    "5.3 热点与数据倾斜分析",
    "5.4 容量规划",
    "5.5 性能保障措施",
    "6. CRUD 契约设计",
    "6.1 CRUD 总览矩阵",
    "6.2 强制前置条件",
    "6.3 禁止操作清单",
    "6.4 Create",
    "6.5 Read",
    "6.6 Update",
    "6.7 Delete",
    "6.8 幂等键与重复请求",
    "6.9 批量操作与数据修复规则",
    "7. 事务、一致性与并发控制",
    "7.1 本地事务边界",
    "7.2 跨表一致性",
    "7.3 并发控制",
    "7.4 数据质量校验",
    "7.5 隔离级别、死锁与重试约定",
    "7.6 跨表最终一致",
    "8. 分区、分片与归档设计",
    "8.1 路由与分片规则",
    "8.2 分区策略",
    "8.3 查询策略",
    "8.4 归档与保留",
    "8.5 冷热分离与只读副本",
    "9. 安全与审计设计",
    "9.1 敏感字段清单",
    "9.2 脱敏与掩码规则",
    "9.3 访问控制",
    "9.4 审计要求",
    "10. 测试与验收",
    "10.1 验收检查表",
    "10.2 测试用例类型",
    "10.3 样例 SQL",
    "11. 附录",
    "11.1 DDL SQL",
    "11.2 兼容性说明"
  ],
  "olap_sections": [
    "数据分层",
    "字段级血缘",
    "MergeTree 引擎选型",
    "ORDER BY",
    "PARTITION BY",
    "TTL",
    "物化视图关系",
    "刷新策略",
    "上下游影响"
  ],
  "oltp_table_headers": [
    "| 项目 | 内容 |",
    "| 版本 | 日期 | 变更原因/依据 | 变更摘要 | 变更人 | 评审/批准 |",
    "| 术语 | 说明 |",
    "| 文档名 | 关联类型 | 参考说明 |",
    "| 成员表 | 角色 | 与主表关系 | 同事务要求 | 备注 |",
    "| 场景 ID | 场景名称 | 触发入口 | 主要 SQL 形态 | 优先级 | 频率/峰值 |",
    "| 阶段 | 进入条件 | 允许的操作类型 | 对外可见性 | 数据留存策略 |",
    "| 当前状态",
    "| 字段名 | 中文名 | 类型 | 必填 | 默认值 | 敏感级别 | 说明 |",
    "| 索引名 | 类型 | 字段",
    "| 类别 | 规则 | 实现方式 | 备注 |",
    "| 字段 | 创建时赋值 | 运行中可改 | 结束态可改 | 修改主体 | 约束/备注 |",
    "| 依赖项 | 版本/规格 | 本文档是否依赖 | 说明 |",
    "| 维度 | 估算值 | 说明 |",
    "| 场景 ID | 场景名称 | 操作类型 | QPS/TPS 目标 | P99 延迟目标 | 优先级 | 说明 |",
    "| 热点类型 | 表现 | 发生条件 | 缓解措施 |",
    "| 资源 | 估算方法 | 目标值 | 说明 |",
    "| 措施 | 适用场景 | 实施状态 | 说明 |",
    "| 操作 | 典型入口 | 定位键/幂等键 | 必备前置条件 | 允许字段/投影 | 明确禁止 | 并发控制 | 审计 |",
    "| 操作 | 编号 | 强制条件",
    "| 编号 | 禁止行为 | 适用范围 | 例外",
    "| 规则项 | 要求 |",
    "| 查询类型 | 必带条件 | 推荐索引 | 主库/只读 | 备注 |",
    "| 场景 | 前置条件 | 允许 SET 字段 | 禁止 SET 字段 | 并发 |",
    "| 操作 | 策略 | 前置条件 | 审批 |",
    "| 层级 | 机制 | 说明 |",
    "| 类型 | 允许条件 | 事务与批次 | 记录要求 |",
    "| 场景 ID | 参与表/对象 | 一致性要求 | 提交/回滚 |",
    "| 关系 | 策略 | 补偿/核对 |",
    "| 场景 | 策略 | 说明 |",
    "| 校验项 | 规则 | 频率 | 失败处理 |",
    "| 主题 | 约定 |",
    "| 步骤 | 动作 | 失败补偿 |",
    "| 分片键 |",
    "| 维度 | MySQL | PostgreSQL |",
    "| 场景 | 是否带路由/分区键 | 预期计划 | 禁止 |",
    "| 阶段 | 条件 | 目标存储 | 在线库策略 |",
    "| 数据类别 | 放置 | 查询入口 | 说明 |",
    "| 字段 | 级别 | 存储 | 应用展示 | 导出 |",
    "| 场景 | 规则 | 示例 |",
    "| 角色 | 读 | 写 | 说明 |",
    "| 事件 | 记录内容 | 保留期 |",
    "| 检查项 | 结果 | 备注 |",
    "| 类型 | 目的 | 示例 |",
    "| 主题 | 注意点 |"
  ],
  "oltp_fact_fields": [
    "文档名称",
    "逻辑库/Schema",
    "物理库标识",
    "所属集群/实例",
    "设计对象",
    "数据库产品",
    "数据库版本",
    "编写日期",
    "编写人",
    "业务负责人",
    "DBA 负责人",
    "安全/合规接口人"
  ],
  "unresolved_markers": [
    "{",
    "}",
    "待补充",
    "待确认",
    "未知",
    "未确认",
    "TBD",
    "TODO",
    "<填写",
    "请替换"
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
    text = read_artifact(payload_path, payload, "database-design.md")
    if not text:
        return ["缺少 database-design.md artifact 或文件不可读"]
    sections = POLICY["olap_sections"] if any(term in text for term in ["ClickHouse", "MergeTree", "物化视图", "分析宽表"]) else POLICY["oltp_sections"]
    for section in sections:
        if section not in text:
            errors.append("database-design.md 缺少模板章节或字段: " + section)
    if sections == POLICY.get("oltp_sections"):
        section_positions = []
        for section in POLICY["oltp_sections"]:
            index = text.find(section)
            if index >= 0:
                section_positions.append(index)
        if section_positions != sorted(section_positions):
            errors.append("database-design.md OLTP 章节顺序必须与模板一致")
        for header in POLICY["oltp_table_headers"]:
            if header not in text:
                errors.append("database-design.md 缺少 OLTP 模板表格列头: " + header)
        for field in POLICY["oltp_fact_fields"]:
            if field not in text:
                errors.append("database-design.md 文档信息缺少必填事实字段: " + field)
        for required_text in ["MC-", "PO-", "QPS", "P99", "DDL SQL", "兼容性说明", "敏感级别", "幂等"]:
            if required_text not in text:
                errors.append("database-design.md 缺少 OLTP 强制内容: " + required_text)
    for match in re.finditer(r"(?is)\b(update|delete)\b([^;]{0,300});", text):
        if "where" not in match.group(2).lower():
            errors.append("禁止没有 WHERE 的 UPDATE/DELETE")
    unresolved = [marker for marker in POLICY.get("unresolved_markers", []) if marker in text]
    if unresolved and payload.get("status") not in {"waiting_for_input", "waiting_for_human_review", "blocked"}:
        errors.append("存在未确认信息时必须 waiting_for_input，禁止推测或以占位符输出 succeeded: " + ", ".join(sorted(set(unresolved))))
    if payload.get("status") == "waiting_for_input" and not payload.get("required_information_requests"):
        errors.append("waiting_for_input 必须输出 required_information_requests 主动询问用户")
    final_status = payload.get("document_metadata", {}).get("document_status")
    if final_status in {"approved", "final"}:
        for required in ["库名", "实例", "字符集", "索引名"]:
            if required + "：" not in text and required + ":" not in text:
                errors.append("approved/final 文档必须确认" + required)
    if payload.get("status") == "succeeded" and any(term in text for term in ["CREATE TABLE", "ALTER TABLE", "DROP TABLE", "DDL"]):
        errors.append("包含 DDL 时必须 waiting_for_human_review")
    return errors


payload_path = Path(sys.argv[1])
payload = load_payload(payload_path)
fail(validate_output(payload_path, payload))
