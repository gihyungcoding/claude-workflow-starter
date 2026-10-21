"""check_architecture.py — "검사하지 않은 것을 통과로 보고하지 않는다" 가 핵심이다."""

from __future__ import annotations

import unittest
from pathlib import Path

from helpers import Project, ProjectTestCase

HEADER = "version: 1\n\nconstraints:\n"


def constraint(
    cid: str,
    type_: str,
    paths: str,
    pattern: str | None = None,
    severity: str = "error",
    extra_detect: str = "",
    extra: str = "",
) -> str:
    lines = [
        f"  - id: {cid}",
        f'    rule: "{cid} 규칙"',
        f"    severity: {severity}",
    ]
    if extra:
        lines.append(extra)
    lines += ["    detect:", f"      type: {type_}", f"      paths: [{paths}]"]
    if pattern is not None:
        lines.append(f"      pattern: {pattern}")
    if extra_detect:
        lines.append(extra_detect)
    return "\n".join(lines) + "\n"


class CheckArchitectureTest(ProjectTestCase):
    def constraints(self, *items: str) -> None:
        self.project.write("docs/architecture/constraints.yaml", HEADER + "".join(items))

    def check(self, *args: str) -> tuple[int, dict]:
        return self.project.run_json("check_architecture.py", "--json", *args)

    # --- 기본 판정 ---

    def test_clean_code_passes_and_reports_files_scanned(self):
        self.project.write("src/api/a.py", "import service\n")
        self.constraints(constraint("ARCH-001", "forbidden_import", '"src/api/**/*.py"', '"^import repo"'))
        code, data = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "pass")
        self.assertEqual(data["files_scanned"], 1)

    def test_error_violation_fails_with_exit_1(self):
        self.project.write("src/api/a.py", "import repo\n")
        self.constraints(constraint("ARCH-001", "forbidden_import", '"src/api/**/*.py"', '"^import repo"'))
        code, data = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(data["status"], "fail")
        self.assertEqual(data["error_count"], 1)
        v = data["results"][0]["violations"][0]
        self.assertEqual((v["file"], v["line"]), ("src/api/a.py", 1))

    def test_warn_violation_does_not_fail(self):
        self.project.write("src/a.py", "TODO\n")
        self.constraints(constraint("DESIGN-003", "forbidden_pattern", '"src/**/*.py"', '"TODO"', severity="warn"))
        code, data = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(data["warn_count"], 1)
        self.assertEqual(data["error_count"], 0)

    # --- 정직한 보고: 아무것도 검사하지 않은 것은 통과가 아니다 ---

    def test_glob_matching_nothing_is_no_target_not_pass(self):
        self.project.write("src/a.py", "import repo\n")
        # glob 이 실제 경로와 어긋났다: 위반이 있어도 검사되지 않는다
        self.constraints(constraint("ARCH-001", "forbidden_import", '"wrong/**/*.py"', '"^import repo"'))
        code, data = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "no_target")
        self.assertEqual(data["no_target"], ["ARCH-001"])
        self.assertEqual(data["files_scanned"], 0)

    def test_no_target_is_flagged_in_human_output(self):
        self.constraints(constraint("ARCH-001", "forbidden_import", '"wrong/**/*.py"', '"x"'))
        out = self.project.run("check_architecture.py")
        self.assertEqual(out.returncode, 0)
        self.assertIn("아무것도 검사하지 않았습니다", out.stdout)
        self.assertNotIn("모두 통과", out.stdout)

    def test_no_target_is_not_reported_for_changed_only(self):
        # --changed-only 에서 대상 0개는 "그 계층에 변경이 없다"는 뜻이다
        self.project.write("src/a.py", "x = 1\n")
        self.project.commit()
        self.constraints(constraint("ARCH-001", "forbidden_import", '"src/**/*.py"', '"^import repo"'))
        self.project.commit()
        code, data = self.check("--changed-only")
        self.assertEqual(code, 0)
        self.assertEqual(data["no_target"], [])

    def test_repo_inside_directory_named_build_is_still_scanned(self):
        # 저장소가 build/ 같은 이름의 상위 디렉터리 아래에 있어도 파일을 건너뛰면 안 된다.
        # SKIP_DIRS 는 저장소 안의 빌드 산출물을 위한 것이다.
        outer = Path(self.project._tmp) / "build"
        outer.mkdir()
        nested = Project(parent=outer)
        self.addCleanup(nested.cleanup)
        nested.write("src/a.py", "import repo\n")
        nested.write(
            "docs/architecture/constraints.yaml",
            HEADER + constraint("ARCH-001", "forbidden_import", '"src/**/*.py"', '"^import repo"'),
        )
        code, data = nested.run_json("check_architecture.py", "--json")
        self.assertEqual(data["files_scanned"], 1, "상위 경로의 'build' 때문에 검사 대상이 사라졌다")
        self.assertEqual(code, 1)

    def test_build_output_inside_repo_is_skipped(self):
        self.project.write("src/a.py", "ok\n")
        self.project.write("src/build/gen.py", "import repo\n")
        self.constraints(constraint("ARCH-001", "forbidden_import", '"src/**/*.py"', '"^import repo"'))
        code, data = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(data["files_scanned"], 1)

    # --- 타입별 동작 ---

    def test_exclude_paths_removes_canonical_files(self):
        self.project.write("src/tokens.css", "color: #fff;\n")
        self.project.write("src/page.css", "color: #000;\n")
        self.constraints(
            constraint(
                "DESIGN-002",
                "forbidden_pattern",
                '"src/**/*.css"',
                '"#[0-9a-fA-F]{3}"',
                extra_detect='      exclude_paths: ["src/tokens.css"]',
            )
        )
        code, data = self.check()
        files = [v["file"] for v in data["results"][0]["violations"]]
        self.assertEqual(files, ["src/page.css"])
        self.assertEqual(data["results"][0]["files_scanned"], 1)

    def test_forbidden_path_flags_existing_file(self):
        self.project.write("src/legacy/old.py", "")
        self.constraints(constraint("ARCH-009", "forbidden_path", '"src/legacy/**"'))
        code, data = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(data["error_count"], 1)

    def test_trailing_double_star_matches_files_on_every_python_version(self):
        # 파이썬 3.12 까지 Path.glob("dir/**") 는 디렉터리만 돌려준다. 같은 제약이 버전에 따라
        # 위반을 놓치면 안 되므로 스크립트가 '**/*' 로 통일한다 (CI 가 3.10 과 3.13 을 모두 돈다).
        self.project.write("src/legacy/deep/old.py", "")
        self.constraints(constraint("ARCH-009", "forbidden_path", '"src/legacy/**"'))
        code, data = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(data["results"][0]["violations"][0]["file"], "src/legacy/deep/old.py")

    def test_required_path_missing_is_violation(self):
        self.constraints(constraint("ARCH-010", "required_path", '"docs/adr/*.md"'))
        code, data = self.check()
        self.assertEqual(code, 1)

    def test_required_path_present_passes(self):
        self.project.write("docs/adr/0001.md", "")
        self.constraints(constraint("ARCH-010", "required_path", '"docs/adr/*.md"'))
        code, data = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "pass")

    # --- 잘못 쓴 제약은 통과가 아니라 위반이다 ---

    def test_unknown_detect_type_is_violation(self):
        self.project.write("src/a.py", "")
        self.constraints(constraint("ARCH-001", "forbiden_import", '"src/**/*.py"', '"x"'))
        code, data = self.check()
        self.assertEqual(code, 1)
        self.assertIn("detect.type", data["results"][0]["violations"][0]["detail"])

    def test_invalid_regex_is_violation(self):
        self.project.write("src/a.py", "")
        self.constraints(constraint("ARCH-001", "forbidden_import", '"src/**/*.py"', '"(unclosed"'))
        code, data = self.check()
        self.assertEqual(code, 1)
        self.assertIn("정규식", data["results"][0]["violations"][0]["detail"])

    def test_missing_pattern_is_violation(self):
        self.project.write("src/a.py", "")
        self.constraints(constraint("ARCH-001", "forbidden_import", '"src/**/*.py"'))
        code, data = self.check()
        self.assertEqual(code, 1)

    # --- 파일/인자 ---

    def test_missing_constraints_file_is_skipped_not_failed(self):
        code, data = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "skipped")

    def test_empty_constraints_reported_as_empty(self):
        self.project.write("docs/architecture/constraints.yaml", HEADER)
        code, data = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "empty")

    def test_unknown_id_filter_exits_2(self):
        self.constraints(constraint("ARCH-001", "forbidden_import", '"src/**"', '"x"'))
        out = self.project.run("check_architecture.py", "--id", "NOPE-1")
        self.assertEqual(out.returncode, 2)

    def test_id_filter_checks_only_that_constraint(self):
        self.project.write("src/a.py", "import repo\n")
        self.constraints(
            constraint("ARCH-001", "forbidden_import", '"src/**/*.py"', '"^import repo"'),
            constraint("ARCH-002", "forbidden_import", '"src/**/*.py"', '"^import other"'),
        )
        code, data = self.check("--id", "ARCH-002")
        self.assertEqual(code, 0)
        self.assertEqual([r["id"] for r in data["results"]], ["ARCH-002"])

    # --- 승격 기한 ---

    def _promote_fixture(self, task_status: str, severity: str = "warn") -> dict:
        self.project.write("src/a.py", "ok\n")
        self.constraints(
            constraint(
                "DESIGN-003",
                "forbidden_pattern",
                '"src/**/*.py"',
                '"TODO"',
                severity=severity,
                extra="    promote_after: TASK-003",
            )
        )
        self.project.write_json(
            "workflow_design/02_tasks/tasks.json",
            [{"id": "TASK-003", "status": task_status}],
        )
        code, data = self.check()
        self.assertEqual(code, 0)
        return data

    def test_overdue_promotion_reported_when_task_done_and_still_warn(self):
        data = self._promote_fixture("done")
        self.assertEqual(data["overdue_promotions"], [{"id": "DESIGN-003", "promote_after": "TASK-003"}])

    def test_no_overdue_while_task_not_done(self):
        self.assertEqual(self._promote_fixture("in_progress")["overdue_promotions"], [])

    def test_no_overdue_once_promoted_to_error(self):
        self.assertEqual(self._promote_fixture("done", severity="error")["overdue_promotions"], [])

    def test_overdue_promotion_is_printed_for_humans(self):
        self._promote_fixture("done")
        out = self.project.run("check_architecture.py")
        self.assertIn("승격 기한이 지난", out.stdout)
        self.assertNotIn("모두 통과", out.stdout)


if __name__ == "__main__":
    unittest.main()
