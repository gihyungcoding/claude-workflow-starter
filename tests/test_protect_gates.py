"""protect_gates.py — 게이트를 통과시키려고 게이트를 고치는 수정은 조용히 일어나지 않는다.

이 훅은 두 방향으로 틀릴 수 있다. 물어야 할 때 안 묻거나(보호 실패),
아무 때나 물어서 사람이 승인 버튼을 습관적으로 누르게 만들거나(경고 피로).
둘 다 확인한다.
"""

from __future__ import annotations

import json
import sys
import unicodedata
import unittest
from pathlib import Path

from helpers import SCRIPTS, ProjectTestCase

sys.path.insert(0, str(SCRIPTS / "hooks"))
sys.path.insert(0, str(SCRIPTS))
import protect_gates  # noqa: E402

HOOK = "hooks/protect_gates.py"
STARTER_ROOT = Path(__file__).resolve().parent.parent

CONSTRAINTS = "docs/architecture/constraints.yaml"
APPROVED_TEST = "backend/src/test/java/FooTest.java"
OTHER_TEST = "backend/src/test/java/BarTest.java"


class ProtectGatesTest(ProjectTestCase):
    def setUp(self):
        super().setUp()
        # 보호 대상이 될 파일들은 이미 존재한다 (새 파일 만들기는 묻지 않는다)
        for rel in (CONSTRAINTS, "frontend/eslint.config.js", "frontend/tsconfig.app.json",
                    ".pre-commit-config.yaml", APPROVED_TEST, OTHER_TEST, "src/app.py"):
            self.project.write(rel, "x\n")

    # --- 픽스처 ---

    def task(self, tid: str, status: str = "ACTIVE", phase: str = "3") -> None:
        self.project.write(
            f"memory-bank/{tid}/activeContext.md",
            f'---\ntask_id: {tid}\nphase: "{phase}"\nstatus: {status}\nlast_updated: 2026-01-01\n---\n',
        )

    def red_tests(self, tid: str, files: list[str], approved: bool = True) -> None:
        self.project.write_json(
            f"workflow_design/05_scenario/TEST_{tid}.json",
            {"test_files": files, "human_review": {"approved": approved}},
        )

    def hook(self, rel: str, key: str = "file_path") -> tuple[int, dict | None, str]:
        target = rel if rel.startswith("/") else str(self.project.path(rel))
        out = self.project.run(HOOK, stdin=json.dumps({"tool_name": "Edit", "tool_input": {key: target}}))
        decision = None
        if out.stdout.strip():
            decision = json.loads(out.stdout)["hookSpecificOutput"]
        return out.returncode, decision, out.stderr

    def assertAsks(self, rel: str, *needles: str) -> None:
        code, decision, _ = self.hook(rel)
        self.assertEqual(code, 0, "이 훅은 항상 exit 0 이어야 한다")
        self.assertIsNotNone(decision, f"{rel}: 물어야 하는데 조용히 통과했다")
        self.assertEqual(decision["permissionDecision"], "ask", "차단(deny)이 아니라 확인(ask)이어야 한다")
        for needle in needles:
            self.assertIn(needle, decision["permissionDecisionReason"])

    def assertSilent(self, rel: str) -> None:
        code, decision, _ = self.hook(rel)
        self.assertEqual(code, 0)
        self.assertIsNone(decision, f"{rel}: 묻지 않아야 하는데 물었다: {decision}")

    # --- 언제 묻나 ---

    def test_constraints_edit_during_phase3_asks(self):
        self.task("TASK-001", phase="3")
        self.assertAsks(CONSTRAINTS, "TASK-001", "Phase 3", "ADR")

    def test_constraints_edit_during_phase4_asks(self):
        self.task("TASK-001", phase="4")
        self.assertAsks(CONSTRAINTS, "Phase 4")

    def test_every_protected_config_pattern_asks(self):
        # 패턴 하나가 목록에서 빠져도 알아채도록 종류마다 한 파일씩 실제로 확인한다
        self.task("TASK-001", phase="3")
        for rel in (
            "frontend/eslint.config.js", "frontend/eslint.config.mjs", ".eslintrc", ".eslintrc.json",
            ".prettierrc", ".prettierrc.yaml", "prettier.config.js", "biome.json", "biome.jsonc",
            "frontend/tsconfig.json", "frontend/tsconfig.app.json", "ruff.toml", ".ruff.toml",
            "mypy.ini", ".mypy.ini", "config/checkstyle-main.xml", ".pre-commit-config.yaml",
        ):
            with self.subTest(rel=rel):
                self.project.write(rel, "x\n")
                self.assertAsks(rel)

    def test_build_files_are_not_protected(self):
        # 의존성 추가로 정당하게 자주 바뀌므로 묻지 않는다
        self.task("TASK-001", phase="3")
        for rel in ("backend/build.gradle", "package.json", "pyproject.toml", "frontend/vite.config.ts"):
            with self.subTest(rel=rel):
                self.project.write(rel, "x\n")
                self.assertSilent(rel)

    def test_approved_red_test_edit_asks(self):
        self.task("TASK-001", phase="3")
        self.red_tests("TASK-001", [APPROVED_TEST])
        self.assertAsks(APPROVED_TEST, "HITL#2", "Phase 2a/2b")

    def test_directory_entry_in_test_files_covers_files_under_it(self):
        self.task("TASK-001", phase="3")
        self.red_tests("TASK-001", ["backend/src/test/java/"])
        self.assertAsks(APPROVED_TEST)

    # --- 언제 묻지 않나 (경고 피로를 막는다) ---

    def test_no_active_task_is_silent(self):
        self.assertSilent(CONSTRAINTS)
        self.assertSilent("frontend/eslint.config.js")

    def test_phases_outside_3_and_4_are_silent(self):
        # /wf-init 의 제약 작성, ADR 과 함께하는 제약 변경, Red 단계의 테스트 작성은 정당하다
        for phase in ("1", "2a", "2b", "5"):
            with self.subTest(phase=phase):
                self.task("TASK-001", phase=phase)
                self.red_tests("TASK-001", [APPROVED_TEST])
                self.assertSilent(CONSTRAINTS)
                self.assertSilent(APPROVED_TEST)

    def test_done_or_blocked_tasks_do_not_count(self):
        for status in ("DONE", "BLOCKED"):
            with self.subTest(status=status):
                self.task("TASK-001", status=status, phase="3")
                self.assertSilent(CONSTRAINTS)

    def test_unrelated_files_are_silent(self):
        self.task("TASK-001", phase="3")
        self.red_tests("TASK-001", [APPROVED_TEST])
        self.assertSilent("src/app.py")
        self.assertSilent(OTHER_TEST)  # 승인 목록에 없는 테스트 (새로 추가한 테스트 등)

    def test_test_edit_is_silent_before_hitl2_approval(self):
        self.task("TASK-001", phase="3")
        self.red_tests("TASK-001", [APPROVED_TEST], approved=False)
        self.assertSilent(APPROVED_TEST)

    def test_only_boolean_true_counts_as_approval(self):
        # 필드가 없거나 "true" 문자열이면 승인이 아니다 — 자기신고성 값을 믿지 않는다
        self.task("TASK-001", phase="3")
        for review in ({}, {"approved": None}, {"approved": "true"}, {"approved": 1}):
            with self.subTest(review=review):
                self.project.write_json(
                    "workflow_design/05_scenario/TEST_TASK-001.json",
                    {"test_files": [APPROVED_TEST], "human_review": review},
                )
                self.assertSilent(APPROVED_TEST)

    def test_test_edit_is_silent_without_red_artifact(self):
        self.task("TASK-001", phase="3")
        self.assertSilent(APPROVED_TEST)

    def test_creating_a_new_file_never_asks(self):
        self.task("TASK-001", phase="3")
        self.project.path("frontend/eslint.config.js").unlink()
        self.assertSilent("frontend/eslint.config.js")
        self.project.path(CONSTRAINTS).unlink()
        self.assertSilent(CONSTRAINTS)

    def test_approval_belongs_to_the_task_that_is_in_phase_3_or_4(self):
        # TASK-002 의 승인된 테스트는 TASK-001(Phase 3)이 건드릴 때가 아니라
        # TASK-002 자신이 Phase 3·4 일 때 보호된다. 종료된 태스크의 테스트는 막지 않는다.
        self.task("TASK-001", phase="3")
        self.task("TASK-002", status="DONE", phase="5")
        self.red_tests("TASK-002", [APPROVED_TEST])
        self.assertSilent(APPROVED_TEST)

    def test_any_guarded_task_is_enough_when_several_are_active(self):
        self.task("TASK-001", phase="1")
        self.task("TASK-002", phase="4")
        self.assertAsks(CONSTRAINTS, "TASK-002")

    # --- 같은 파일을 다른 표기로 가리켜도 보호된다 ---
    # macOS(APFS)·Windows 는 대소문자를 구분하지 않는다. resolve() 는 표기를 그대로 남기므로
    # 문자열을 그대로 비교하면 `DOCS/Constraints.YAML` 로 보호를 우회할 수 있다.
    # 대소문자를 구분하는 파일시스템(Linux CI)에서는 다른 경로라 해당 없음 — 건너뛴다.

    def _fs_ignores_case(self) -> bool:
        probe = self.project.write("CaseProbe.tmp", "x")
        try:
            return self.project.path("caseprobe.tmp").exists()
        finally:
            probe.unlink()

    def test_case_variant_of_constraints_path_still_asks(self):
        if not self._fs_ignores_case():
            self.skipTest("대소문자를 구분하는 파일시스템")
        self.task("TASK-001", phase="3")
        self.assertAsks("DOCS/Architecture/CONSTRAINTS.YAML", "ADR")

    def test_case_variant_of_lint_config_still_asks(self):
        if not self._fs_ignores_case():
            self.skipTest("대소문자를 구분하는 파일시스템")
        self.task("TASK-001", phase="3")
        self.assertAsks("frontend/ESLINT.CONFIG.JS")

    def test_case_variant_of_approved_test_still_asks(self):
        if not self._fs_ignores_case():
            self.skipTest("대소문자를 구분하는 파일시스템")
        self.task("TASK-001", phase="3")
        self.red_tests("TASK-001", [APPROVED_TEST])
        self.assertAsks(APPROVED_TEST.upper().replace("/SRC/", "/src/"), "HITL#2")

    def test_unicode_normalization_variant_of_approved_test_still_asks(self):
        # APFS 는 NFC/NFD 를 같은 이름으로 본다. Linux 에서는 다른 파일이라 건너뛴다.
        nfc = "backend/src/test/java/" + unicodedata.normalize("NFC", "한글Test.java")
        nfd = "backend/src/test/java/" + unicodedata.normalize("NFD", "한글Test.java")
        self.project.write(nfc, "x\n")
        if not self.project.path(nfd).exists():
            self.skipTest("유니코드 정규화를 구분하는 파일시스템")
        self.task("TASK-001", phase="3")
        self.red_tests("TASK-001", [nfc])
        self.assertAsks(nfd, "HITL#2")

    # --- 훅은 작업을 막는 쪽으로 고장나면 안 된다 ---

    def test_unreadable_payload_is_silent(self):
        self.task("TASK-001", phase="3")
        out = self.project.run(HOOK, stdin="not json")
        self.assertEqual((out.returncode, out.stdout), (0, ""))

    def test_payload_without_path_is_silent(self):
        self.task("TASK-001", phase="3")
        out = self.project.run(HOOK, stdin=json.dumps({"tool_input": {}}))
        self.assertEqual((out.returncode, out.stdout), (0, ""))

    def test_path_outside_repo_is_silent(self):
        self.task("TASK-001", phase="3")
        self.assertSilent("/etc/hosts")

    def test_corrupt_red_artifact_does_not_break_the_hook(self):
        self.task("TASK-001", phase="3")
        self.project.write("workflow_design/05_scenario/TEST_TASK-001.json", "{broken")
        self.assertSilent(APPROVED_TEST)
        # 깨진 산출물이어도 제약 파일 보호는 그대로 동작한다
        self.assertAsks(CONSTRAINTS)

    def test_test_files_with_unexpected_types_do_not_break_the_hook(self):
        self.task("TASK-001", phase="3")
        self.project.write_json(
            "workflow_design/05_scenario/TEST_TASK-001.json",
            {"test_files": [None, 3, {"a": 1}, APPROVED_TEST], "human_review": {"approved": True}},
        )
        self.assertAsks(APPROVED_TEST)

    def test_notebook_path_key_is_understood(self):
        self.task("TASK-001", phase="3")
        code, decision, _ = self.hook(CONSTRAINTS, key="notebook_path")
        self.assertEqual(decision["permissionDecision"], "ask")


class PathKeyTest(unittest.TestCase):
    """경로 비교 키 — 파일시스템과 무관하게 항상 검증되는 부분."""

    def test_case_is_folded(self):
        self.assertEqual(protect_gates.path_key("Docs/Architecture/Constraints.YAML"),
                         protect_gates.path_key("docs/architecture/constraints.yaml"))

    def test_unicode_normalization_is_folded(self):
        nfc = unicodedata.normalize("NFC", "한글.java")
        nfd = unicodedata.normalize("NFD", "한글.java")
        self.assertNotEqual(nfc, nfd)
        self.assertEqual(protect_gates.path_key(nfc), protect_gates.path_key(nfd))

    def test_different_names_stay_different(self):
        self.assertNotEqual(protect_gates.path_key("a/b.py"), protect_gates.path_key("a/c.py"))

    def test_gate_config_match_ignores_case_but_not_build_files(self):
        for name in ("ESLint.Config.JS", "TSConfig.App.json", ".PRETTIERRC", "Biome.JSON", "Checkstyle-Main.XML"):
            with self.subTest(name=name):
                self.assertTrue(protect_gates.matches_gate_config(name))
        for name in ("build.gradle", "package.json", "vite.config.ts", "eslint-notes.md"):
            with self.subTest(name=name):
                self.assertFalse(protect_gates.matches_gate_config(name))

    def test_approved_test_match_ignores_case_and_normalization(self):
        approved = {unicodedata.normalize("NFC", "backend/src/test/한글Test.java"), "backend/src/test/dir/"}
        self.assertTrue(protect_gates.is_approved_test(
            unicodedata.normalize("NFD", "BACKEND/src/test/한글test.java"), approved))
        self.assertTrue(protect_gates.is_approved_test("Backend/SRC/test/DIR/deep/XTest.java", approved))
        self.assertFalse(protect_gates.is_approved_test("backend/src/test/other.java", approved))


class ProtectGatesWiringTest(unittest.TestCase):
    """스크립트가 있어도 settings.json 에 연결되지 않으면 아무것도 보호하지 못한다."""

    def settings(self) -> dict:
        return json.loads((STARTER_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))

    def test_hook_is_registered_for_edit_tools(self):
        entries = self.settings()["hooks"]["PreToolUse"]
        matched = [
            e for e in entries
            if any("protect_gates.py" in h.get("command", "") for h in e.get("hooks", []))
        ]
        self.assertTrue(matched, "protect_gates.py 가 PreToolUse 에 등록되어 있지 않다")
        for tool in ("Write", "Edit"):
            self.assertTrue(
                any(tool in e["matcher"].split("|") for e in matched),
                f"{tool} 도구에 연결되어 있지 않다",
            )

    def test_registered_script_exists(self):
        for entry in self.settings()["hooks"]["PreToolUse"]:
            for hook in entry["hooks"]:
                cmd = hook["command"]
                if "scripts/hooks/" in cmd:
                    name = cmd.split("scripts/hooks/")[1].split('"')[0].split(" ")[0]
                    self.assertTrue((STARTER_ROOT / "scripts" / "hooks" / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
