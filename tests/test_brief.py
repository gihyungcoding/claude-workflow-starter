"""요청 계획(BRIEF) — 게이트·후속 작업·재계획 영향·이벤트 기록.

계획 단계는 대화로 진행되고 "다 정했다"는 판단을 에이전트가 내린다. 이 스크립트들이 그
판단을 파일로 대신하므로, 거짓 통과(미결 결정이 남았는데 확정 가능)와 거짓 차단(정상 계획을
막음)을 둘 다 확인한다.
"""

from __future__ import annotations

import copy
import json
import unittest

from helpers import ProjectTestCase

REQ = "REQ-001"
BRIEF = f"workflow_design/01_brief/BRIEF_{REQ}.json"
MOCK = f"workflow_design/01_brief/mockup/{REQ}"
CHECK_PATHS = "hooks/check_artifact_paths.py"


def brief(**over) -> dict:
    data = {
        "id": REQ,
        "status": "refining",
        "prompt": "매장 검색에 권한 필터를 넣어 줘",
        "posture": "hold",
        "goal": "담당하지 않는 매장은 검색되지 않는다",
        "acceptance_criteria": [
            {"id": "AC-1", "text": "담당 매장만 나온다", "kind": "happy", "ui": False},
            {"id": "AC-2", "text": "직접 조회는 403", "kind": "error", "ui": False},
        ],
        "out_of_scope": ["검색 랭킹"],
        "decisions": [
            {"id": "D1", "class": "mechanical", "status": "approved", "question": "계층", "answer": "Service"},
            {"id": "D2", "class": "user_challenge", "status": "approved", "question": "관리자도 막나", "answer": "관리자는 전체"},
        ],
        "completeness": [{"id": "C1", "text": "형제 엔드포인트 대칭", "in_radius": True,
                          "estimate_delta_h": 1, "status": "included"}],
        "scope": {"wru": True, "routes": ["Backend"], "product_change": False,
                  "architecture": {"change": False, "adr": []}, "design_tokens": False,
                  "ui": "none", "migration": False, "paths": ["src/api/store_search.py"]},
        "split": [{"key": "A", "title": "권한 필터", "route": "Backend", "estimate_h": 8,
                   "ac": ["AC-1", "AC-2"], "depends_on": []}],
    }
    data.update(over)
    return data


class BriefTestCase(ProjectTestCase):
    def setUp(self):
        super().setUp()
        for rel in ("docs/product/product.md", "docs/architecture/architecture.md"):
            self.project.write(rel, "# 완성된 문서\n")

    def save(self, data: dict) -> None:
        self.project.write_json(BRIEF, data)

    def gate(self, gate: str = "lock") -> tuple[int, dict]:
        return self.project.run_json("check_brief.py", "--req", REQ, "--gate", gate, "--json")

    def assertPasses(self, gate: str = "lock") -> dict:
        code, out = self.gate(gate)
        self.assertEqual(code, 0, out)
        return out

    def assertFailsWith(self, needle: str, gate: str = "lock") -> None:
        code, out = self.gate(gate)
        self.assertEqual(code, 1, out)
        self.assertTrue(any(needle in e for e in out["errors"]), f"{needle!r} 없음: {out['errors']}")


class CheckBriefLockTest(BriefTestCase):
    def test_complete_brief_passes_lock(self):
        self.save(brief())
        self.assertPasses()

    def test_unresolved_decision_blocks_lock(self):
        b = brief()
        b["decisions"].append({"id": "D3", "class": "user_challenge", "status": "unresolved", "question": "캐시?"})
        self.save(b)
        self.assertFailsWith("D3")

    def test_reopened_decision_blocks_lock(self):
        b = brief()
        b["decisions"][1]["status"] = "reopened"
        self.save(b)
        self.assertFailsWith("D2")

    def test_user_challenge_needs_the_humans_answer(self):
        b = brief()
        del b["decisions"][1]["answer"]
        self.save(b)
        self.assertFailsWith("answer")

    def test_error_acceptance_criterion_is_required(self):
        b = brief()
        b["acceptance_criteria"] = [b["acceptance_criteria"][0]]
        b["split"][0]["ac"] = ["AC-1"]
        self.save(b)
        self.assertFailsWith("오류(error)")

    def test_non_code_request_needs_no_error_case_or_split(self):
        b = brief(split=[], acceptance_criteria=[{"id": "AC-1", "text": "문서 갱신", "kind": "happy"}])
        b["scope"]["wru"] = False
        self.save(b)
        self.assertPasses()

    def test_uncovered_acceptance_criterion_fails(self):
        b = brief()
        b["split"][0]["ac"] = ["AC-1"]
        self.save(b)
        self.assertFailsWith("AC-2")

    def test_completeness_outside_radius_must_be_asked(self):
        b = brief()
        b["completeness"][0]["in_radius"] = False
        self.save(b)
        self.assertFailsWith("영향 범위 밖")

    def test_completeness_too_large_must_be_asked(self):
        b = brief()
        b["completeness"][0]["estimate_delta_h"] = 5
        self.save(b)
        self.assertFailsWith("5")

    def test_dropped_completeness_is_not_checked(self):
        b = brief()
        b["completeness"][0].update(in_radius=False, estimate_delta_h=9, status="dropped")
        self.save(b)
        self.assertPasses()

    def test_architecture_change_needs_an_adr(self):
        b = brief()
        b["scope"]["architecture"] = {"change": True, "adr": []}
        self.save(b)
        self.assertFailsWith("ADR")

    def test_estimate_outside_wru_is_a_warning_not_a_failure(self):
        b = brief()
        b["split"][0]["estimate_h"] = 24
        self.save(b)
        out = self.assertPasses()
        self.assertTrue(out["warnings"])

    def test_bad_req_id_is_an_argument_error(self):
        self.assertEqual(self.project.run("check_brief.py", "--req", "REQ-1").returncode, 2)

    def test_missing_brief_is_an_argument_error(self):
        self.assertEqual(self.project.run("check_brief.py", "--req", REQ).returncode, 2)


class CheckBriefMockupTest(BriefTestCase):
    def ui_brief(self, **mock) -> dict:
        b = brief()
        b["scope"].update(ui="mockup", routes=["Backend", "Frontend"])
        b["acceptance_criteria"][0]["ui"] = True
        b["mockup"] = {"status": "approved", "rev": 2, "coverage": {"AC-1": ["home", "d-home"]}, **mock}
        return b

    def screens(self) -> None:
        self.project.write_json(f"{MOCK}/screens.json", {
            "screens": [{"id": "home"}], "desktop": [{"id": "d-home", "merges": ["home"]}]})

    def test_approved_mockup_covering_ui_criteria_passes(self):
        self.screens()
        self.save(self.ui_brief())
        self.assertPasses()

    def test_unapproved_mockup_blocks_lock(self):
        self.screens()
        self.save(self.ui_brief(status="draft"))
        self.assertFailsWith("시안이 확정되지 않았다")

    def test_ui_criterion_without_screen_fails(self):
        self.screens()
        self.save(self.ui_brief(coverage={}))
        self.assertFailsWith("AC-1")

    def test_coverage_pointing_to_missing_screen_fails(self):
        self.screens()
        self.save(self.ui_brief(coverage={"AC-1": ["nowhere"]}))
        self.assertFailsWith("nowhere")

    def test_missing_mockup_evidence_fails(self):
        self.save(self.ui_brief())
        self.assertFailsWith("시안 증거가 없다")


class CheckBriefLockedAndDispatchTest(BriefTestCase):
    def locked(self, **over) -> dict:
        return brief(status="locked", draft_commit="abc1234",
                     human_review={"approved": True, "locked_commit": "def5678"}, **over)

    def test_locked_gate_requires_human_approval(self):
        self.save(brief())
        self.assertFailsWith("HITL#0", gate="locked")

    def test_locked_gate_requires_locked_commit(self):
        self.save(brief(human_review={"approved": True}))
        self.assertFailsWith("locked_commit", gate="locked")

    def test_locked_brief_passes_locked_gate(self):
        self.save(self.locked())
        self.assertPasses("locked")

    def test_dispatch_gate_requires_all_jobs_handled(self):
        self.save(self.locked(dispatch=[{"job": "tasks", "status": "pending"}], tasks=["TASK-001"]))
        self.assertFailsWith("tasks", gate="dispatch")

    def test_dispatch_gate_requires_tasks_to_point_back(self):
        self.project.write_json("workflow_design/02_tasks/tasks.json",
                                [{"id": "TASK-001", "source_refs": {"request_id": "REQ-999"}}])
        self.save(self.locked(dispatch=[{"job": "tasks", "status": "done"}], tasks=["TASK-001"]))
        self.assertFailsWith("request_id", gate="dispatch")

    def test_dispatch_gate_passes_when_linked(self):
        self.project.write_json("workflow_design/02_tasks/tasks.json",
                                [{"id": "TASK-001", "source_refs": {"request_id": REQ}}])
        self.save(self.locked(dispatch=[{"job": "tasks", "status": "done"}], tasks=["TASK-001"]))
        self.assertPasses("dispatch")


class RouteBriefTest(BriefTestCase):
    def jobs(self, data: dict, *args) -> tuple[int, dict]:
        self.save(data)
        return self.project.run_json("route_brief.py", "--req", REQ, "--json", *args)

    def names(self, out: dict) -> list[str]:
        return [j["job"] for j in out["jobs"]]

    def test_single_backend_task_goes_straight_to_tasks(self):
        _, out = self.jobs(brief())
        self.assertEqual(self.names(out), ["tasks", "start"])
        self.assertEqual(out["jobs"][-1]["ref"], "A")

    def test_scope_flags_add_jobs_in_order(self):
        b = brief()
        b["scope"].update(product_change=True, design_tokens=True, ui="mockup", routes=["Backend", "Frontend"],
                          architecture={"change": True, "adr": ["캐시 계층 배치"]})
        _, out = self.jobs(b)
        self.assertEqual(self.names(out),
                         ["product", "adr", "architecture", "design", "feature_doc", "tasks", "start"])

    def test_two_tasks_need_a_feature_doc(self):
        b = brief()
        b["split"].append({"key": "B", "title": "화면", "route": "Frontend", "estimate_h": 6,
                           "ac": ["AC-1"], "depends_on": ["A"]})
        _, out = self.jobs(b)
        self.assertIn("feature_doc", self.names(out))
        self.assertEqual(out["jobs"][-1]["ref"], "A")   # 선행이 없는 쪽부터

    def test_non_code_request_is_handled_directly(self):
        b = brief()
        b["scope"]["wru"] = False
        _, out = self.jobs(b)
        self.assertEqual(self.names(out), ["direct"])

    def test_missing_foundation_adds_init_first(self):
        self.project.write("docs/architecture/architecture.md", "TODO: 계층\n")
        _, out = self.jobs(brief())
        self.assertEqual(self.names(out)[0], "init")

    def test_paths_contradicting_flags_warn(self):
        b = brief()
        b["scope"]["paths"] = ["db/migration/V3__add.sql", "frontend/src/pages/Search.tsx"]
        _, out = self.jobs(b)
        self.assertEqual(len(out["warnings"]), 2)

    def test_write_refuses_unlocked_brief(self):
        self.save(brief())
        self.assertEqual(self.project.run("route_brief.py", "--req", REQ, "--write").returncode, 1)

    def test_write_keeps_finished_job_status(self):
        b = brief(status="locked", dispatch=[{"job": "tasks", "status": "done", "result": ["TASK-001"]}])
        code, _ = self.jobs(b, "--write")
        self.assertEqual(code, 0)
        saved = json.loads(self.project.path(BRIEF).read_text(encoding="utf-8"))
        by_job = {j["job"]: j for j in saved["dispatch"]}
        self.assertEqual(by_job["tasks"]["status"], "done")
        self.assertEqual(by_job["tasks"]["result"], ["TASK-001"])
        self.assertEqual(by_job["start"]["status"], "pending")


class PlanImpactTest(BriefTestCase):
    TID = "TASK-001"
    PLAN = "workflow_design/04_plan/PLAN_TASK-001.json"

    def plan(self) -> dict:
        return {"task_id": self.TID, "route": "Backend",
                "acceptance_criteria": ["담당 매장만"],
                "design": {"inputs": [{"name": "q"}], "outputs": [{"name": "r"}], "flows": [{"id": "F1"}]},
                "codebase_analysis": {"target_files": [{"path": "src/a.py"}], "existing_tests": [], "unresolved": []},
                "test_hints": {"framework": "pytest"}}

    def phase(self, phase: str) -> None:
        self.project.write(f"memory-bank/{self.TID}/activeContext.md", f"---\ntask_id: {self.TID}\nphase: \"{phase}\"\n---\n")

    def impact(self, old: dict, new: dict, *, req: bool = False) -> tuple[int, dict]:
        path = BRIEF if req else self.PLAN
        self.project.write_json(path, old)
        base = self.project.commit("chore: v1")
        self.project.write_json(path, new)
        who = ["--req", REQ] if req else ["--task-id", self.TID]
        return self.project.run_json("plan_impact.py", *who, "--from", base, "--json")

    def test_no_change(self):
        code, out = self.impact(self.plan(), self.plan())
        self.assertEqual((code, out["restart"], out["changes"]), (0, "none", []))

    def test_target_files_only_restart_at_green(self):
        self.phase("4")
        new = self.plan()
        new["codebase_analysis"]["target_files"].append({"path": "src/b.py"})
        code, out = self.impact(self.plan(), new)
        self.assertEqual(out["restart"], "3")
        self.assertTrue(out["rewind"])
        self.assertEqual(code, 1)

    def test_acceptance_change_restarts_scenarios(self):
        new = self.plan()
        new["acceptance_criteria"].append("관리자는 전체")
        _, out = self.impact(self.plan(), new)
        self.assertEqual((out["restart"], out["reject_type"]), ("2a", "RETRY_SCENARIO"))

    def test_route_change_restructures_the_task(self):
        new = self.plan()
        new["route"] = "Frontend"
        _, out = self.impact(self.plan(), new)
        self.assertEqual(out["restart"], "task")

    def test_change_after_current_phase_needs_no_rewind(self):
        self.phase("2a")
        new = self.plan()
        new["codebase_analysis"]["target_files"].append({"path": "src/b.py"})
        code, out = self.impact(self.plan(), new)
        self.assertEqual((code, out["rewind"]), (0, False))

    def test_earliest_restart_wins(self):
        new = self.plan()
        new["test_hints"] = {"framework": "unittest"}
        new["design"]["flows"].append({"id": "F2"})
        _, out = self.impact(self.plan(), new)
        self.assertEqual(out["restart"], "2a")

    def test_brief_scope_change_needs_dispatch(self):
        new = brief()
        new["scope"]["migration"] = True
        _, out = self.impact(brief(), new, req=True)
        self.assertEqual(out["restart"], "dispatch")

    def test_brief_progress_fields_are_ignored(self):
        new = brief(status="locked", human_review={"approved": True})
        _, out = self.impact(brief(), new, req=True)
        self.assertEqual(out["restart"], "none")

    def test_new_mockup_feedback_impact_decides(self):
        old = brief(mockup={"feedback": [{"rev": 1, "impact": "visual"}]})
        new = copy.deepcopy(old)
        new["mockup"]["feedback"].append({"rev": 2, "impact": "data"})
        _, out = self.impact(old, new, req=True)
        self.assertEqual(out["restart"], "dispatch")

    def test_unknown_ref_is_an_error(self):
        self.project.write_json(self.PLAN, self.plan())
        out = self.project.run("plan_impact.py", "--task-id", self.TID, "--from", "nope")
        self.assertEqual(out.returncode, 2)


class WfEventTest(BriefTestCase):
    def test_events_append_and_summarize(self):
        run = self.project.run
        for ev, data in (("question_asked", {}), ("question_answered", {}),
                         ("review_finding", {"role": "eng"}), ("finding_applied", {"role": "eng"}),
                         ("reopened", {"phase": "2a"})):
            self.assertEqual(run("wf_event.py", "--id", REQ, "--event", ev, "--data", json.dumps(data)).returncode, 0)
        code, s = self.project.run_json("wf_event.py", "--id", REQ, "--summary", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(s["events"], 5)
        self.assertEqual(s["question_wait_sec"]["n"], 1)
        self.assertEqual(s["review_by_role"]["eng"], {"findings": 1, "applied": 1, "rejected": 0})
        self.assertEqual(s["reopened_in"], ["2a"])

    def test_unknown_event_is_rejected(self):
        self.assertEqual(self.project.run("wf_event.py", "--id", REQ, "--event", "whatever").returncode, 2)

    def test_bad_id_is_rejected(self):
        self.assertEqual(self.project.run("wf_event.py", "--id", "task-1", "--event", "locked").returncode, 2)

    def test_written_file_obeys_path_rules(self):
        self.project.run("wf_event.py", "--id", REQ, "--event", "locked")
        rel = f"workflow_design/09_telemetry/{REQ}.jsonl"
        self.assertTrue(self.project.path(rel).is_file())
        self.assertEqual(self.project.run(CHECK_PATHS, rel).returncode, 0)

    def test_broken_line_does_not_break_summary(self):
        self.project.write(f"workflow_design/09_telemetry/{REQ}.jsonl", "{broken\n")
        self.project.run("wf_event.py", "--id", REQ, "--event", "locked")
        code, s = self.project.run_json("wf_event.py", "--id", REQ, "--summary", "--json")
        self.assertEqual((code, s["events"]), (0, 1))


class BriefPathRulesTest(ProjectTestCase):
    def code(self, rel: str) -> int:
        return self.project.run(CHECK_PATHS, rel).returncode

    def test_allowed(self):
        for rel in (BRIEF, f"{MOCK}/screens.json", f"{MOCK}/screens/desktop/d-home.html",
                    "workflow_design/09_telemetry/TASK-001.jsonl", "workflow_design/09_telemetry/REQ-002.jsonl"):
            with self.subTest(rel=rel):
                self.assertEqual(self.code(rel), 0)

    def test_denied(self):
        for rel in ("workflow_design/01_brief/BRIEF_TASK-001.json", "workflow_design/01_brief/BRIEF_REQ-1.json",
                    "workflow_design/01_brief/notes.md", "workflow_design/01_brief/mockup/feature-x/a.html",
                    "workflow_design/09_telemetry/events.jsonl", "workflow_design/09_telemetry/REQ-001.json"):
            with self.subTest(rel=rel):
                self.assertEqual(self.code(rel), 1)


class TaskRequestIdTest(ProjectTestCase):
    def test_malformed_request_id_is_an_error(self):
        task = {"id": "TASK-001", "title": "x", "description": "x", "primary_category": "Backend",
                "priority": "High", "depends_on": [], "status": "todo",
                "meta": {"estimate": {"unit": "hour", "value": 8}, "acceptance_criteria": ["a", "b"]},
                "source_refs": {"request_id": "req-1"}}
        self.project.write_json("workflow_design/02_tasks/tasks.json", [task])
        code, out = self.project.run_json("validate_tasks.py", "--json")
        self.assertEqual(code, 1, out)
        self.assertIn("request_id", json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
