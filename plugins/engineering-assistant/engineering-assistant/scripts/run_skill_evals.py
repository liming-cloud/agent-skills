#!/usr/bin/env python3
import json
from pathlib import Path

CASES = ["happy_path", "missing_required_input", "ambiguous_input", "policy_conflict", "edge_case", "regression_case", "technology_demo_adoption", "control_plane_drift", "rule_consumption_gap", "context_noise_overload", "low_quality_automation"]
REQUIRED_FIELDS = ["id", "name", "case_type", "scenario", "input", "expected_behavior", "expected_gate_decision", "expected_status", "pass_criteria", "required_artifacts", "grader"]
SCENARIO_FIELDS = ["title", "material", "system_scope", "team_rule_refs", "risk_focus", "forbidden_behavior"]
VALID_DECISIONS = {"pass", "waiting_for_input", "require_human_review", "block"}
VALID_STATUS = {"succeeded", "waiting_for_input", "waiting_for_human_review", "blocked"}
GENERIC_EXPECTED = {"生成声明产物并输出门禁决策", "识别该场景并避免误判通过"}

errors = []
warnings = []

for required_eval in [
    Path("engineering-assistant/evals/trigger/trigger-cases.jsonl"),
    Path("engineering-assistant/evals/safety/safety-cases.jsonl"),
]:
    if not required_eval.exists():
        errors.append(f"{required_eval}: 缺少团队级 eval 数据集")
    elif not required_eval.read_text(encoding="utf-8").strip():
        errors.append(f"{required_eval}: eval 数据集为空")


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{path}: 无法解析为 JSON/YAML 子集: {exc}")
        return {}


for skill in sorted(p for p in Path("skills").glob("*") if p.is_dir()):
    contract_path = skill / "contract.yaml"
    contract = load_json(contract_path) if contract_path.exists() else {}
    output_schema = load_json(skill / "output.schema.json") if (skill / "output.schema.json").exists() else {}
    declared_outputs = [item["name"] for item in contract.get("outputs", []) if item.get("name") != "code changes"]
    language_policy = contract.get("language_policy", {})
    if language_policy.get("when_unspecified") != "ask_user":
        errors.append(f"{contract_path}: language_policy.when_unspecified 必须为 ask_user")
    technology_selection_policy = contract.get("technology_selection_policy", {})
    categories = set(technology_selection_policy.get("categories", []))
    for category in ["backend_framework", "persistence_framework", "frontend_stack", "test_framework", "build_tool"]:
        if category not in categories:
            errors.append(f"{contract_path}: technology_selection_policy.categories 缺少 {category}")
    if technology_selection_policy.get("team_defaults", {}).get("java_spring_persistence") != "mybatis-plus":
        errors.append(f"{contract_path}: technology_selection_policy.team_defaults.java_spring_persistence 必须为 mybatis-plus")
    if technology_selection_policy.get("ask_user_when_unspecified") is not True:
        errors.append(f"{contract_path}: technology_selection_policy.ask_user_when_unspecified 必须为 true")
    if "JDBC" not in technology_selection_policy.get("requires_review", []):
        errors.append(f"{contract_path}: technology_selection_policy.requires_review 必须包含 JDBC")
    execution_gates = contract.get("execution_gates", {})
    for gate in ["preflight_required_information", "formal_document_metadata_required", "stage_result_validation_required", "block_when_agent_violates_contract"]:
        if execution_gates.get(gate) is not True:
            errors.append(f"{contract_path}: execution_gates.{gate} 必须为 true")
    required_schema_fields = set(output_schema.get("required", []))
    for field in ["language", "document_metadata", "required_information_requests"]:
        if field not in required_schema_fields:
            errors.append(f"{skill / 'output.schema.json'}: required 缺少 {field}")
    fingerprints = set()
    for case in CASES:
        path = skill / "evals" / f"{case}.yaml"
        if not path.exists():
            errors.append(f"{path}: eval 用例缺失")
            continue
        data = load_json(path)
        if not data:
            continue
        for field in REQUIRED_FIELDS:
            if field not in data:
                errors.append(f"{path}: 缺少字段 {field}")
        if data.get("case_type") != case:
            errors.append(f"{path}: case_type 应为 {case}")
        scenario = data.get("scenario", {})
        for field in SCENARIO_FIELDS:
            if field not in scenario:
                errors.append(f"{path}: scenario 缺少字段 {field}")
        if len(str(scenario.get("material", ""))) < 40:
            errors.append(f"{path}: scenario.material 过短，不能作为真实压力场景")
        if not scenario.get("team_rule_refs"):
            errors.append(f"{path}: 未引用团队规范编号")
        if len(scenario.get("risk_focus", [])) < 2:
            errors.append(f"{path}: risk_focus 至少需要两个风险点")
        if not scenario.get("forbidden_behavior"):
            errors.append(f"{path}: forbidden_behavior 不能为空")
        if data.get("expected_behavior") in GENERIC_EXPECTED:
            errors.append(f"{path}: expected_behavior 仍是骨架模板")
        if data.get("expected_gate_decision") not in VALID_DECISIONS:
            errors.append(f"{path}: expected_gate_decision 不合法")
        if data.get("expected_status") not in VALID_STATUS:
            errors.append(f"{path}: expected_status 不合法")
        if len(data.get("pass_criteria", [])) < 5:
            errors.append(f"{path}: pass_criteria 过少，无法形成团队门禁")
        criteria_text = "\n".join(data.get("pass_criteria", []))
        for required_text in ["language", "document_metadata", "required_information_requests"]:
            if required_text not in criteria_text:
                errors.append(f"{path}: pass_criteria 缺少运行时行为断言 {required_text}")
        if skill.name in {"code-development", "detailed-design", "design-review", "code-review", "code-quality-governor"} and "framework" not in criteria_text and "mybatis-plus" not in criteria_text:
            errors.append(f"{path}: pass_criteria 缺少框架选型/mybatis-plus 防回归断言")
        if skill.name in {"code-review", "code-quality-governor"}:
            for required_text in ["sonar", "qodana", "checkstyle", "complexity", "HTML"]:
                if required_text not in criteria_text:
                    errors.append(f"{path}: pass_criteria 缺少静态分析/HTML 防回归断言 {required_text}")
        if skill.name in {"frontend-design", "frontend-development"} and "frontend" not in criteria_text:
            errors.append(f"{path}: pass_criteria 缺少 frontend 防回归断言")
        if case == "missing_required_input" and "questions" not in criteria_text:
            errors.append(f"{path}: missing_required_input 必须断言 questions 非空")
        stage_request = data.get("input", {}).get("stage_run_request", {})
        if stage_request.get("skill_id") != skill.name:
            errors.append(f"{path}: stage_run_request.skill_id 与目录不一致")
        if data.get("required_artifacts") != declared_outputs:
            errors.append(f"{path}: required_artifacts 与 contract outputs 不一致")
        fingerprint = json.dumps({
            "material": scenario.get("material"),
            "rules": scenario.get("team_rule_refs"),
            "decision": data.get("expected_gate_decision"),
        }, ensure_ascii=False, sort_keys=True)
        if fingerprint in fingerprints:
            errors.append(f"{path}: 与同 skill 其他 eval 场景重复")
        fingerprints.add(fingerprint)
        if skill.name in {"high-level-design", "detailed-design", "redis-design", "mq-design", "database-design", "design-review"} and len(scenario.get("team_rule_refs", [])) < 3:
            warnings.append(f"{path}: 核心设计 skill 建议至少引用 3 条团队规范")

for required_skill in ["frontend-design", "frontend-development"]:
    if not (Path("skills") / required_skill / "SKILL.md").exists():
        errors.append(f"skills/{required_skill}: 前端研发流程 skill 缺失")

if errors:
    raise SystemExit("\n".join(errors))
if warnings:
    print("\n".join(f"warning: {item}" for item in warnings))
print("ok")
