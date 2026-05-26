#!/usr/bin/env python3
import json
import re
import sys

payload = json.load(sys.stdin)
cmd = payload.get("tool_input", {}).get("command", "")
plugin_write_pattern = r"plugins/engineering-assistant/"
write_intent_pattern = r"(apply_patch|>\s*|>>\s*|write_text|open\(|sed\s+-i|perl\s+-pi)"
deny_patterns = [
    r"\brm\s+-rf\b",
    r"\bgit\s+push\b",
    r"\bgit\s+commit\b",
    r"\bcurl\b.*\|\s*sh\b",
]

for pattern in deny_patterns:
    if re.search(pattern, cmd):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "命中高风险命令规则；请改走受控流程。"
            }
        }, ensure_ascii=False))
        sys.exit(0)

if re.search(plugin_write_pattern, cmd) and re.search(write_intent_pattern, cmd):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "禁止直接修改插件镜像 plugins/engineering-assistant/；请修改生成器或源树后运行 generate_engineering_assistant_assets.py 同步。"
        }
    }, ensure_ascii=False))
    sys.exit(0)

additional_context = "本仓库启用研发助手运行时策略；高风险动作必须人工确认。"
if "run_controlled_task.py" in cmd:
    additional_context += " 受控自动化会串联控制面健康、技术采用度、规则消费和质量命令；失败必须写入 repair-attempts.json。"

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": additional_context
    }
}, ensure_ascii=False))
