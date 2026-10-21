"""check_plan.py — PLAN 이 적은 경로가 실제로 있는가.

조사를 서브에이전트에 맡기면 결과를 요약으로 받는다. 지어낸 경로를 잡는 것이 이 검사의
존재 이유이고, 과거 PLAN 이 쓰던 표기를 오탐하지 않는 것이 함께 지켜야 할 조건이다.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from helpers import SCRIPTS, ProjectTestCase

STARTER_ROOT = Path(__file__).resolve().parent.parent

TID = "TASK-001"
PLAN = f"workflow_design/04_plan/PLAN_{TID}.json"
CP = f"memory-bank/{TID}/checkpoints/phase1/CP-1.3_context-plan.md"


class CheckPlanTest(ProjectTestCase):
    def setUp(self):
        super().setUp()
        for rel in ("src/api/search.py", "src/auth/decorators.py", "tests/api/test_search.py"):
            self.project.write(rel, "x\n")
        self.project.write(CP, "---\nstatus: ACTIVE\n---\n")

    def plan(self, targets=None, reusable=None, existing_tests=None, **over) -> None:
        data = {
            "task_id": TID,
            "route": "Backend",
            "design": {"inputs": [{"name": "q"}], "outputs": [{"name": "r"}], "flows": [{"id": "F1"}]},
            "codebase_analysis": {
                "target_files": targets if targets is not None else [
                    {"path": "src/api/search.py", "change": "필터 추가"},
                    {"path": "src/api/new_handler.py", "change": "핸들러", "new": True},
                ],
                "reusable": reusable if reusable is not None else [
                    {"path": "src/auth/decorators.py", "symbol": "require_role"}],
                "existing_tests": existing_tests if existing_tests is not None else ["tests/api/test_search.py"],
                "unresolved": [],
            },
        }
        data.update(over)
        self.project.write_json(PLAN, data)

    def run_check(self, *args):
        return self.project.run("check_plan.py", "--task-id", TID, *args)

    def assertOk(self, out=None):
        out = out or self.run_check()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        return out

    def assertViolation(self, *needles: str):
        out = self.run_check()
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        for n in needles:
            self.assertIn(n, out.stdout)
        return out

    # --- 정상 ---

    def test_existing_and_explicitly_new_files_pass(self):
        self.plan()
        out = self.assertOk()
        self.assertIn("기존 1 · 신규 1", out.stdout)

    # --- 지어낸 경로를 잡는다 ---

    def test_missing_file_not_marked_new_is_a_violation(self):
        self.plan(targets=[{"path": "src/api/imaginary.py", "change": "수정"}])
        self.assertViolation("존재하지 않는다", "imaginary.py", '"new": true')

    def test_missing_reusable_is_a_violation(self):
        self.plan(reusable=[{"path": "src/util/ghost.py", "symbol": "helper"}])
        self.assertViolation("reusable[0]", "ghost.py")

    def test_missing_existing_test_is_a_violation(self):
        self.plan(existing_tests=["tests/api/test_ghost.py"])
        self.assertViolation("existing_tests[0]")

    def test_new_file_that_already_exists_is_a_violation(self):
        self.plan(targets=[{"path": "src/api/search.py", "change": "x", "new": True}])
        self.assertViolation("이미 있다")

    def test_new_flag_must_be_boolean(self):
        self.plan(targets=[{"path": "src/api/x.py", "change": "x", "new": "true"}])
        self.assertViolation("true/false")

    def test_empty_target_files_is_a_violation(self):
        self.plan(targets=[])
        self.assertViolation("target_files 가 비어 있다")

    # --- 경로 형식 ---

    def test_several_paths_in_one_entry_is_a_violation(self):
        # 실제 사례 (TASK-008): 두 번째 파일에는 디렉터리도 없어 존재를 확인할 수 없다
        self.plan(reusable=[{"path": "src/auth/decorators.py, helpers.py"}])
        self.assertViolation("여럿")

    def test_glob_absolute_and_parent_paths_are_violations(self):
        for bad in ("src/**/*.py", "/etc/hosts", "../outside.py", ""):
            with self.subTest(path=bad):
                self.plan(targets=[{"path": bad, "change": "x"}])
                self.assertEqual(self.run_check().returncode, 1)

    def test_new_flag_does_not_excuse_a_non_concrete_path(self):
        # new: true 면 존재 검사를 건너뛴다 — 그때는 형식 검사가 유일한 방어선이다
        for bad, needle in (("src/**/*.py", "glob"), ("/tmp/x.py", "상대경로"), ("../x.py", "상대경로")):
            with self.subTest(path=bad):
                self.plan(targets=[{"path": bad, "change": "x", "new": True}])
                self.assertViolation(needle)

    def test_line_and_symbol_suffixes_are_stripped(self):
        self.plan(reusable=[{"path": "src/auth/decorators.py:12"}, {"path": "src/auth/decorators.py#require_role"}])
        self.assertOk()

    # --- 과거 PLAN 의 표기를 오탐하지 않는다 (실제 사례에서 나온 회귀 테스트) ---

    def test_commentary_after_the_path_is_tolerated(self):
        # TASK-001, TASK-007: 경로 뒤에 '— 설명', '(23개 시나리오)' 를 붙였다
        self.plan(existing_tests=["tests/api/test_search.py — 패키지 컨벤션 참고용",
                                  "tests/api/test_search.py (23개 시나리오 — sc01~sc24)"])
        self.assertOk()

    def test_new_file_written_only_in_prose_is_accepted_with_a_note(self):
        self.plan(targets=[{"path": "src/api/brand_new.py", "change": "신규 — 검색 핸들러"}])
        out = self.assertOk()
        self.assertIn("문장의 '신규'", out.stdout)

    def test_prose_never_turns_an_existing_file_into_a_violation(self):
        # TASK-003·004·005·006 오탐: 기존 파일의 change 에 'createTheme()', '생성', '/new' 가 들어 있었다
        for change in ("const theme = createTheme() → import theme",
                       "좌석 생성·시각순서 검증 추가",
                       "라우트 추가: /performances/new → RegisterPage"):
            with self.subTest(change=change):
                self.plan(targets=[{"path": "src/api/search.py", "change": change}])
                # 종료 코드만이 아니라 분류도 본다 — 있는 파일을 '신규' 로 세면 안 된다
                self.assertIn("기존 1 · 신규 0", self.assertOk().stdout)

    def test_missing_file_without_new_wording_is_still_a_violation(self):
        self.plan(targets=[{"path": "src/api/ghost.py", "change": "검증 추가"}])
        self.assertViolation("존재하지 않는다")

    def test_explicit_new_false_is_not_excused_by_prose(self):
        self.plan(targets=[{"path": "src/api/ghost.py", "change": "신규", "new": False}])
        self.assertViolation("존재하지 않는다")

    # --- 나머지 EXIT GATE 항목 ---

    def test_empty_design_sections_are_violations(self):
        self.plan(design={"inputs": [], "outputs": [{"n": 1}], "flows": []})
        self.assertViolation("design.inputs", "design.flows")

    def test_route_must_be_known(self):
        self.plan(route="Fullstack")
        self.assertViolation("route")

    def test_architecture_refs_required_only_when_architecture_doc_exists(self):
        self.plan()
        self.assertOk()
        self.project.write("docs/architecture/architecture.md", "# arch\n")
        self.assertViolation("architecture_refs")
        self.plan(architecture_refs={"layer": "Service"})
        self.assertOk()

    def test_missing_checkpoint_is_a_violation(self):
        self.plan()
        self.project.path(CP).unlink()
        self.assertViolation("CP-1.3")

    # --- 기록 ---

    def test_exploration_method_is_reported(self):
        self.plan()
        self.assertIn("조사 기록 없음", self.assertOk().stdout)
        self.plan(codebase_analysis={
            "target_files": [{"path": "src/api/search.py", "change": "x"}],
            "exploration": {"method": "explore"}})
        code, data = self.project.run_json("check_plan.py", "--task-id", TID, "--json")
        self.assertEqual((code, data["stats"]["exploration"]), (0, "explore"))

    # --- 인자 ---

    def test_missing_plan_exits_2(self):
        self.assertEqual(self.run_check().returncode, 2)

    def test_malformed_plan_exits_2(self):
        self.project.write(PLAN, "{broken")
        self.assertEqual(self.run_check().returncode, 2)

    def test_invalid_task_id_exits_2(self):
        self.assertEqual(self.project.run("check_plan.py", "--task-id", "TASK-1").returncode, 2)


class PlanDocsTest(unittest.TestCase):
    """문서가 가리키는 검사와 필드가 실제와 맞는다."""

    def read(self, rel: str) -> str:
        return (STARTER_ROOT / rel).read_text(encoding="utf-8")

    def test_exit_gate_names_the_script_that_exists(self):
        self.assertIn("check_plan.py", self.read(".claude/skills/wf-plan/SKILL.md"))
        self.assertTrue((SCRIPTS / "check_plan.py").is_file())

    def test_the_old_impossible_rule_is_gone(self):
        # 새 파일이 58% 인데 '모든 경로가 실재' 를 요구하던 문구
        self.assertNotIn("모든 경로가 **실재**", self.read(".claude/skills/wf-plan/SKILL.md"))

    def test_skill_points_at_the_trial_doc_that_exists(self):
        self.assertIn("references/explore-trial.md", self.read(".claude/skills/wf-plan/SKILL.md"))
        self.assertTrue((STARTER_ROOT / ".claude/skills/wf-plan/references/explore-trial.md").is_file())

    def test_trial_doc_records_the_fields_the_script_reports(self):
        text = self.read(".claude/skills/wf-plan/references/explore-trial.md")
        for token in ('"method"', '"calls"', '"main_reads"', "explore", "inline", "check_plan.py", '"new": true'):
            self.assertIn(token, text)

    def test_explore_prompt_asks_for_the_format_the_checker_requires(self):
        # 검사기는 한 항목에 경로 하나를 요구한다 — 템플릿이 쉼표 묶음을 금지해야 한다
        text = self.read(".claude/skills/wf-plan/references/explore-trial.md")
        self.assertIn("쉼표로 묶지 않는다", text)
        self.assertIn("저장소 기준 상대경로", text)


if __name__ == "__main__":
    unittest.main()
