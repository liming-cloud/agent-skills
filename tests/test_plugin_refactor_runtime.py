#!/usr/bin/env python3
"""Regression checks for the engineering-assistant runtime refactor."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "engineering-assistant"


class PluginRuntimeRefactorTests(unittest.TestCase):
    def test_implementation_controller_is_source_generated_and_mirrored(self) -> None:
        generator = (ROOT / "generate_engineering_assistant_assets.py").read_text(encoding="utf-8")
        self.assertIn('"id": "implementation-controller"', generator)
        self.assertIn('"contract-driven-development"', generator)
        self.assertIn('"init_task.py"', generator)
        self.assertIn('"run_quality_commands.py"', generator)

        for root in [ROOT, PLUGIN_ROOT]:
            skill = root / "skills" / "implementation-controller"
            self.assertTrue((skill / "SKILL.md").exists(), f"{skill} missing SKILL.md")
            self.assertTrue((skill / "contract.yaml").exists(), f"{skill} missing contract")
            contract = json.loads((skill / "contract.yaml").read_text(encoding="utf-8"))
            self.assertEqual("implementation-controller", contract["skill_id"])
            self.assertIn("quality-contract.json", json.dumps(contract, ensure_ascii=False))

    def test_contract_driven_workflow_places_controller_after_design_review(self) -> None:
        full = json.loads((ROOT / "engineering-assistant" / "workflows" / "full-feature-development.yaml").read_text(encoding="utf-8"))
        node_ids = [node["node_id"] for node in full["nodes"]]
        self.assertLess(node_ids.index("design-review"), node_ids.index("implementation-controller"))
        self.assertLess(node_ids.index("implementation-controller"), node_ids.index("code-development"))

        dedicated = ROOT / "engineering-assistant" / "workflows" / "contract-driven-development.yaml"
        self.assertTrue(dedicated.exists(), "missing contract-driven-development workflow")
        workflow = json.loads(dedicated.read_text(encoding="utf-8"))
        self.assertEqual("contract-driven-development", workflow["workflow_id"])
        self.assertIn("implementation-controller", [node["node_id"] for node in workflow["nodes"]])

    def test_runtime_policy_pack_exists_and_is_packaged(self) -> None:
        required = [
            "AGENTS.md",
            "engineering-assistant/runtime/codex/README.md",
            "engineering-assistant/runtime/codex/config.toml",
            "engineering-assistant/runtime/codex/rules/default.rules",
            "engineering-assistant/runtime/codex/hooks/pre_tool_use_policy.py",
        ]
        for rel in required:
            self.assertTrue((ROOT / rel).exists(), f"missing source runtime policy file {rel}")
            if rel != "AGENTS.md":
                self.assertTrue((PLUGIN_ROOT / rel).exists(), f"missing packaged runtime policy file {rel}")

        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertLess(len(agents.splitlines()), 90, "AGENTS.md should stay concise")
        self.assertIn("artifacts/_control", agents)

    def test_source_and_plugin_trees_are_synchronized(self) -> None:
        for left, right in [
            (ROOT / "skills", PLUGIN_ROOT / "skills"),
            (ROOT / "engineering-assistant", PLUGIN_ROOT / "engineering-assistant"),
        ]:
            result = subprocess.run(
                ["diff", "-qr", str(left), str(right)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
