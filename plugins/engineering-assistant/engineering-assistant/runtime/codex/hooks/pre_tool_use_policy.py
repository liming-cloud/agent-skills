#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

payload = json.load(sys.stdin)
cmd = payload.get("tool_input", {}).get("command", "")

POLICY_PATH = Path(__file__).resolve().parents[1] / "policies" / "tool-policy.yaml"
policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def matches(rule: dict, command: str) -> bool:
    matcher = rule.get("match", {})
    if matcher.get("contains") and matcher["contains"] in command:
        return True
    if matcher.get("regex") and re.search(matcher["regex"], command):
        return True
    return False


matched_context = []
for rule in policy.get("policies", []):
    if not matches(rule, cmd):
        continue
    if rule.get("decision") == "deny":
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": rule.get("reason", "命中工具策略阻断规则。"),
                "policyId": rule.get("id")
            }
        }, ensure_ascii=False))
        sys.exit(0)
    matched_context.append(rule.get("reason", "命中允许策略。"))

additional_context = "本仓库启用研发助手运行时策略；高风险动作必须人工确认。"
if matched_context:
    additional_context += " " + " ".join(matched_context)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "additionalContext": additional_context
    }
}, ensure_ascii=False))
