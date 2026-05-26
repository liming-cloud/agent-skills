#!/usr/bin/env python3
"""Regression checks for runtime hook and rules packaging."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "plugins" / "engineering-assistant" / "engineering-assistant" / "runtime" / "codex" / "hooks" / "pre_tool_use_policy.py"


class PluginRuntimeHooksRulesTests(unittest.TestCase):
    def run_hook(self, command: str) -> dict:
        result = subprocess.run(
            ["python3", str(HOOK)],
            input=json.dumps({"tool_input": {"command": command}}, ensure_ascii=False),
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def test_hook_blocks_direct_plugin_mirror_mutation(self) -> None:
        output = self.run_hook("python3 - <<'PY'\nopen('plugins/engineering-assistant/skills/x','w').write('bad')\nPY")
        decision = output["hookSpecificOutput"]
        self.assertEqual("deny", decision["permissionDecision"])
        self.assertIn("插件镜像", decision["permissionDecisionReason"])

    def test_hook_adds_context_for_controlled_task_scripts(self) -> None:
        output = self.run_hook("python3 engineering-assistant/scripts/run_controlled_task.py --root /tmp/project")
        context = output["hookSpecificOutput"].get("additionalContext", "")
        self.assertIn("受控自动化", context)

    def test_rules_file_mentions_generator_and_controlled_runner(self) -> None:
        rules = (ROOT / "engineering-assistant" / "runtime" / "codex" / "rules" / "default.rules").read_text(encoding="utf-8")
        self.assertIn("generate_engineering_assistant_assets.py", rules)
        self.assertIn("run_controlled_task.py", rules)


if __name__ == "__main__":
    unittest.main()
