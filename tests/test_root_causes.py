"""check_root_causes.py — FAIL 은 뿌리와 변종을 남기고, 재현된 변종이 남은 채로는 통과하지 못한다.

기록의 *질*은 검사하지 못한다. 그래서 테스트는 형식을 채워도 통과하는 부분과
(그리고 그 한계를 숨기지 않고 세는 부분을) 함께 확인한다.
"""

from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from pathlib import Path

from helpers import SCRIPTS, ProjectTestCase

sys.path.insert(0, str(SCRIPTS))
import check_root_causes  # noqa: E402

STARTER_ROOT = Path(__file__).resolve().parent.parent

TID = "TASK-001"
VERIFY = f"workflow_design/07_verify/VERIFY_{TID}.json"

CASE_A = "소문자화로 길이가 늘어나는 이메일"
CASE_B = "name 에 NUL 문자"
CASE_C = "name 이 컬럼 길이를 넘는다"


def variant(case: str, origin: str = "found", probe: str = "reproduced", **extra) -> dict:
    return {"case": case, "origin": origin, "probe": probe, **extra}


def root_cause(rc_id: str = "RC-1", variants: list | None = None, **extra) -> dict:
    rc = {
        "id": rc_id,
        "summary": "DataIntegrityViolationException 을 전부 UNIQUE 위반으로 취급하는 catch",
        "found_in_round": 1,
        "variants": variants if variants is not None else [variant(CASE_A)],
    }
    rc.update(extra)
    return rc


class RootCausesTest(ProjectTestCase):
    def verify(self, status: str, root_causes=None, **extra) -> None:
        data = {"task_id": TID, "status": status, **extra}
        if root_causes is not None:
            data["root_causes"] = root_causes
        self.project.write_json(VERIFY, data)

    def check(self, *args: str):
        return self.project.run("check_root_causes.py", "--task-id", TID, *args)

    def assertOk(self, out=None) -> None:
        out = out or self.check()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def assertViolation(self, *needles: str, out=None) -> None:
        out = out or self.check()
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        for needle in needles:
            self.assertIn(needle, out.stdout)

    # --- FAIL ---

    def test_fail_with_root_cause_and_variants_is_ok(self):
        self.verify("FAIL", [root_cause(variants=[
            variant(CASE_A), variant(CASE_B, "predicted", "reproduced")])])
        self.assertOk()

    def test_fail_without_root_causes_is_a_violation(self):
        self.verify("FAIL")
        self.assertViolation("root_causes")

    def test_fail_with_empty_root_causes_is_a_violation(self):
        self.verify("FAIL", [])
        self.assertViolation("비어 있다")

    def test_unresolved_reproduced_variants_are_expected_while_failing(self):
        # 아직 고치기 전이다 — FAIL 이면 재현된 변종이 해소되지 않은 것이 정상이다
        self.verify("FAIL", [root_cause(variants=[variant(CASE_A), variant(CASE_B, "predicted")])])
        self.assertOk()

    # --- PASS / WARN ---

    def test_pass_without_any_record_is_ok_and_says_so(self):
        self.verify("PASS")
        out = self.check()
        self.assertOk(out)
        self.assertIn("기록 없음", out.stdout)
        # 기록이 없다는 것이지 결함이 없었다는 주장이 아니다 (필드가 생기기 전의 VERIFY 도 같다)
        self.assertIn("결함이 없었다는 뜻이 아니라", out.stdout)
        self.assertNotIn("결함을 찾지 않은", out.stdout)

    def test_pass_with_unresolved_reproduced_variant_is_blocked(self):
        for status in ("PASS", "WARN"):
            with self.subTest(status=status):
                self.verify(status, [root_cause(variants=[variant(CASE_A)])])
                self.assertViolation("해소되지 않았다", CASE_A)

    def test_pass_with_resolved_and_evidenced_variants_is_ok(self):
        self.verify("PASS", [root_cause(variants=[
            variant(CASE_A, resolved=True, evidence="AuthServiceTest.longEmail"),
            variant(CASE_B, "predicted", resolved=True, evidence="AuthServiceTest.nulName")])])
        self.assertOk()

    def test_resolved_without_evidence_is_a_violation(self):
        self.verify("PASS", [root_cause(variants=[variant(CASE_A, resolved=True)])])
        self.assertViolation("evidence")

    def test_resolved_with_blank_evidence_is_a_violation(self):
        self.verify("PASS", [root_cause(variants=[variant(CASE_A, resolved=True, evidence="  ")])])
        self.assertViolation("evidence")

    def test_resolved_must_be_boolean_not_a_string(self):
        self.verify("PASS", [root_cause(variants=[variant(CASE_A, resolved="true", evidence="t")])])
        self.assertViolation("resolved")

    def test_not_reproduced_variants_need_no_resolution(self):
        self.verify("PASS", [root_cause(variants=[variant(CASE_C, "predicted", "not_reproduced")])])
        self.assertOk()

    # --- 구조 ---

    def test_bad_root_cause_id_is_a_violation(self):
        self.verify("FAIL", [root_cause("rc1")])
        self.assertViolation("RC-숫자")

    def test_duplicate_root_cause_ids_are_a_violation(self):
        self.verify("FAIL", [root_cause("RC-1"), root_cause("RC-1")])
        self.assertViolation("중복")

    def test_blank_summary_is_a_violation(self):
        self.verify("FAIL", [root_cause(summary="  ")])
        self.assertViolation("summary")

    def test_found_in_round_must_be_a_positive_integer(self):
        for bad in (0, -1, "1", True, None):
            with self.subTest(bad=bad):
                self.verify("FAIL", [root_cause(found_in_round=bad)])
                self.assertViolation("found_in_round")

    def test_no_variants_requires_a_reason(self):
        self.verify("FAIL", [root_cause(variants=[])])
        self.assertViolation("no_variants_reason")

    def test_no_variants_with_a_reason_is_ok(self):
        self.verify("FAIL", [root_cause(variants=[], no_variants_reason="입력 경로가 이 하나뿐임을 Grep 으로 확인")])
        self.assertOk()

    def test_blank_no_variants_reason_does_not_count(self):
        self.verify("FAIL", [root_cause(variants=[], no_variants_reason="   ")])
        self.assertViolation("no_variants_reason")

    def test_unknown_origin_and_probe_are_violations(self):
        self.verify("FAIL", [root_cause(variants=[variant(CASE_A, origin="guessed")])])
        self.assertViolation("origin")
        self.verify("FAIL", [root_cause(variants=[variant(CASE_A, probe="skipped")])])
        self.assertViolation("probe")

    def test_not_probed_requires_a_reason(self):
        self.verify("FAIL", [root_cause(variants=[variant(CASE_A, probe="not_probed")])])
        self.assertViolation("reason")
        self.verify("FAIL", [root_cause(variants=[variant(CASE_A, probe="not_probed", reason="Docker 꺼짐")])])
        self.assertOk()

    def test_blank_or_duplicate_case_is_a_violation(self):
        self.verify("FAIL", [root_cause(variants=[variant("  ")])])
        self.assertViolation("case")
        self.verify("FAIL", [root_cause(variants=[variant(CASE_A), variant(CASE_A, "predicted")])])
        self.assertViolation("중복")

    def test_root_causes_must_be_a_list(self):
        self.verify("FAIL", {"id": "RC-1"})
        self.assertViolation("배열")

    # --- 한계를 숨기지 않는다 ---

    def test_later_variants_are_counted_and_called_out(self):
        self.verify("FAIL", [root_cause(variants=[
            variant(CASE_A), variant(CASE_B, "later", "reproduced")])], attempt=2)
        out = self.check()
        self.assertOk(out)
        self.assertIn("later 1", out.stdout)
        self.assertIn("스윕이 놓친", out.stdout)

    def test_not_probed_variants_are_surfaced(self):
        self.verify("PASS", [root_cause(variants=[
            variant(CASE_A, resolved=True, evidence="t"),
            variant(CASE_C, "predicted", "not_probed", reason="DB 없음")])])
        out = self.check()
        self.assertOk(out)
        self.assertIn("프로브하지 못한", out.stdout)

    def test_json_output(self):
        self.verify("FAIL", [root_cause(variants=[variant(CASE_A), variant(CASE_B, "later")])])
        code, data = self.project.run_json("check_root_causes.py", "--task-id", TID, "--json")
        self.assertEqual(code, 0)
        self.assertTrue(data["ok"])
        self.assertEqual(data["stats"]["by_origin"], {"found": 1, "predicted": 0, "later": 1})
        self.assertEqual(data["verify_status"], "FAIL")

    # --- 인자 ---

    def test_missing_verify_exits_2(self):
        self.assertEqual(self.check().returncode, 2)

    def test_malformed_verify_exits_2(self):
        self.project.write(VERIFY, "{broken")
        self.assertEqual(self.check().returncode, 2)

    def test_invalid_task_id_exits_2(self):
        out = self.project.run("check_root_causes.py", "--task-id", "TASK-task-001")
        self.assertEqual(out.returncode, 2)


class CarriedForwardTest(ProjectTestCase):
    """이전 라운드에 기록된 뿌리·변종을 지워서 PASS 로 가는 길을 막는다."""

    def setUp(self):
        super().setUp()
        self.round1 = {
            "task_id": TID, "status": "FAIL",
            "root_causes": [root_cause(variants=[variant(CASE_A), variant(CASE_B, "predicted")])],
        }
        self.project.write_json(VERIFY, self.round1)
        self.project.commit("chore(workflow): 1차 FAIL")

    def resolved_round2(self) -> dict:
        data = copy.deepcopy(self.round1)
        data["status"] = "PASS"
        for v in data["root_causes"][0]["variants"]:
            v["resolved"], v["evidence"] = True, "test"
        return data

    def check(self):
        return self.project.run("check_root_causes.py", "--task-id", TID)

    def test_keeping_everything_and_resolving_is_ok(self):
        self.project.write_json(VERIFY, self.resolved_round2())
        self.assertEqual(self.check().returncode, 0)

    def test_dropping_the_root_cause_is_a_violation(self):
        data = self.resolved_round2()
        del data["root_causes"]
        self.project.write_json(VERIFY, data)
        out = self.check()
        self.assertEqual(out.returncode, 1)
        self.assertIn("RC-1", out.stdout)
        self.assertIn("사라졌다", out.stdout)

    def test_dropping_an_unfavourable_variant_is_a_violation(self):
        data = self.resolved_round2()
        data["root_causes"][0]["variants"].pop()   # CASE_B 를 지운다
        self.project.write_json(VERIFY, data)
        out = self.check()
        self.assertEqual(out.returncode, 1)
        self.assertIn(CASE_B, out.stdout)

    def test_rewording_a_variant_reads_as_dropping_it(self):
        # 이력 대조는 case 문자열이 같은지로 한다 — 그대로 옮겨 적으라고 문서가 요구한다
        data = self.resolved_round2()
        data["root_causes"][0]["variants"][1]["case"] = "NUL 문자가 든 name"
        self.project.write_json(VERIFY, data)
        self.assertEqual(self.check().returncode, 1)

    def test_adding_a_new_root_cause_alongside_is_ok(self):
        data = self.resolved_round2()
        data["root_causes"].append(root_cause("RC-2", variants=[
            variant("다른 뿌리의 결함", resolved=True, evidence="t")]))
        self.project.write_json(VERIFY, data)
        self.assertEqual(self.check().returncode, 0)

    def test_new_variant_in_an_existing_root_cause_is_ok(self):
        data = self.resolved_round2()
        data["root_causes"][0]["variants"].append(
            variant("뒤늦게 나온 변종", "later", resolved=True, evidence="t"))
        self.project.write_json(VERIFY, data)
        out = self.check()
        self.assertEqual(out.returncode, 0)
        self.assertIn("later 1", out.stdout)

    def test_a_file_with_no_history_has_nothing_to_carry_forward(self):
        other = "TASK-002"
        self.project.write_json(
            f"workflow_design/07_verify/VERIFY_{other}.json",
            {"task_id": other, "status": "PASS"})
        out = self.project.run("check_root_causes.py", "--task-id", other)
        self.assertEqual(out.returncode, 0)

    def test_earlier_version_without_root_causes_is_ignored(self):
        # 이력에 root_causes 가 없는 오래된 형식의 버전이 섞여 있어도 깨지지 않는다
        self.project.write_json(VERIFY, {"task_id": TID, "status": "FAIL", "code_review": {"round_1": []}})
        self.project.commit("old format")
        self.project.write_json(VERIFY, self.resolved_round2())
        self.assertEqual(self.check().returncode, 0)


class DocExamplesTest(unittest.TestCase):
    """문서에 실린 예시가 검증기와 어긋나지 않는다 — 리뷰어가 문서대로 써도 막히면 안 된다."""

    def read(self, rel: str) -> str:
        return (STARTER_ROOT / rel).read_text(encoding="utf-8")

    def test_reviewer_output_example_is_accepted_as_a_fail(self):
        text = self.read(".claude/agents/code-reviewer.md")
        blocks = re.findall(r"```json\n(.*?)\n```", text, re.DOTALL)
        self.assertTrue(blocks, "code-reviewer.md 에서 root_causes JSON 예시를 찾지 못했다")
        data = json.loads(blocks[0])
        problems, stats = check_root_causes.validate_record({"status": "FAIL", **data})
        self.assertEqual(problems, [])
        self.assertEqual(stats["by_origin"], {"found": 1, "predicted": 2, "later": 0})
        self.assertEqual(stats["not_probed"], 1)

    def test_reference_example_is_accepted_as_a_pass(self):
        text = self.read(".claude/skills/wf-verify/references/root-cause-sweep.md")
        blocks = re.findall(r"```jsonc\n(\"root_causes\": \[.*?\n\])\n```", text, re.DOTALL)
        self.assertTrue(blocks, "root-cause-sweep.md 에서 root_causes 예시를 찾지 못했다")
        data = json.loads("{" + blocks[0] + "}")
        problems, _ = check_root_causes.validate_record({"status": "PASS", **data})
        self.assertEqual(problems, [])

    def test_the_documented_schema_values_match_the_validator(self):
        text = self.read(".claude/skills/wf-verify/references/root-cause-sweep.md")
        for value in (*check_root_causes.ORIGINS, *check_root_causes.PROBES):
            self.assertIn(value, text, f"검증기가 받는 값 {value!r} 이 문서에 없다")

    def test_every_doc_that_points_at_the_sweep_points_at_an_existing_file(self):
        target = STARTER_ROOT / ".claude/skills/wf-verify/references/root-cause-sweep.md"
        self.assertTrue(target.is_file())
        for rel in (
            ".claude/agents/code-reviewer.md", ".claude/skills/wf-verify/SKILL.md",
            ".claude/skills/wf-develop/SKILL.md", ".claude/skills/wf-scenario/SKILL.md",
            "docs/workflow/reject-state-machine.md",
        ):
            with self.subTest(doc=rel):
                self.assertIn("root-cause-sweep", self.read(rel))

    def test_wf_verify_gate_runs_the_script_that_exists(self):
        text = self.read(".claude/skills/wf-verify/SKILL.md")
        self.assertIn("check_root_causes.py", text)
        self.assertTrue((SCRIPTS / "check_root_causes.py").is_file())


if __name__ == "__main__":
    unittest.main()
