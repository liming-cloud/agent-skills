#!/usr/bin/env python3
"""Regression checks for hard gates in the product-development plugin flow."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SCRIPTS = ROOT / "plugins" / "engineering-assistant" / "engineering-assistant" / "scripts"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_script(script_name: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(PLUGIN_SCRIPTS / script_name), *args],
        cwd=cwd or ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class ControlledProductPipelineGuardTests(unittest.TestCase):
    def make_control_root(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        control = root / "artifacts" / "_control"
        control.mkdir(parents=True)
        write_json(control / "current-task.json", {"task_id": "aip", "status": "contract_compiled"})
        write_json(control / "design-contract.json", {"task_id": "aip", "goals": ["deliver product"]})
        write_json(control / "artifact-index.json", {"artifacts": {}})
        write_json(control / "open-questions.json", {"questions": []})
        (control / "task-context.agent.md").write_text("# Agent Context\n", encoding="utf-8")
        return root

    def test_contract_control_blocks_weak_implementation_contract(self) -> None:
        root = self.make_control_root()
        control = root / "artifacts" / "_control"
        write_json(
            control / "implementation-contract.json",
            {
                "task_id": "aip",
                "allowed_modules": ["backend/"],
                "forbidden_modules": [".git/"],
                "architecture_rules": ["Follow architecture"],
                "done_conditions": ["Design-to-code validation passes."],
            },
        )
        write_json(control / "quality-contract.json", {"required_commands": []})

        result = run_script("validate_contract_control.py", str(root))

        self.assertNotEqual(0, result.returncode)
        output = result.stdout + result.stderr
        self.assertIn("expected_interfaces", output)
        self.assertIn("required_tests", output)
        self.assertIn("required_commands", output)

    def test_design_to_code_validation_blocks_major_findings(self) -> None:
        root = self.make_control_root()
        control = root / "artifacts" / "_control"
        write_json(
            control / "implementation-contract.json",
            {
                "allowed_modules": ["backend/contexts/identity-access"],
                "forbidden_modules": ["node_modules/"],
                "required_files_or_patterns": [],
            },
        )
        write_json(control / "changed-files-report.json", {"changed_files": ["frontend/console-web/src/app/App.tsx"]})

        result = run_script("validate_design_to_code.py", "--root", str(root))

        self.assertNotEqual(0, result.returncode)
        report = json.loads((control / "design-to-code-validation.json").read_text(encoding="utf-8"))
        self.assertEqual("block", report["status"])
        self.assertEqual("major", report["findings"][0]["severity"])

    def test_quality_runner_blocks_missing_required_commands(self) -> None:
        root = self.make_control_root()
        control = root / "artifacts" / "_control"
        write_json(control / "quality-contract.json", {"required_commands": []})

        result = run_script("run_quality_commands.py", "--root", str(root))

        self.assertNotEqual(0, result.returncode)
        report = json.loads((control / "quality-run-report.json").read_text(encoding="utf-8"))
        self.assertEqual("block", report["status"])
        self.assertIn("no required quality commands", report["errors"][0])

    def test_rule_index_excludes_nested_generated_dependency_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "docs").mkdir()
            (root / "docs" / "standard.md").write_text("- 必须执行真实环境验收。\n", encoding="utf-8")
            nested = root / "frontend" / "console-web" / "node_modules" / "pkg"
            nested.mkdir(parents=True)
            (nested / "README.md").write_text("- must not leak dependency docs into project rules.\n", encoding="utf-8")

            result = run_script("build_rule_index.py", "--root", str(root), "--max-rules-per-pack", "20")

            self.assertEqual(0, result.returncode, result.stderr + result.stdout)
            registry = json.loads((root / "artifacts" / "rule-governance" / "rule-registry.json").read_text(encoding="utf-8"))
            sources = [rule["source"]["path"] for rule in registry["rules"]]
            self.assertNotIn("frontend/console-web/node_modules/pkg/README.md", sources)
            self.assertIn("docs/standard.md", sources)

    def test_stage_result_validator_blocks_succeeded_with_blocking_evidence(self) -> None:
        validator = ROOT / "engineering-assistant" / "scripts" / "validate_stage_run_result.py"
        invalid_result = {
            "run_id": "run-001",
            "skill_id": "code-review",
            "status": "succeeded",
            "language": "zh-CN",
            "document_metadata": {
                "document_number": "CRR-AIP-20260520-001",
                "document_status": "final",
                "retention_policy": "keep_until_run_end",
                "title": "Code Review",
                "owner": "code-review-agent",
                "source_artifacts": ["artifacts/code-development/implementation-summary.md"],
            },
            "artifacts": [],
            "quality_gates": [{"name": "Product completion", "result": "block_for_completion"}],
            "findings": [{"id": "BLOCK-001", "severity": "blocker", "summary": "业务流程未完成"}],
            "required_human_reviews": [],
            "required_information_requests": [],
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tmp:
            json.dump(invalid_result, tmp, ensure_ascii=False)
            tmp_path = Path(tmp.name)

        try:
            result = subprocess.run(
                ["python3", str(validator), str(tmp_path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        finally:
            tmp_path.unlink(missing_ok=True)

        self.assertNotEqual(0, result.returncode)
        output = result.stderr + result.stdout
        self.assertIn("succeeded 不允许包含 blocker/major finding", output)
        self.assertIn("succeeded 不允许包含阻断质量门禁", output)


if __name__ == "__main__":
    unittest.main()
