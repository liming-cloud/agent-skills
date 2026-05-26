#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from control_runtime import checksum, compact_lines, ensure_control_dir, find_file_patterns, now_iso, read_json, update_artifact_index, validate_target_project_root, write_json

DEFAULT_FORBIDDEN = [".git/", ".idea/", "node_modules/", "target/", "build/", "dist/", "coverage/"]
DEFAULT_RULES = [
    "Every changed source file must map to design-contract goals or acceptance criteria.",
    "Do not modify forbidden modules or generated dependency/build directories.",
    "Follow existing repository framework, layering, mapper/repository, service, and test conventions.",
    "Record unresolved business decisions in open-questions.json instead of guessing.",
    "A succeeded stage must not contain blocker or major findings, blocked quality gates, or product-completion blockers.",
]
PLACEHOLDER_RE = re.compile(r"(待 code-development 阶段写入|待确认|todo|tbd|placeholder)", re.IGNORECASE)

def is_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER_RE.search(value or ""))

def infer_commands(profile: dict, file_patterns: list[str]):
    commands = []
    raw_quality = profile.get("quality_commands", [])
    raw_items = []
    if isinstance(raw_quality, list):
        raw_items.extend(raw_quality)
    elif isinstance(raw_quality, dict):
        for value in raw_quality.values():
            raw_items.extend(value if isinstance(value, list) else [value])
    for item in raw_items:
        if isinstance(item, str) and not is_placeholder(item):
            commands.append({"id": item.split()[0], "command": item, "required": True})
        elif isinstance(item, dict) and item.get("command") and not is_placeholder(item["command"]):
            commands.append({"id": item.get("id", f"cmd-{len(commands) + 1}"), "command": item["command"], "required": item.get("required", True)})
    pattern_text = "\n".join(file_patterns)
    if not commands and re.search(r"(^|/)pom\.xml$|backend/", pattern_text):
        commands.append({"id": "backend-test", "command": "mvn -q test", "required": True})
    if not commands and "frontend/console-web" in pattern_text:
        commands.append({"id": "frontend-test", "command": "cd frontend/console-web && npm test", "required": True})
        commands.append({"id": "frontend-build", "command": "cd frontend/console-web && npm run build", "required": True})
    if not commands:
        commands.append({"id": "repo-test", "command": "python3 -m unittest discover", "required": True})
    return commands

def grep_lines(lines: list[str], keywords: list[str], limit: int = 12) -> list[str]:
    selected = []
    lowered_keywords = [item.lower() for item in keywords]
    for line in lines:
        lowered = line.lower()
        if any(keyword in lowered for keyword in lowered_keywords) and line not in selected:
            selected.append(line[:240])
        if len(selected) >= limit:
            break
    return selected

def backtick_values(text: str) -> list[str]:
    values = []
    for item in re.findall(r"`([^`\n]+)`", text):
        item = item.strip()
        if item and item not in values:
            values.append(item)
    return values

def infer_expected_contracts(text: str, lines: list[str], file_patterns: list[str]) -> dict:
    ticks = backtick_values(text)
    api_like = [item for item in ticks if item.startswith("/") or "/api/" in item or item.lower().endswith(("request", "response", "controller"))]
    service_like = [item for item in ticks if re.search(r"(Service|UseCase|Application|应用服务|用例)$", item)]
    repo_like = [item for item in ticks if re.search(r"(Repository|Mapper|Port|仓储|持久化|MyBatis)", item, re.IGNORECASE)]
    if not api_like:
        api_like = grep_lines(lines, ["api", "接口", "controller", "request", "response"], 8)
    if not service_like:
        service_like = grep_lines(lines, ["application service", "应用服务", "use case", "用例", "领域服务"], 8)
    if not repo_like:
        repo_like = grep_lines(lines, ["repository", "mapper", "port", "仓储", "持久化", "mybatis"], 8)
    if not api_like and any("frontend/" in item or "backend/" in item for item in file_patterns):
        api_like = ["All changed public API contracts must be explicitly mapped to request/response tests."]
    if not service_like and any("backend/" in item for item in file_patterns):
        service_like = ["Each backend use case must identify one application service boundary and one bounded-context owner."]
    if not repo_like and any("backend/" in item for item in file_patterns):
        repo_like = ["Persistence access must go through repository/mapper adapters declared by the task design."]
    return {"expected_interfaces": api_like[:20], "expected_services": service_like[:20], "expected_repositories_or_mappers": repo_like[:20]}

def infer_technology_adoption_contract(text: str, file_patterns: list[str], profile: dict) -> dict:
    explicit = profile.get("technology_adoption_contract")
    if isinstance(explicit, dict) and explicit:
        return explicit
    frameworks = profile.get("backend_frameworks", {}) if isinstance(profile.get("backend_frameworks"), dict) else {}
    persistence = frameworks.get("persistence") or profile.get("persistence_framework") or ""
    pattern_text = "\n".join(file_patterns)
    backend_like = bool(re.search(r"backend/|pom\.xml|spring|java", pattern_text + "\n" + text, re.IGNORECASE))
    frontend_like = bool(re.search(r"frontend/|react|vite|tsx|jsx|package\.json", pattern_text + "\n" + text, re.IGNORECASE))
    if backend_like and (not persistence or "mybatis" in str(persistence).lower()):
        return {
            "backend_framework": frameworks.get("web") or profile.get("backend_framework") or "Spring Boot",
            "persistence_framework": persistence or "mybatis-plus",
            "required_indicators": ["BaseMapper", "@Mapper", "extends ServiceImpl", "LambdaQueryWrapper"],
            "forbidden_indicators": ["DriverManager.getConnection", "JdbcTemplate", "java.sql.Statement"],
            "minimum_required_indicators": 1,
            "review_required_for": ["JDBC", "direct SQL bypassing mapper/repository"],
        }
    if frontend_like:
        frontend_stack = profile.get("frontend_stack") or "React/Vite"
        return {
            "frontend_stack": frontend_stack,
            "required_indicators": ["React", "Vite", "useState", "useEffect", "render(", "describe("],
            "forbidden_indicators": ["document.querySelector", "innerHTML"],
            "minimum_required_indicators": 1,
            "review_required_for": ["framework replacement", "component library replacement", "direct DOM mutation"],
        }
    return {"required_indicators": [], "forbidden_indicators": [], "minimum_required_indicators": 0, "review_required_for": []}

def infer_required_tests(text: str, file_patterns: list[str], profile: dict) -> list[str]:
    tests = [item.strip() for item in profile.get("required_tests", []) if isinstance(item, str) and item.strip() and not is_placeholder(item)] if isinstance(profile.get("required_tests"), list) else []
    pattern_text = "\n".join(file_patterns)
    if "backend/" in pattern_text:
        tests.extend(["backend unit tests for domain/application invariants and failure paths", "backend architecture boundary tests for DDD dependencies and high cohesion"])
    if "frontend/console-web" in pattern_text:
        tests.extend(["frontend component tests for forms, guards, and error states", "frontend integration tests for real API client and permission-driven navigation"])
    if re.search(r"真实环境|E2E|验收|release", text, re.IGNORECASE):
        tests.append("real environment smoke or Playwright E2E proving frontend-backend interaction with required dependencies")
    if not tests:
        tests.append("task-specific failing test must be written before implementation and pass before review")
    return list(dict.fromkeys(tests))

def main():
    parser = argparse.ArgumentParser(description="Compile an approved design artifact into machine-readable control contracts.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--design", required=True)
    parser.add_argument("--task-id")
    parser.add_argument("--profile")
    args = parser.parse_args()
    root = validate_target_project_root(Path(args.root))
    design_path = Path(args.design)
    if not design_path.is_absolute():
        design_path = root / design_path
    if design_path.suffix.lower() in {".html", ".htm"}:
        raise SystemExit("HTML artifacts are human-only. Provide the approved MD/JSON/YAML design artifact instead.")
    control = ensure_control_dir(root)
    task = read_json(control / "current-task.json", {})
    profile = read_json(Path(args.profile), {}) if args.profile else task.get("project_profile", {})
    task_id = args.task_id or task.get("task_id") or design_path.stem
    text = design_path.read_text(encoding="utf-8")
    lines = compact_lines(text, 32)
    file_patterns = find_file_patterns(text)
    expected = infer_expected_contracts(text, lines, file_patterns)
    design_contract = {"task_id": task_id, "source_design": str(design_path.relative_to(root)), "source_checksum": checksum(design_path), "generated_at": now_iso(), "goals": lines[:8] or ["Implement the approved design without expanding scope."], "acceptance_criteria": lines[:12], "module_boundaries": {"allowed_from_design": file_patterns, "source": "compiled_from_design_artifact"}, "assumptions": ["The human-approved design is the source of truth for implementation scope."]}
    implementation_contract = {"task_id": task_id, "allowed_modules": file_patterns, "forbidden_modules": DEFAULT_FORBIDDEN, "required_files_or_patterns": file_patterns, "expected_interfaces": expected["expected_interfaces"], "expected_services": expected["expected_services"], "expected_repositories_or_mappers": expected["expected_repositories_or_mappers"], "technology_adoption_contract": infer_technology_adoption_contract(text, file_patterns, profile), "architecture_rules": DEFAULT_RULES, "required_tests": infer_required_tests(text, file_patterns, profile), "done_conditions": ["No changed file is outside allowed scope unless approved.", "Design-to-code validation passes with no blocker or major findings.", "Technology adoption validation passes.", "Rule consumption validation passes.", "Required quality commands pass; missing commands are blocking.", "Open blocking questions are empty."], "generated_at": now_iso()}
    quality_contract = {"task_id": task_id, "required_commands": infer_commands(profile, file_patterns), "required_evidence": ["control_health", "design_to_code_mapping", "technology_adoption", "rule_consumption", "quality_commands"], "quality_gates": ["control_health", "design_to_code_mapping", "technology_adoption", "rule_consumption", "architecture_boundary", "build_lint_test", "semantic_review"], "repair_policy": {"max_attempts": 2, "ask_human_only_for": ["approved design conflict", "business decision missing", "high risk approval", "production action", "repair attempts exhausted"]}, "generated_at": now_iso()}
    write_json(control / "design-contract.json", design_contract)
    write_json(control / "implementation-contract.json", implementation_contract)
    write_json(control / "quality-contract.json", quality_contract)
    context = ["# Agent Context Pack", "", "## Read First", "- This is the task-scoped context pack. Consume it before broad doc search.", "- Required rule ids must come from `artifacts/rule-governance/task-rule-packs/code-development.json`.", "- A stale changed-files report, missing rule pack, blocking open question, or failed gate means stop and report blocked.", "", f"- task_id: {task_id}", f"- source_design: {design_contract['source_design']}", f"- source_checksum: {design_contract['source_checksum']}", f"- task_rule_pack: artifacts/rule-governance/task-rule-packs/code-development.json", "", "## Goals", *[f"- {item}" for item in design_contract["goals"]], "", "## Allowed Modules", *[f"- {item}" for item in implementation_contract["allowed_modules"]], "", "## Technology Adoption Contract", f"- {json.dumps(implementation_contract['technology_adoption_contract'], ensure_ascii=False)}", "", "## Required Evidence", *[f"- {item}" for item in quality_contract["required_evidence"]], "", "## Fast Validation Commands", "- python3 engineering-assistant/scripts/run_controlled_task.py --root <project-root> --mode audit-readonly", "- python3 engineering-assistant/scripts/run_controlled_task.py --root <project-root> --rule-evidence <evidence-json>", ""]
    (control / "task-context.agent.md").write_text("\n".join(context), encoding="utf-8")
    for name, rel, artifact_type in [("design-contract.json", control / "design-contract.json", "json"), ("implementation-contract.json", control / "implementation-contract.json", "json"), ("quality-contract.json", control / "quality-contract.json", "json"), ("task-context.agent.md", control / "task-context.agent.md", "markdown")]:
        update_artifact_index(root, name, rel, artifact_type, "implementation-controller")
    task.update({"task_id": task_id, "status": "contract_compiled", "current_contracts": {"design_contract": str((control / "design-contract.json").relative_to(root)), "implementation_contract": str((control / "implementation-contract.json").relative_to(root)), "quality_contract": str((control / "quality-contract.json").relative_to(root)), "context_pack": str((control / "task-context.agent.md").relative_to(root))}, "updated_at": now_iso()})
    write_json(control / "current-task.json", task)
    print(control / "implementation-contract.json")

if __name__ == "__main__":
    main()
