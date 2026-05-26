#!/usr/bin/env python3
import json, sys
from pathlib import Path

REQUIRED = ["request_id", "run_id", "skill_id", "blocking", "status", "questions"]
QUESTION_REQUIRED = ["id", "question", "reason", "required", "priority", "expected_format"]
VALID_PRIORITY = {"critical", "major", "minor"}
VALID_STATUS = {"waiting_for_input", "optional_context_requested", "resolved"}

errors = []
for arg in sys.argv[1:]:
    path = Path(arg)
    data = json.loads(path.read_text(encoding="utf-8"))
    for field in REQUIRED:
        if field not in data:
            errors.append(f"{path}: 缺少字段 {field}")
    if errors:
        continue
    questions = data.get("questions", [])
    if not questions:
        errors.append(f"{path}: questions 不能为空")
    if data.get("status") not in VALID_STATUS:
        errors.append(f"{path}: status 不合法")
    if data.get("blocking") and data.get("status") != "waiting_for_input":
        errors.append(f"{path}: blocking=true 时 status 必须为 waiting_for_input")
    for index, question in enumerate(questions):
        for field in QUESTION_REQUIRED:
            if field not in question:
                errors.append(f"{path}: questions[{index}] 缺少字段 {field}")
        if question.get("priority") not in VALID_PRIORITY:
            errors.append(f"{path}: questions[{index}].priority 不合法")
        if question.get("required") and not question.get("reason"):
            errors.append(f"{path}: questions[{index}] required=true 时必须说明 reason")
if errors:
    raise SystemExit("\n".join(errors))
print("ok")
