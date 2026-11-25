"""코딩 규칙 게이트 — 첫 태스크 전에 규칙이 정해지고 기준 구현으로 증명됐는가.

시험 실행(ticket-booking)의 실제 사례를 하나씩 재현한다: 테스트 DB 를 '나중에 전환'으로 두고 두 달,
포매터 없이 첫 태스크, 빈 저장소에서 쓴 제약 경로가 실제 파일과 어긋나 거짓 통과, warn 승격을 잊음.
"""

from __future__ import annotations

from helpers import ProjectTestCase
from test_check_architecture import HEADER, constraint

GATE = "check_conventions.py"
CONV = "docs/architecture/conventions.md"

ROWS = {
    "C-TESTDB": "운영과 같음 — PostgreSQL (Testcontainers)",
    "C-LINT": "Spotless + google-java-format",
    "C-LAYOUT": "api → service → repository",
    "C-ERROR": "{code, message}",
    "C-VALID": "Bean Validation, @Valid",
    "C-DATA": "쿼리는 repository 만",
    "C-TEST": "<Class>Test, 대상 패키지",
    "C-LOG": "SLF4J",
    "C-FE": "해당 없음 — 백엔드만",
    "C-COMMIT": "CLAUDE.md 「커밋」 절",
}


def conventions(rows: dict[str, str] | None = None, refs: list[str] | None = None, status: str = "기준 구현 확인") -> str:
    rows = dict(ROWS if rows is None else rows)
    body = "\n".join(f"| {k} | {v} | 리뷰 | {status} |" for k, v in rows.items())
    ref_lines = "\n".join(f"- {r} — 기준" for r in (["src/api/echo.py"] if refs is None else refs))
    return f"# 코딩 규칙\n\n## 규칙\n\n| id | 결정 | 검사 | 상태 |\n|---|---|---|---|\n{body}\n\n## 기준 파일\n\n{ref_lines}\n\n## 결정 메모\n"


class ConventionsGateTest(ProjectTestCase):
    def setUp(self):
        super().setUp()
        self.project.write("CLAUDE.md", "# 가이드\n\n- **린트**: `./gradlew spotlessCheck`\n")
        self.project.write("src/api/echo.py", "def echo(): ...\n")
        self.project.write(CONV, conventions())

    def gate(self) -> tuple[int, dict]:
        return self.project.run_json(GATE, "--json")

    def assertBlocks(self, needle: str) -> None:
        code, out = self.gate()
        self.assertEqual(code, 1, out)
        self.assertTrue(any(needle in p for p in out["problems"]), f"{needle!r} 없음: {out['problems']}")

    def test_complete_conventions_pass(self):
        code, out = self.gate()
        self.assertEqual((code, out["problems"]), (0, []))

    def test_missing_file_blocks_first_task(self):
        self.project.path(CONV).unlink()
        self.assertBlocks("conventions.md 가 없다")

    def test_todo_item_blocks(self):
        self.project.write(CONV, conventions({**ROWS, "C-VALID": "TODO"}))
        self.assertBlocks("C-VALID: TODO 가 남았다 — 결정")

    def test_missing_item_blocks(self):
        rows = dict(ROWS)
        del rows["C-TEST"]
        self.project.write(CONV, conventions(rows))
        self.assertBlocks("C-TEST: 표에 없다")

    def test_different_test_db_needs_adr_and_switch_task(self):
        # 시험 실행: "DB 전용 기능을 쓰는 순간 전환" 만 적고 두 달 동안 전환하지 않았다
        self.project.write(CONV, conventions({**ROWS, "C-TESTDB": "다름 — H2, PostgreSQL 기능 쓰면 전환"}))
        self.assertBlocks("C-TESTDB")
        self.project.write(CONV, conventions({**ROWS, "C-TESTDB": "다름 — H2 (ADR-0006, promote_after: TASK-005)"}))
        self.assertEqual(self.gate()[0], 0)

    def test_reference_files_must_exist(self):
        self.project.write(CONV, conventions(refs=[]))
        self.assertBlocks("기준 파일이 없다 —")
        self.project.write(CONV, conventions(refs=["src/api/ghost.py"]))
        self.assertBlocks("기준 파일이 없다: src/api/ghost.py")

    def test_lint_command_must_be_filled(self):
        self.project.write("CLAUDE.md", "- **린트**: (예: `ruff check`)\n")
        self.assertBlocks("린트 명령이 비어 있다")

    def test_constraint_glob_matching_nothing_blocks(self):
        # 시험 실행: **/controller/** 로 썼는데 코드는 **/api/** — 검사 대상 0개라 거짓 통과
        self.project.write("docs/architecture/constraints.yaml",
                           HEADER + constraint("ARCH-001", "forbidden_import", '"src/controller/**/*.py"', '"^import repo"'))
        self.assertBlocks("ARCH-001: 검사 대상이 0개")

    def test_satisfied_forbidden_path_is_not_no_target(self):
        # 금지 경로는 파일이 없는 것이 통과다
        self.project.write("docs/architecture/constraints.yaml",
                           HEADER + constraint("TEST-001", "forbidden_path", '"src/**/task[0-9]*"'))
        self.assertEqual(self.gate()[0], 0)

    def test_warn_without_promote_after_blocks(self):
        # 시험 실행: DESIGN-003 이 기한 없는 warn 으로 남았다
        self.project.write("docs/architecture/constraints.yaml",
                           HEADER + constraint("DESIGN-003", "forbidden_pattern", '"src/**/*.py"', '"height=240"', severity="warn"))
        self.assertBlocks("DESIGN-003: warn 인데 promote_after 가 없다")

    def test_started_project_warns_but_does_not_block(self):
        self.project.path(CONV).unlink()
        self.project.write_json("workflow_design/02_tasks/tasks.json", [{"id": "TASK-001", "status": "done"}])
        code, out = self.gate()
        self.assertEqual(code, 0)
        self.assertTrue(out["started"] and not out["pass"] and not out["blocking"])

    def test_rules_not_confirmed_by_reference_slice_block(self):
        # 드라이런: 상태가 전부 '정함' 이어도 통과했다 — 4.5 사람 확인이 강제되지 않았다
        self.project.write(CONV, conventions(status="정함"))
        self.assertBlocks("C-TESTDB: 상태가 '정함'")

    def test_not_applicable_item_passes(self):
        rows = conventions().replace("| C-FE | 해당 없음 — 백엔드만 | 리뷰 | 기준 구현 확인 |", "| C-FE | 해당 없음 — 백엔드만 | — | 해당 없음 |")
        self.project.write(CONV, rows)
        self.assertEqual(self.gate()[0], 0)

    def test_pipe_inside_cell_is_caught(self):
        self.project.write(CONV, conventions({**ROWS, "C-LOG": "print|console 금지"}))
        self.assertBlocks("C-LOG: 칸이 4개다")
        self.project.write(CONV, conventions({**ROWS, "C-LOG": "print\\|console 금지"}))
        self.assertEqual(self.gate()[0], 0)

    def test_error_violation_in_reference_slice_blocks(self):
        # 드라이런: 제약 위반이 있어도 게이트가 통과했다
        self.project.write("src/api/echo.py", "import repo\n")
        self.project.write("docs/architecture/constraints.yaml",
                           HEADER + constraint("ARCH-001", "forbidden_import", '"src/api/**/*.py"', '"^import repo"'))
        self.assertBlocks("ARCH-001: 위반 1건")
