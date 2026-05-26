#!/usr/bin/env python3
"""Regression checks for flexible workflow composition and entry modes."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FlexibleWorkflowCompositionTests(unittest.TestCase):
    def load_workflow(self, workflow_id: str) -> dict:
        return json.loads((ROOT / "engineering-assistant" / "workflows" / f"{workflow_id}.yaml").read_text(encoding="utf-8"))

    def test_workflows_declare_supported_entry_modes(self) -> None:
        for workflow_id in ["full-feature-development", "design-only", "coding-only", "frontend-only"]:
            workflow = self.load_workflow(workflow_id)
            self.assertEqual(workflow["default_entry_mode"], "auto_flow")
            self.assertEqual(set(workflow["supported_entry_modes"]), {"auto_flow", "from_node", "single_node"})
            self.assertIn("start_node", workflow)
            self.assertIn("terminal_nodes", workflow)
            self.assertIn("composition_policy", workflow)
            self.assertIn("from_node", workflow["composition_policy"])
            self.assertIn("single_node", workflow["composition_policy"])
            self.assertIn("auto_flow", workflow["composition_policy"])

    def test_sequential_workflows_wire_next_nodes_and_dependencies(self) -> None:
        workflow = self.load_workflow("coding-only")
        nodes = workflow["nodes"]
        node_ids = [node["node_id"] for node in nodes]
        self.assertEqual(workflow["start_node"], node_ids[0])
        self.assertEqual(workflow["terminal_nodes"], [node_ids[-1]])

        for index, node in enumerate(nodes):
            expected_next = [node_ids[index + 1]] if index + 1 < len(nodes) else []
            expected_previous = [node_ids[index - 1]] if index > 0 else []
            self.assertEqual(node["next_nodes"], expected_next)
            self.assertEqual(node["depends_on"], expected_previous)
            self.assertEqual(set(node["entry_modes"]), {"auto_flow", "from_node", "single_node"})

    def test_workflow_orchestrator_contract_names_runtime_modes(self) -> None:
        contract = json.loads((ROOT / "skills" / "workflow-orchestrator" / "contract.yaml").read_text(encoding="utf-8"))
        self.assertIn("workflow_runtime_policy", contract)
        runtime_policy = contract["workflow_runtime_policy"]
        self.assertEqual(set(runtime_policy["supported_entry_modes"]), {"auto_flow", "from_node", "single_node"})
        self.assertIn("start_node", runtime_policy["from_node_required_fields"])
        self.assertIn("target_node", runtime_policy["single_node_required_fields"])

    def test_plugin_tree_receives_same_workflow_assets(self) -> None:
        source = self.load_workflow("full-feature-development")
        plugin = json.loads(
            (
                ROOT
                / "plugins"
                / "engineering-assistant"
                / "engineering-assistant"
                / "workflows"
                / "full-feature-development.yaml"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(source["supported_entry_modes"], plugin["supported_entry_modes"])
        self.assertEqual(source["nodes"][0]["next_nodes"], plugin["nodes"][0]["next_nodes"])


if __name__ == "__main__":
    unittest.main()
