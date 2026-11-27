"""verify_convergence.py — Phase 4 라운드·later 를 세고, 카탈로그에 아직 없는 후보를 모은다."""

from __future__ import annotations

from helpers import ProjectTestCase


def verify(status, history=(), variants=(), human_review=None):
    return {"status": status, "history": list(history), "human_review": human_review,
            "root_causes": [{"id": "RC-1", "summary": "넓은 catch", "found_in_round": 1, "variants": list(variants)}]}


class ConvergenceTest(ProjectTestCase):
    def setUp(self):
        super().setUp()
        hr = {"decision": "RETRY_SCENARIO"}
        self.project.write_json("workflow_design/07_verify/VERIFY_TASK-001.json", verify(
            "FAIL", [{"round": 1, "status": "FAIL", "human_review": {"decision": "x"}},
                     {"round": 2, "status": "FAIL", "human_review": hr}],
            [{"case": "405", "origin": "found", "probe": "reproduced"},
             {"case": "Range 416", "origin": "later", "probe": "reproduced"},
             {"case": "Tomcat 400", "origin": "later", "probe": "reproduced", "deferred_to": "TASK-002"}],
            human_review=hr))   # history 의 마지막이 지금 판정이다 — 두 번 세지 않는다
        self.project.write_json("workflow_design/07_verify/VERIFY_TASK-002.json", verify("PASS"))

    def test_rounds_from_history_do_not_double_count_the_current_verdict(self):
        code, out = self.project.run_json("verify_convergence.py", "--json")
        self.assertEqual(code, 0)
        t1 = out["tasks"][0]
        self.assertEqual((t1["rounds"], t1["fail_rounds"], t1["later"], t1["deferred"]), (2, 2, 2, 1))
        self.assertEqual(out["tasks"][1]["rounds"], 1)

    def test_candidates_are_later_or_deferred_and_skip_what_the_catalog_cites(self):
        _, out = self.project.run_json("verify_convergence.py", "--json")
        self.assertEqual({c["case"] for c in out["candidates"]}, {"Range 416", "Tomcat 400"})
        self.project.write("docs/architecture/failure-modes.md",
                           "## `static_serving` — 정적\n\n| 칸 | 무엇 | 출처 |\n|---|---|---|\n"
                           "| `range_invalid` | 416 | TASK-001 RC-1 |\n")
        _, out = self.project.run_json("verify_convergence.py", "--json")
        self.assertEqual(out["candidates"], [])
