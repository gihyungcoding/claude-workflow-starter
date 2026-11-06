"""coverage_matrix.py — 칸 목록과 coverage-policy §2-1 표의 짝, 칸 펼치기."""

from __future__ import annotations

import subprocess
import sys
import unittest

from helpers import SCRIPTS, ProjectTestCase

TID = "TASK-001"


class PolicyParityTest(unittest.TestCase):
    """표에만 있는 경계는 아무도 세지 않는다 — KINDS 와 표가 같은 이름을 가져야 한다."""

    def test_policy_table_matches_kinds(self):
        out = subprocess.run([sys.executable, str(SCRIPTS / "coverage_matrix.py"), "--check-policy"],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)


class ExpandTest(ProjectTestCase):
    def setUp(self):
        super().setUp()
        self.project.write_json(f"workflow_design/04_plan/PLAN_{TID}.json", {"design": {
            "flows": [{"id": "F1"}, {"id": "F2"}],
            "input_fields": [{"field": "email", "flows": ["F1", "F2"], "kinds": ["required", "string"]}],
        }})

    def test_cells_are_expanded_per_flow(self):
        out = self.project.run("coverage_matrix.py", "--task-id", TID, "--skeleton")
        self.assertEqual(out.returncode, 0, out.stderr)
        # required 2칸 + string 3칸, 흐름 2개
        self.assertEqual(out.stdout.count('"cell"'), 10)
        self.assertIn("email@F2:string.max+1", out.stdout)

    def test_without_scenario_every_cell_is_missing(self):
        out = self.project.run("coverage_matrix.py", "--task-id", TID)
        self.assertEqual(out.returncode, 1)
        self.assertIn("빠짐 10", out.stdout)


if __name__ == "__main__":
    unittest.main()
