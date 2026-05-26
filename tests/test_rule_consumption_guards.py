#!/usr/bin/env python3
"""Regression checks for task rule-pack consumption."""

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


class RuleConsumptionGuardTests(unittest.TestCase):
    def test_rule_pack_contains_source_traceability(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            docs.mkdir()
            (docs / "standard.md").write_text("- 必须引用 rule_id 才能通过代码评审。\n", encoding="utf-8")

            result = subprocess.run(
                ["python3", str(PLUGIN_SCRIPTS / "build_rule_index.py"), "--root", str(root), "--max-rules-per-pack", "20"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr + result.stdout)
            pack = json.loads((root / "artifacts" / "rule-governance" / "task-rule-packs" / "code-review.json").read_text(encoding="utf-8"))
            self.assertGreater(pack["rule_count"], 0)
            first = pack["rules"][0]
            self.assertIn("rule_id", first)
            self.assertIn("severity", first)
            self.assertIn("source", first)
            self.assertIn("line", first["source"])

    def test_validator_blocks_review_findings_without_rule_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pack = root / "artifacts" / "rule-governance" / "task-rule-packs" / "code-review.json"
            write_json(pack, {"task_type": "code-review", "rule_count": 1, "rules": [{"rule_id": "RG-001", "severity": "blocker"}]})
            report = root / "artifacts" / "code-review" / "review-comments.json"
            write_json(report, {"findings": [{"id": "F1", "severity": "major", "summary": "missing rule refs"}]})

            result = subprocess.run(
                [
                    "python3",
                    str(PLUGIN_SCRIPTS / "validate_rule_consumption.py"),
                    "--root",
                    str(root),
                    "--task-type",
                    "code-review",
                    "--evidence",
                    "artifacts/code-review/review-comments.json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(0, result.returncode)
            control_report = json.loads((root / "artifacts" / "_control" / "rule-consumption-report.json").read_text(encoding="utf-8"))
            self.assertEqual("block", control_report["status"])
            self.assertIn("missing rule_refs", control_report["findings"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
