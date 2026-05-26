#!/usr/bin/env python3
"""Regression checks for team detailed-design document rules."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_validator(skill_id: str, payload_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(ROOT / "skills" / skill_id / "scripts" / "validate_output.py"), str(payload_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def payload(skill_id: str, artifacts: list[dict[str, str]], status: str = "succeeded", document_status: str = "draft") -> dict:
    return {
        "run_id": "run-team-doc-001",
        "skill_id": skill_id,
        "status": status,
        "language": "zh-CN",
        "trace_id": "trace-team-doc-001",
        "document_metadata": {
            "document_number": "DDD-TEAM-20260526-001",
            "document_status": document_status,
            "retention_policy": "keep_until_run_end",
            "owner": "后端开发",
            "source_artifacts": [],
        },
        "artifacts": [
            {
                "name": item["name"],
                "path": item["path"],
                "artifact_type": item.get("artifact_type", "markdown"),
                "producer_skill": skill_id,
            }
            for item in artifacts
        ],
        "quality_gates": [],
        "findings": [],
        "required_human_reviews": [],
        "required_information_requests": [],
        "repair_summary": {"attempts": 0, "max_attempts": 0, "status": "not_needed"},
        "next_action": "complete",
    }


class TeamDocumentDesignRulesTest(unittest.TestCase):
    def test_detailed_design_contract_exposes_team_document_policy(self) -> None:
        contract = json.loads((ROOT / "skills" / "detailed-design" / "contract.yaml").read_text(encoding="utf-8"))
        policy = contract["team_document_policy"]

        self.assertIn("来源证据", policy["main_document"]["forbidden_headings"])
        self.assertIn("sequenceDiagram", policy["main_document"]["forbidden_mermaid"])
        self.assertIn("flowchart", policy["main_document"]["required_mermaid"])
        self.assertIn("classDiagram", json.dumps(policy, ensure_ascii=False))
        self.assertIn("database-design.md", policy["stage_result"]["must_register_specialty_artifacts"])
        self.assertIn("Redis 新 Key", policy["stage_result"]["waiting_for_human_review_when"])

        skill_md = (ROOT / "skills" / "detailed-design" / "SKILL.md").read_text(encoding="utf-8")
        for text in ["主文档不得包含独立章节", "sequenceDiagram", "流程设计说明", "classDiagram", "waiting_for_human_review"]:
            self.assertIn(text, skill_md)

    def test_team_templates_are_generated(self) -> None:
        expected = [
            ROOT / "skills" / "detailed-design" / "assets" / "detailed-design-template.md",
            ROOT / "skills" / "database-design" / "assets" / "database-oltp-template.md",
            ROOT / "skills" / "database-design" / "assets" / "database-olap-template.md",
            ROOT / "skills" / "redis-design" / "assets" / "redis-design-template.md",
            ROOT / "skills" / "mq-design" / "assets" / "mq-design-template.md",
        ]
        for path in expected:
            self.assertTrue(path.exists(), f"missing template: {path}")

        detailed_template = expected[0].read_text(encoding="utf-8")
        self.assertIn("关联专项设计文档", detailed_template)
        self.assertIn("flowchart TD", detailed_template)
        self.assertIn("classDiagram", detailed_template)
        self.assertNotIn("## 来源证据", detailed_template)
        self.assertNotIn("## 发布", detailed_template)

    def test_extra_team_eval_cases_are_generated_and_checked_by_runner(self) -> None:
        expected_cases = [
            "team_db_reference_only",
            "team_mq_template_reference_only",
            "team_redis_template_reference_only",
            "team_flowchart_not_sequence",
            "team_rules_under_flow",
            "team_ddd_requires_uml",
            "team_no_release_gray_sections",
        ]
        for case in expected_cases:
            path = ROOT / "skills" / "detailed-design" / "evals" / f"{case}.yaml"
            self.assertTrue(path.exists(), f"missing eval case: {case}")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(case, data["case_type"])
            self.assertIn("detailed-design.md", "\n".join(data["pass_criteria"]))

        runner = (ROOT / "engineering-assistant" / "scripts" / "run_skill_evals.py").read_text(encoding="utf-8")
        self.assertIn('glob("*.yaml")', runner)
        self.assertIn("StageRunResult.artifacts", runner)

    def test_detailed_design_validator_blocks_forbidden_sections_and_sequence_diagram(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            design = root / "detailed-design.md"
            design.write_text(
                """# 详细设计

## 来源证据

```mermaid
sequenceDiagram
    A->>B: 调用
```
""",
                encoding="utf-8",
            )
            result_payload = payload(
                "detailed-design",
                [
                    {"name": "detailed-design.md", "path": str(design)},
                    {"name": "database-design.md", "path": str(root / "database-design.md")},
                    {"name": "mq-design.md", "path": str(root / "mq-design.md")},
                    {"name": "redis-design.md", "path": str(root / "redis-design.md")},
                    {"name": "interface-contracts.yaml", "path": str(root / "interface-contracts.yaml"), "artifact_type": "yaml"},
                    {"name": "test-strategy.md", "path": str(root / "test-strategy.md")},
                ],
            )
            payload_path = root / "stage-run-result.json"
            payload_path.write_text(json.dumps(result_payload, ensure_ascii=False), encoding="utf-8")

            result = run_validator("detailed-design", payload_path)

        self.assertNotEqual(0, result.returncode)
        output = result.stdout + result.stderr
        self.assertIn("禁止标题", output)
        self.assertIn("sequenceDiagram", output)
        self.assertIn("必须包含 flowchart", output)

    def test_detailed_design_validator_blocks_missing_flow_notes_uml_and_human_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            design = root / "detailed-design.md"
            design.write_text(
                """# 详细设计

## 6. 流程图与流程设计

```mermaid
flowchart TD
    A["提交"] --> B["保存"]
```

本方案采用 DDD、ApplicationService、Repository、Handler Template 扩展点。
包含 DDL 和 Redis 新 Key。
""",
                encoding="utf-8",
            )
            result_payload = payload(
                "detailed-design",
                [
                    {"name": "detailed-design.md", "path": str(design)},
                    {"name": "database-design.md", "path": str(root / "database-design.md")},
                    {"name": "mq-design.md", "path": str(root / "mq-design.md")},
                    {"name": "redis-design.md", "path": str(root / "redis-design.md")},
                    {"name": "interface-contracts.yaml", "path": str(root / "interface-contracts.yaml"), "artifact_type": "yaml"},
                    {"name": "test-strategy.md", "path": str(root / "test-strategy.md")},
                ],
            )
            payload_path = root / "stage-run-result.json"
            payload_path.write_text(json.dumps(result_payload, ensure_ascii=False), encoding="utf-8")

            result = run_validator("detailed-design", payload_path)

        self.assertNotEqual(0, result.returncode)
        output = result.stdout + result.stderr
        self.assertIn("流程设计说明", output)
        self.assertIn("classDiagram", output)
        self.assertIn("waiting_for_human_review", output)

    def test_specialty_validators_block_template_and_policy_violations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            db_doc = root / "database-design.md"
            db_doc.write_text("UPDATE t_order SET status = 1;\nCREATE TABLE t_order_ext(id bigint);\n", encoding="utf-8")
            db_payload = root / "db-stage-run-result.json"
            db_payload.write_text(json.dumps(payload("database-design", [{"name": "database-design.md", "path": str(db_doc)}]), ensure_ascii=False), encoding="utf-8")
            db_result = run_validator("database-design", db_payload)
            self.assertNotEqual(0, db_result.returncode)
            self.assertIn("没有 WHERE", db_result.stdout + db_result.stderr)

            redis_doc = root / "redis-design.md"
            redis_doc.write_text("Redis 作为事实库。\nTTL：30\n", encoding="utf-8")
            redis_payload = root / "redis-stage-run-result.json"
            redis_payload.write_text(json.dumps(payload("redis-design", [{"name": "redis-design.md", "path": str(redis_doc)}]), ensure_ascii=False), encoding="utf-8")
            redis_result = run_validator("redis-design", redis_payload)
            self.assertNotEqual(0, redis_result.returncode)
            redis_output = redis_result.stdout + redis_result.stderr
            self.assertIn("事实库", redis_output)
            self.assertIn("TTL 必须带单位", redis_output)

            mq_doc = root / "mq-design.md"
            mq_doc.write_text("消息预估大小：28KB\n生产消息回放。\n", encoding="utf-8")
            mq_payload = root / "mq-stage-run-result.json"
            mq_payload.write_text(json.dumps(payload("mq-design", [{"name": "mq-design.md", "path": str(mq_doc)}]), ensure_ascii=False), encoding="utf-8")
            mq_result = run_validator("mq-design", mq_payload)
            self.assertNotEqual(0, mq_result.returncode)
            mq_output = mq_result.stdout + mq_result.stderr
            self.assertIn("生产者表缺少字段", mq_output)
            self.assertIn("超过 10KB", mq_output)


if __name__ == "__main__":
    unittest.main()
