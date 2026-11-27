"""check_addenda.py — RETRY_FIX 의 추가 시나리오는 근거·새 테스트 파일·수정 전 커밋·HITL#3 승인을 갖춘다.

2a 를 다시 돌지 않는 대신 이 검사가 형식을 지킨다. 근거 문장이 맞는지는 사람이 HITL#3 에서 본다.
"""

from __future__ import annotations

from helpers import ProjectTestCase

TID = "TASK-001"
TEST = f"workflow_design/05_scenario/TEST_{TID}.json"
SCEN = f"workflow_design/05_scenario/SCENARIO_{TID}.json"
VERIFY = f"workflow_design/07_verify/VERIFY_{TID}.json"
OLD = "tests/test_echo.py"
NEW = "tests/test_echo_errors.py"


class AddendaTest(ProjectTestCase):
    def setUp(self):
        super().setUp()
        self.project.write(OLD, "def test_ok(): pass\n")
        self.project.write(NEW, "def test_415(): assert False\n")
        self.red = self.project.commit("test: 추가 시나리오 SC-03 실패 확인")
        self.project.write("app/echo.py", "# 고침\n")
        self.project.commit("fix: 415")
        self.scenarios = [{"id": "SC-01"}, {"id": "SC-02"},
                          {"id": "SC-03", "addendum": 1, "basis": "conventions.md C-ERROR — 오류는 {code, message}"}]
        self.add = {"round": 1, "scenarios": ["SC-03"], "test_files": [NEW], "red_commit": self.red,
                    "red_evidence": "1 failed — 500 != 415", "approved": False}
        self.save()

    def save(self, decision=None):
        self.project.write_json(SCEN, {"scenarios": self.scenarios})
        self.project.write_json(TEST, {"test_files": [OLD], "human_review": {"approved": True}, "addenda": [self.add]})
        if decision:
            self.project.write_json(VERIFY, {"status": "PASS", "human_review": {"decision": decision}})

    def check(self):
        return self.project.run_json("check_addenda.py", "--task-id", TID, "--json")

    def assertFlags(self, needle):
        self.save()
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertTrue(any(needle in p for p in out["problems"]), out["problems"])

    def test_well_formed_addendum_passes(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertEqual(out["stats"], {"addenda": 1, "scenarios": 1})

    def test_no_addenda_passes(self):
        self.project.write_json(TEST, {"test_files": [OLD]})
        self.project.write_json(SCEN, {"scenarios": self.scenarios[:2]})
        self.assertEqual(self.check()[0], 0)

    def test_scenario_needs_basis(self):
        self.scenarios[2]["basis"] = ""
        self.assertFlags("basis 가 없다")

    def test_scenario_must_exist_in_json(self):
        self.add["scenarios"] = ["SC-09"]
        self.assertFlags("SC-09 가 SCENARIO json 에 없다")

    def test_round_must_match(self):
        self.scenarios[2]["addendum"] = 2
        self.assertFlags("회차 1 와 다르다")

    def test_unclaimed_addendum_scenario_fails(self):
        self.scenarios.append({"id": "SC-04", "addendum": 1, "basis": "x"})
        self.assertFlags("SC-04: addendum 이 붙었는데")

    def test_approved_test_file_cannot_host_the_addendum(self):
        self.add["test_files"] = [OLD]
        self.assertFlags("승인된 테스트 파일")

    def test_test_must_be_committed_before_the_fix(self):
        self.add["red_commit"] = self.project.git("rev-parse", "HEAD~2").strip()   # 테스트 전 커밋
        self.assertFlags("테스트가 수정보다 먼저")

    def test_red_commit_and_evidence_required(self):
        self.add["red_commit"] = ""
        self.add["red_evidence"] = ""
        self.save()
        _, out = self.check()
        self.assertTrue(any("red_commit 이 없다" in p for p in out["problems"]))
        self.assertTrue(any("red_evidence" in p for p in out["problems"]))

    def test_approval_requires_addenda_marked_approved(self):
        self.save(decision="APPROVE")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertTrue(any("approved 가 true" in p for p in out["problems"]))
        self.add["approved"] = True
        self.save(decision="APPROVE")
        self.assertEqual(self.check()[0], 0)

    def test_unreadable_test_json_exits_2(self):
        self.project.path(TEST).unlink()
        self.assertEqual(self.project.run("check_addenda.py", "--task-id", TID).returncode, 2)
