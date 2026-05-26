#!/usr/bin/env python3
"""Regression checks for control-plane health enforcement."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SCRIPTS = ROOT / "engineering-assistant" / "scripts"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class ControlHealthGuardTests(unittest.TestCase):
    def test_control_health_script_is_generated_and_packaged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            publish_root = Path(temp_dir) / "publish"
            result = subprocess.run(
                [
                    "python3",
                    str(ROOT / "engineering-assistant" / "scripts" / "publish_plugin.py"),
                    "--publish-root",
                    str(publish_root),
                    "--marketplace-path",
                    str(publish_root / ".agents" / "plugins" / "marketplace.json"),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr + result.stdout)
            bases = [ROOT, publish_root / "plugins" / "teamwork-engineering-assistant"]
            for base in bases:
                script = base / "engineering-assistant" / "scripts" / "validate_control_health.py"
                self.assertTrue(script.exists(), f"missing {script}")
                self.assertIn("control-health-report.json", script.read_text(encoding="utf-8"))

    def test_control_health_blocks_missing_rule_pack_and_open_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            control = root / "artifacts" / "_control"
            control.mkdir(parents=True)
            write_json(control / "current-task.json", {"task_id": "aip", "status": "contract_compiled"})
            write_json(control / "artifact-index.json", {"artifacts": {}})
            write_json(control / "implementation-contract.json", {"technology_adoption_contract": {"persistence_framework": "mybatis-plus"}})
            write_json(control / "quality-contract.json", {"required_evidence": ["technology_adoption", "rule_consumption"]})
            write_json(control / "open-questions.json", {"questions": [{"id": "Q1", "severity": "blocker", "status": "open"}]})
            (control / "task-context.agent.md").write_text("# Agent Context\n", encoding="utf-8")

            result = subprocess.run(
                ["python3", str(PLUGIN_SCRIPTS / "validate_control_health.py"), "--root", str(root), "--task-type", "code-development"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(0, result.returncode)
            report = json.loads((control / "control-health-report.json").read_text(encoding="utf-8"))
            self.assertEqual("block", report["status"])
            reasons = " ".join(item["reason"] for item in report["findings"])
            self.assertIn("missing task rule pack", reasons)
            self.assertIn("blocking open question", reasons)


if __name__ == "__main__":
    unittest.main()
