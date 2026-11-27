"""coverage_matrix.py — 칸 목록과 coverage-policy §2-1 표의 짝, 칸 펼치기."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

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


CATALOG_SRC = Path(__file__).resolve().parent.parent / "docs/architecture/failure-modes.md"


class StarterCatalogTest(unittest.TestCase):
    """스타터가 싣는 카탈로그가 스크립트가 읽는 형식이다 — 형식이 어긋나면 칸이 조용히 0개가 된다."""

    def test_catalog_parses_with_cells_and_sources(self):
        catalog = coverage_matrix.load_catalog(CATALOG_SRC)
        self.assertGreaterEqual(len(catalog), 8)
        for name, (title, cells) in catalog.items():
            with self.subTest(surface=name):
                self.assertTrue(title)
                self.assertTrue(cells, f"{name} 에 칸이 없다")
        text = CATALOG_SRC.read_text(encoding="utf-8")
        self.assertIn("TASK-004 RC-3", text)   # 출처 열 — verify_convergence 가 이것으로 반영된 후보를 거른다


class SurfaceCellsTest(ProjectTestCase):
    """PLAN surfaces → 카탈로그 칸. 카탈로그가 없는 프로젝트는 요구하지 않는다."""

    def setUp(self):
        super().setUp()
        self.design = {"flows": [{"id": "F1"}], "input_fields": [],
                       "input_fields_none_reason": "입력 없음"}
        self.save()

    def save(self):
        self.project.write_json(f"workflow_design/04_plan/PLAN_{TID}.json", {"design": self.design})

    def with_catalog(self):
        self.project.write("docs/architecture/failure-modes.md", CATALOG_SRC.read_text(encoding="utf-8"))

    def test_without_catalog_surfaces_are_not_required(self):
        out = self.project.run("coverage_matrix.py", "--task-id", TID, "--skeleton")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("fm:", out.stdout)

    def test_with_catalog_missing_surfaces_is_a_plan_problem(self):
        self.with_catalog()
        out = self.project.run("coverage_matrix.py", "--task-id", TID)
        self.assertEqual(out.returncode, 1)
        self.assertIn("design.surfaces 가 없다", out.stdout)

    def test_surfaces_expand_to_catalog_cells_per_place(self):
        self.with_catalog()
        self.design["surfaces"] = [
            {"id": "spa", "surface": "static_serving", "where": "/assets/**"},
            {"id": "api", "surface": "http_error_path", "where": "EchoController"},
        ]
        self.save()
        out = self.project.run("coverage_matrix.py", "--task-id", TID, "--skeleton")
        self.assertEqual(out.returncode, 0, out.stderr)
        catalog = coverage_matrix.load_catalog(CATALOG_SRC)
        expected = len(catalog["static_serving"][1]) + len(catalog["http_error_path"][1])
        self.assertEqual(out.stdout.count('"cell"'), expected)
        self.assertIn("fm:spa:static_serving.range_invalid", out.stdout)
        self.assertIn("fm:api:http_error_path.method_not_allowed", out.stdout)

    def test_unknown_surface_and_missing_where_are_problems(self):
        self.with_catalog()
        self.design["surfaces"] = [{"id": "x", "surface": "nope", "where": "a"},
                                   {"id": "y", "surface": "broad_catch"}]
        self.save()
        out = self.project.run("check_plan.py", "--task-id", TID)
        self.assertIn("카탈로그에 없는 노출면", out.stdout + out.stderr)
        self.assertIn("where", out.stdout + out.stderr)

    def test_empty_surfaces_need_a_reason(self):
        self.with_catalog()
        self.design["surfaces"] = []
        self.save()
        out = self.project.run("coverage_matrix.py", "--task-id", TID)
        self.assertIn("surfaces_none_reason", out.stdout)
        self.design["surfaces_none_reason"] = "설정 화면 문구만 바꾼다"
        self.save()
        self.project.write_json(f"workflow_design/05_scenario/SCENARIO_{TID}.json",
                                {"scenarios": [], "coverage_matrix": []})
        self.assertEqual(self.project.run("coverage_matrix.py", "--task-id", TID).returncode, 0)

    def test_surface_cells_are_judged_like_input_cells(self):
        self.with_catalog()
        self.design["surfaces"] = [{"id": "c", "surface": "concurrent_write", "where": "SeatService.hold"}]
        self.save()
        self.project.write_json(f"workflow_design/05_scenario/SCENARIO_{TID}.json", {
            "scenarios": [{"id": "SC-01"}],
            "coverage_matrix": [{"cell": "fm:c:concurrent_write.lost_update", "state": "covered", "by": ["SC-01"]}]})
        self.assertEqual(self.project.run("coverage_matrix.py", "--task-id", TID).returncode, 0)


if __name__ == "__main__":
    unittest.main()
