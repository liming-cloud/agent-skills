#!/usr/bin/env python3
"""Regression checks for technology adoption enforcement."""

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


class TechnologyAdoptionGuardTests(unittest.TestCase):
    def test_compile_design_contract_emits_technology_adoption_contract(self) -> None:
        script = ROOT / "engineering-assistant" / "scripts" / "compile_design_contract.py"
        text = script.read_text(encoding="utf-8")
        self.assertIn("technology_adoption_contract", text)
        self.assertIn("mybatis-plus", text)
        self.assertIn("JDBC", text)

        schema = json.loads((ROOT / "engineering-assistant" / "schemas" / "implementation-contract.schema.json").read_text(encoding="utf-8"))
        self.assertIn("technology_adoption_contract", schema["required"])

    def test_validator_blocks_declared_mybatis_plus_with_only_jdbc_usage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            control = root / "artifacts" / "_control"
            write_json(
                control / "implementation-contract.json",
                {
                    "technology_adoption_contract": {
                        "persistence_framework": "mybatis-plus",
                        "required_indicators": ["BaseMapper", "@Mapper"],
                        "forbidden_indicators": ["DriverManager.getConnection", "JdbcTemplate"],
                        "minimum_required_indicators": 1,
                    }
                },
            )
            java_file = root / "backend" / "contexts" / "identity" / "JdbcUserRepository.java"
            java_file.parent.mkdir(parents=True)
            java_file.write_text(
                "class JdbcUserRepository { void c() { java.sql.DriverManager.getConnection(\"jdbc:h2:mem:test\"); } }\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                ["python3", str(PLUGIN_SCRIPTS / "validate_technology_adoption.py"), "--root", str(root)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(0, result.returncode)
            report = json.loads((control / "technology-adoption-report.json").read_text(encoding="utf-8"))
            self.assertEqual("block", report["status"])
            reasons = " ".join(item["reason"] for item in report["findings"])
            self.assertIn("forbidden technology indicator", reasons)
            self.assertIn("not enough required technology indicators", reasons)


if __name__ == "__main__":
    unittest.main()
