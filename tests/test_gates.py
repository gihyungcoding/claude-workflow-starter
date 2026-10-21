"""EXIT GATE 류 스크립트 — validate_phase2a_gate, check_freshness, ship_preflight.

이 스크립트들의 존재 이유는 "에이전트의 자기신고를 믿지 않고 산출물만 본다" 이다.
그래서 테스트는 각 조건을 하나씩 깨뜨려 보고, 게이트가 실제로 닫히는지 확인한다.
"""

from __future__ import annotations

import json
import os
import sys
import unittest

from helpers import SCRIPTS, ProjectTestCase

TID = "TASK-001"


class Phase2aGateTest(ProjectTestCase):
    """validate_phase2a_gate.py — 정상 산출물에서 출발해 조건을 하나씩 깬다."""

    def setUp(self):
        super().setUp()
        p = self.project
        p.write_json(
            f"workflow_design/04_plan/PLAN_{TID}.json",
            {"acceptance_criteria": ["목록 조회", "잘못된 입력은 400"]},
        )
        self.scenario = {
            "scenarios": [
                {"id": "SC-01", "type": "happy", "covers": ["목록 조회"]},
                {"id": "SC-02", "type": "error", "covers": ["잘못된 입력은 400"]},
            ],
            "human_input": {"generate_red_trigger": True},
        }
        p.write_json(f"workflow_design/05_scenario/SCENARIO_{TID}.json", self.scenario)
        p.write(f"workflow_design/05_scenario/SCENARIO_{TID}.md", "# scenarios\n")
        p.write_json(
            f"workflow_design/05_scenario/validator/VALIDATION_{TID}.json",
            {"overall": {"pass": True, "fail_count": 0, "summary": "ok"}},
        )
        p.write(f"memory-bank/{TID}/checkpoints/phase2a/CP-2.2_canonical-scenarios.md", "---\nstatus: ACTIVE\n---\n")

    def gate(self, *args: str) -> int:
        return self.project.run("validate_phase2a_gate.py", "--task-id", TID, *args).returncode

    def rewrite_scenario(self, **changes) -> None:
        self.scenario.update(changes)
        self.project.write_json(f"workflow_design/05_scenario/SCENARIO_{TID}.json", self.scenario)

    def test_complete_artifacts_pass(self):
        self.assertEqual(self.gate(), 0)

    def test_missing_validation_file_fails(self):
        self.project.path(f"workflow_design/05_scenario/validator/VALIDATION_{TID}.json").unlink()
        self.assertEqual(self.gate(), 1)

    def test_validation_pass_false_fails(self):
        self.project.write_json(
            f"workflow_design/05_scenario/validator/VALIDATION_{TID}.json",
            {"overall": {"pass": False, "fail_count": 1, "summary": "V11"}},
        )
        self.assertEqual(self.gate(), 1)

    def test_validation_pass_must_be_boolean_true(self):
        # "true" 문자열은 통과가 아니다 — 자기신고성 값을 걸러낸다
        self.project.write_json(
            f"workflow_design/05_scenario/validator/VALIDATION_{TID}.json",
            {"overall": {"pass": "true", "fail_count": 0}},
        )
        self.assertEqual(self.gate(), 1)

    def test_missing_overall_fails(self):
        self.project.write_json(f"workflow_design/05_scenario/validator/VALIDATION_{TID}.json", {})
        self.assertEqual(self.gate(), 1)

    def test_hitl_trigger_false_fails(self):
        self.rewrite_scenario(human_input={"generate_red_trigger": False})
        self.assertEqual(self.gate(), 1)

    def test_hitl_trigger_must_be_boolean_true(self):
        self.rewrite_scenario(human_input={"generate_red_trigger": "true"})
        self.assertEqual(self.gate(), 1)

    def test_hitl_trigger_absent_fails(self):
        self.rewrite_scenario(human_input={})
        self.assertEqual(self.gate(), 1)

    def test_skip_hitl_ignores_only_the_hitl_condition(self):
        self.rewrite_scenario(human_input={"generate_red_trigger": False})
        self.assertEqual(self.gate("--skip-hitl"), 0)
        self.project.path(f"workflow_design/05_scenario/validator/VALIDATION_{TID}.json").unlink()
        self.assertEqual(self.gate("--skip-hitl"), 1, "--skip-hitl 이 독립검증 조건까지 풀면 안 된다")

    def test_uncovered_acceptance_criterion_fails(self):
        self.rewrite_scenario(
            scenarios=[
                {"id": "SC-01", "type": "happy", "covers": ["목록 조회"]},
                {"id": "SC-02", "type": "error", "covers": ["다른 기준"]},
            ]
        )
        out = self.project.run("validate_phase2a_gate.py", "--task-id", TID)
        self.assertEqual(out.returncode, 1)
        self.assertIn("잘못된 입력은 400", out.stdout)

    def test_plan_without_criteria_fails_instead_of_vacuously_passing(self):
        self.project.write_json(f"workflow_design/04_plan/PLAN_{TID}.json", {})
        self.assertEqual(self.gate(), 1)

    def test_no_error_scenario_fails(self):
        self.rewrite_scenario(
            scenarios=[
                {"id": "SC-01", "type": "happy", "covers": ["목록 조회", "잘못된 입력은 400"]},
                {"id": "SC-02", "type": "happy", "covers": []},
            ]
        )
        self.assertEqual(self.gate(), 1)

    def test_single_scenario_fails(self):
        self.rewrite_scenario(
            scenarios=[{"id": "SC-01", "type": "happy", "covers": ["목록 조회", "잘못된 입력은 400"]}]
        )
        self.assertEqual(self.gate(), 1)

    def test_missing_checkpoint_fails(self):
        self.project.path(f"memory-bank/{TID}/checkpoints/phase2a/CP-2.2_canonical-scenarios.md").unlink()
        self.assertEqual(self.gate(), 1)

    def test_missing_scenario_md_fails(self):
        self.project.path(f"workflow_design/05_scenario/SCENARIO_{TID}.md").unlink()
        self.assertEqual(self.gate(), 1)

    def test_invalid_task_id_exits_2(self):
        out = self.project.run("validate_phase2a_gate.py", "--task-id", "TASK-task-001")
        self.assertEqual(out.returncode, 2)


class FreshnessTest(ProjectTestCase):
    """check_freshness.py — 승인한 코드가 그대로인가."""

    def approve(self) -> str:
        """소스를 커밋하고, 그 커밋을 verified_commit 으로 기록한다."""
        p = self.project
        p.write("src/app.py", "x = 1\n")
        sha = p.commit("feat: app")
        p.write_json(
            f"workflow_design/07_verify/VERIFY_{TID}.json",
            {"human_review": {"verified_commit": sha}},
        )
        p.commit("chore(workflow): verify")
        return sha

    def fresh(self) -> tuple[int, dict]:
        return self.project.run_json("check_freshness.py", "--task-id", TID, "--json")

    def test_unchanged_code_is_fresh(self):
        self.approve()
        code, data = self.fresh()
        self.assertEqual((code, data["status"]), (0, "fresh"))

    def test_source_change_after_approval_is_stale(self):
        self.approve()
        self.project.write("src/app.py", "x = 2\n")
        self.project.commit("fix: sneaky change")
        code, data = self.fresh()
        self.assertEqual((code, data["status"]), (1, "stale"))
        self.assertEqual(data["changed_source"], ["src/app.py"])

    def test_workflow_artifacts_after_approval_do_not_make_it_stale(self):
        self.approve()
        self.project.write("memory-bank/TASK-001/activeContext.md", "x\n")
        self.project.write("workflow_design/08_reflect/REFLECT_TASK-001.json", "{}\n")
        self.project.commit("chore: reflect")
        code, data = self.fresh()
        self.assertEqual((code, data["status"]), (0, "fresh"))

    def test_missing_verify_artifact_is_undeterminable_not_fresh(self):
        code, data = self.fresh()
        self.assertEqual(code, 2)
        self.assertNotEqual(data["status"], "fresh")

    def test_missing_verified_commit_is_undeterminable_not_fresh(self):
        self.project.write_json(f"workflow_design/07_verify/VERIFY_{TID}.json", {"human_review": {}})
        self.project.commit()
        code, data = self.fresh()
        self.assertEqual(code, 2)
        self.assertNotEqual(data["status"], "fresh")

    def test_unknown_verified_commit_is_undeterminable_not_fresh(self):
        self.project.write_json(
            f"workflow_design/07_verify/VERIFY_{TID}.json",
            {"human_review": {"verified_commit": "0" * 40}},
        )
        self.project.commit()
        code, data = self.fresh()
        self.assertEqual(code, 2)
        self.assertNotEqual(data["status"], "fresh")


class ShipPreflightTest(ProjectTestCase):
    """ship_preflight.py 의 개별 검사. CWD 를 임시 저장소로 옮겨 함수를 직접 부른다."""

    def setUp(self):
        super().setUp()
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(sys.path.remove, str(SCRIPTS))
        previous = os.getcwd()
        os.chdir(self.project.root)
        self.addCleanup(os.chdir, previous)
        import ship_preflight

        self.sp = ship_preflight

    def reflect(self, approved: bool) -> None:
        self.project.write(
            f"memory-bank/{TID}/activeContext.md",
            f"---\ntask_id: {TID}\nphase: \"5\"\nstatus: ACTIVE\n---\n",
        )
        self.project.write_json(
            f"workflow_design/08_reflect/REFLECT_{TID}.json",
            {"completion_report": {"approved_by_human": approved}},
        )

    def test_phase5_requires_human_approval(self):
        self.reflect(approved=False)
        self.assertFalse(self.sp.check_phase_complete(TID).ok)

    def test_phase5_approved_passes(self):
        self.reflect(approved=True)
        self.assertTrue(self.sp.check_phase_complete(TID).ok)

    def test_phase5_approval_must_be_boolean_true(self):
        self.reflect(approved=True)
        self.project.write_json(
            f"workflow_design/08_reflect/REFLECT_{TID}.json",
            {"completion_report": {"approved_by_human": "true"}},
        )
        self.assertFalse(self.sp.check_phase_complete(TID).ok)

    def test_blocked_task_cannot_ship_even_if_reflect_approved(self):
        self.reflect(approved=True)
        self.project.write(
            f"memory-bank/{TID}/activeContext.md",
            f"---\ntask_id: {TID}\nphase: \"5\"\nstatus: BLOCKED\nblocked_reason: 선행 대기\n---\n",
        )
        self.assertFalse(self.sp.check_phase_complete(TID).ok)

    def test_task_without_memory_bank_cannot_ship(self):
        self.assertFalse(self.sp.check_phase_complete(TID).ok)

    def test_dirty_worktree_fails(self):
        self.project.write("src/wip.py", "x\n")
        self.assertFalse(self.sp.check_worktree().ok)

    def test_clean_worktree_passes(self):
        self.assertTrue(self.sp.check_worktree().ok)

    def test_working_on_base_branch_fails(self):
        self.project.git("checkout", "-q", "-b", "develop")
        self.assertFalse(self.sp.check_branch(TID).ok)

    def test_feature_branch_passes(self):
        self.project.git("checkout", "-q", "-b", "develop")
        self.project.git("checkout", "-q", "-b", "feature/task-001-x")
        self.assertTrue(self.sp.check_branch(TID).ok)

    def test_architecture_violation_blocks_ship(self):
        self.project.write("src/api/a.py", "import repo\n")
        self.project.write(
            "docs/architecture/constraints.yaml",
            "version: 1\n\nconstraints:\n"
            "  - id: ARCH-001\n    rule: r\n    severity: error\n    detect:\n"
            '      type: forbidden_import\n      paths: ["src/api/**/*.py"]\n      pattern: "^import repo"\n',
        )
        check = self.sp.check_architecture()
        self.assertFalse(check.ok)

    def test_architecture_with_no_scanned_files_must_not_look_like_a_clean_pass(self):
        # glob 이 어긋나 아무것도 검사하지 못했다. ship 게이트가 이것을 "통과"로 보고하면
        # check_architecture.py 가 애써 구분한 no_target 이 마지막 관문에서 사라진다.
        self.project.write(
            "docs/architecture/constraints.yaml",
            "version: 1\n\nconstraints:\n"
            "  - id: ARCH-001\n    rule: r\n    severity: error\n    detect:\n"
            '      type: forbidden_import\n      paths: ["wrong/**/*.py"]\n      pattern: "x"\n',
        )
        check = self.sp.check_architecture()
        self.assertIn("검사되지 않음", check.detail)
        self.assertIn("ARCH-001", check.detail)
        self.assertNotIn("모두 통과", check.detail)

    def test_architecture_clean_pass_reports_how_many_files_were_scanned(self):
        self.project.write("src/api/a.py", "import service\n")
        self.project.write(
            "docs/architecture/constraints.yaml",
            "version: 1\n\nconstraints:\n"
            "  - id: ARCH-001\n    rule: r\n    severity: error\n    detect:\n"
            '      type: forbidden_import\n      paths: ["src/api/**/*.py"]\n      pattern: "^import repo"\n',
        )
        check = self.sp.check_architecture()
        self.assertTrue(check.ok)
        self.assertIn("파일 1개 검사", check.detail)

    def test_architecture_without_constraints_is_skipped(self):
        check = self.sp.check_architecture()
        self.assertTrue(check.ok and check.skipped)


if __name__ == "__main__":
    unittest.main()
