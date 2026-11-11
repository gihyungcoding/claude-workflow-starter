"""coverage_matrix.py — 칸 목록과 coverage-policy §2-1 표의 짝, 칸 펼치기."""

from __future__ import annotations

import subprocess
import sys
import unittest

from helpers import SCRIPTS, ProjectTestCase

sys.path.insert(0, str(SCRIPTS))
import coverage_matrix  # noqa: E402

TID = "TASK-001"

#: 흐름 2개 × (required + string) 칸. 종류에 칸을 더하면 이 값이 따라 바뀐다 —
#: 숫자를 하드코딩하면 칸을 추가한 변경이 이 테스트를 조용히 깨뜨린다 (PR #10 이 그랬다).
FLOWS = 2
EXPECTED_CELLS = FLOWS * (
    len(coverage_matrix.KINDS["required"][1]) + len(coverage_matrix.KINDS["string"][1])
)


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
        self.assertEqual(out.stdout.count('"cell"'), EXPECTED_CELLS)
        self.assertIn("email@F2:string.max+1", out.stdout)
        # 종류가 새로 얻은 칸도 흐름마다 펼쳐진다
        self.assertIn("email@F2:string.unicode_blank", out.stdout)
        self.assertIn("email@F1:string.unicode_blank", out.stdout)

    def test_without_scenario_every_cell_is_missing(self):
        out = self.project.run("coverage_matrix.py", "--task-id", TID)
        self.assertEqual(out.returncode, 1)
        self.assertIn(f"빠짐 {EXPECTED_CELLS}", out.stdout)


if __name__ == "__main__":
    unittest.main()
