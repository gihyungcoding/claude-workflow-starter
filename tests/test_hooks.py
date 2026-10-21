"""scripts/hooks/* — 막아야 할 것은 막고, 막으면 안 되는 것은 막지 않는다.

훅은 두 방향으로 틀릴 수 있다. 위반을 놓치거나(거짓 통과), 정상 작업을 막거나(거짓 차단).
둘 다 확인한다. 특히 훅이 *고장 났을 때* 작업을 막지 않아야 한다는 약속을 검사한다.
"""

from __future__ import annotations

import json
import os
import unittest

from helpers import ProjectTestCase

CHECK_PATHS = "hooks/check_artifact_paths.py"
CHECK_SECRETS = "hooks/check_secrets.py"
CHECK_SYMLINKS = "hooks/check_symlinks.py"
CHECK_UNCOMMITTED = "hooks/check_uncommitted.py"
SESSION_START = "hooks/session_start.py"

# 테스트 소스에 리터럴 토큰을 두지 않는다 — 저장소 전체 비밀정보 검사(--all)와
# GitHub 의 시크릿 스캔이 이 파일을 유출로 오인하지 않도록 실행 시점에 조립한다.
FAKE_AWS_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"
FAKE_GH_TOKEN = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
FAKE_PRIVATE_KEY_HEADER = "-----BEGIN RSA " + "PRIVATE KEY-----"
FAKE_PASSWORD_LINE = 'pass' + 'word = "hunter2' + 'hunter2"'


class ArtifactPathHookTest(ProjectTestCase):
    def hook(self, rel_or_abs: str) -> object:
        target = rel_or_abs if os.path.isabs(rel_or_abs) else str(self.project.path(rel_or_abs))
        payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": target}})
        return self.project.run(CHECK_PATHS, "--hook", stdin=payload)

    def assertAllowed(self, rel: str) -> None:
        out = self.hook(rel)
        self.assertEqual(out.returncode, 0, f"{rel} 가 막혔다: {out.stderr}")

    def assertDenied(self, rel: str) -> None:
        out = self.hook(rel)
        self.assertEqual(out.returncode, 2, f"{rel} 가 통과했다")
        decision = json.loads(out.stdout.splitlines()[0])["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertTrue(decision["permissionDecisionReason"])

    # --- 허용 ---

    def test_canonical_paths_are_allowed(self):
        for rel in (
            "memory-bank/TASK-001/activeContext.md",
            "memory-bank/TASK-001/checkpoints/phase2a/CP-2.2_canonical-scenarios.md",
            "memory-bank/TASK-0042/checkpoints/phase3/CP-3.4_context-dev.md",
            "workflow_design/04_plan/PLAN_TASK-001.json",
            "workflow_design/05_scenario/SCENARIO_TASK-001.md",
            "docs/decisions/ADR-0001-use-postgres.md",
            "docs/product/design-tokens.css",
            "src/anything/else.py",
        ):
            with self.subTest(rel=rel):
                self.assertAllowed(rel)

    def test_v1_retry_checkpoint_names_remain_allowed(self):
        self.assertAllowed("memory-bank/TASK-001/checkpoints/phase2a/CP-2.2_canonical-scenarios_retry1.md")

    # --- 차단 ---

    def test_memory_bank_nested_under_workflow_design_is_denied(self):
        self.assertDenied("workflow_design/memory-bank/TASK-001/activeContext.md")

    def test_double_prefixed_task_id_is_denied(self):
        self.assertDenied("memory-bank/TASK-task-001/activeContext.md")

    def test_task_folder_must_be_well_formed(self):
        self.assertDenied("memory-bank/TASK-1/activeContext.md")
        self.assertDenied("memory-bank/task-001/activeContext.md")

    def test_unknown_workflow_design_directory_is_denied(self):
        self.assertDenied("workflow_design/05_chain_data_plan/x.json")

    def test_free_form_checkpoint_name_is_denied(self):
        self.assertDenied("memory-bank/TASK-001/checkpoints/phase2a/CP-9.9_my-notes.md")

    def test_unknown_checkpoint_phase_dir_is_denied(self):
        self.assertDenied("memory-bank/TASK-001/checkpoints/phase9/CP-2.2_canonical-scenarios.md")

    def test_unknown_docs_directory_is_denied(self):
        self.assertDenied("docs/random-stuff/note.md")

    def test_non_kebab_doc_name_is_denied(self):
        self.assertDenied("docs/product/Design_Notes.md")

    # --- 훅은 작업을 막는 쪽으로 고장나면 안 된다 ---

    def test_unreadable_payload_is_allowed(self):
        out = self.project.run(CHECK_PATHS, "--hook", stdin="not json")
        self.assertEqual(out.returncode, 0)

    def test_payload_without_path_is_allowed(self):
        out = self.project.run(CHECK_PATHS, "--hook", stdin=json.dumps({"tool_input": {}}))
        self.assertEqual(out.returncode, 0)

    def test_path_outside_repo_is_allowed(self):
        self.assertAllowed("/etc/hosts")

    # --- CLI 모드 ---

    def test_cli_flags_a_bad_file_with_exit_1(self):
        out = self.project.run(CHECK_PATHS, "workflow_design/memory-bank/x.md")
        self.assertEqual(out.returncode, 1)

    def test_scan_all_finds_existing_violations(self):
        self.project.write("workflow_design/05_chain_data_plan/x.json", "{}")
        self.project.commit()
        self.assertEqual(self.project.run(CHECK_PATHS, "--all").returncode, 1)

    def test_scan_all_clean_repo_passes(self):
        self.assertEqual(self.project.run(CHECK_PATHS, "--all").returncode, 0)


class SecretsHookTest(ProjectTestCase):
    def scan(self, content: str, rel: str = "src/config.py") -> object:
        self.project.write(rel, content)
        return self.project.run(CHECK_SECRETS, rel)

    def test_aws_access_key_is_found(self):
        out = self.scan(f'KEY = "{FAKE_AWS_KEY}"\n')
        self.assertEqual(out.returncode, 1)
        self.assertIn("AWS Access Key", out.stdout)

    def test_github_token_is_found(self):
        self.assertEqual(self.scan(f"token={FAKE_GH_TOKEN}\n").returncode, 1)

    def test_private_key_header_is_found(self):
        self.assertEqual(self.scan(FAKE_PRIVATE_KEY_HEADER + "\n").returncode, 1)

    def test_hardcoded_password_is_found(self):
        self.assertEqual(self.scan(FAKE_PASSWORD_LINE + "\n").returncode, 1)

    def test_finding_does_not_echo_the_full_secret(self):
        out = self.scan(f"token={FAKE_GH_TOKEN}\n")
        self.assertNotIn(FAKE_GH_TOKEN, out.stdout, "발견 보고가 비밀값 전체를 다시 출력한다")

    def test_placeholder_values_are_ignored(self):
        self.assertEqual(self.scan('password = "your_password_here"\n').returncode, 0)
        self.assertEqual(self.scan('api_key = "<API_KEY_VALUE>"\n').returncode, 0)

    def test_environment_variable_reference_is_ignored(self):
        self.assertEqual(self.scan('password = "${DB_PASSWORD_VALUE}"\n').returncode, 0)

    def test_security_docs_are_excluded(self):
        out = self.scan(f"example leak: {FAKE_AWS_KEY}\n", rel="docs/security/leaks.md")
        self.assertEqual(out.returncode, 0)

    def test_binary_suffix_is_skipped(self):
        self.assertEqual(self.scan(f"{FAKE_AWS_KEY}\n", rel="assets/logo.png").returncode, 0)

    def test_clean_file_passes(self):
        self.assertEqual(self.scan("print('hello')\n").returncode, 0)

    def test_no_arguments_is_an_error_not_a_pass(self):
        self.assertEqual(self.project.run(CHECK_SECRETS).returncode, 1)

    def test_scan_all_covers_tracked_files(self):
        self.project.write("src/leak.py", f'K = "{FAKE_AWS_KEY}"\n')
        self.project.commit()
        self.assertEqual(self.project.run(CHECK_SECRETS, "--all").returncode, 1)


class SymlinkHookTest(ProjectTestCase):
    def link(self, name: str, target: str) -> str:
        path = self.project.path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(target, path)
        return name

    def test_absolute_symlink_is_blocked(self):
        name = self.link("docs/abs", "/Users/someone/project")
        self.assertEqual(self.project.run(CHECK_SYMLINKS, name).returncode, 1)

    def test_absolute_link_into_the_repo_itself_is_blocked(self):
        # 대상이 저장소 안이어도 절대경로면 다른 사람의 clone 에서 깨진다.
        # "저장소 밖" 규칙에는 걸리지 않으므로 절대경로 규칙이 따로 막아야 한다.
        self.project.write("docs/real.md", "x\n")
        name = self.link("docs/alias.md", str(self.project.path("docs/real.md")))
        out = self.project.run(CHECK_SYMLINKS, name)
        self.assertEqual(out.returncode, 1)
        self.assertIn("절대경로", out.stdout)

    def test_link_escaping_the_repo_is_blocked(self):
        name = self.link("docs/out", "../../../etc/passwd")
        self.assertEqual(self.project.run(CHECK_SYMLINKS, name).returncode, 1)

    def test_relative_link_inside_repo_is_allowed(self):
        self.project.write("docs/real.md", "x\n")
        name = self.link("docs/alias.md", "real.md")
        self.assertEqual(self.project.run(CHECK_SYMLINKS, name).returncode, 0)

    def test_dangling_link_inside_repo_is_allowed(self):
        # 대상이 아직 없는 링크가 정당한 경우가 있다 (스크립트 docstring 에 명시된 설계)
        name = self.link("docs/future.md", "not-yet.md")
        self.assertEqual(self.project.run(CHECK_SYMLINKS, name).returncode, 0)

    def test_regular_file_is_allowed(self):
        self.project.write("docs/a.md", "x\n")
        self.assertEqual(self.project.run(CHECK_SYMLINKS, "docs/a.md").returncode, 0)

    def test_scan_all_finds_committed_absolute_link(self):
        self.link("bad", "/tmp/x")
        self.project.commit()
        self.assertEqual(self.project.run(CHECK_SYMLINKS, "--all").returncode, 1)


class UncommittedHookTest(ProjectTestCase):
    def test_warns_about_untracked_checkpoint_but_never_blocks(self):
        # git 은 새 디렉터리를 폴더 단위로 접어서 보여준다 — 그래서 파일명이 아니라 폴더까지만 단언한다
        self.project.write("memory-bank/TASK-001/activeContext.md", "---\nstatus: ACTIVE\n---\n")
        self.project.commit()
        self.project.write("memory-bank/TASK-001/checkpoints/phase1/CP-1.3_context-plan.md", "x\n")
        out = self.project.run(CHECK_UNCOMMITTED)
        self.assertEqual(out.returncode, 0, "이 훅은 항상 exit 0 이어야 한다")
        self.assertIn("커밋되지 않은 워크플로우 산출물", out.stderr)
        self.assertIn("memory-bank/TASK-001/checkpoints", out.stderr)

    def test_silent_when_everything_is_committed(self):
        out = self.project.run(CHECK_UNCOMMITTED)
        self.assertEqual((out.returncode, out.stderr), (0, ""))

    def test_ignores_dirty_files_outside_workflow_dirs(self):
        self.project.write("src/wip.py", "x\n")
        self.assertEqual(self.project.run(CHECK_UNCOMMITTED).stderr, "")


class SessionStartHookTest(ProjectTestCase):
    def context(self) -> str:
        out = self.project.run(SESSION_START)
        self.assertEqual(out.returncode, 0)
        if not out.stdout.strip():
            return ""
        payload = json.loads(out.stdout)["hookSpecificOutput"]
        self.assertEqual(payload["hookEventName"], "SessionStart")
        return payload["additionalContext"]

    def task(self, tid: str, status: str, phase: str = "3", **extra: str) -> None:
        fm = [f"task_id: {tid}", f'title: "{tid} 제목"', f'phase: "{phase}"', f"status: {status}",
              "last_updated: 2099-01-01"]
        fm += [f"{k}: {v}" for k, v in extra.items()]
        self.project.write(f"memory-bank/{tid}/activeContext.md", "---\n" + "\n".join(fm) + "\n---\n\n본문 마커\n")

    def test_silent_when_no_active_tasks(self):
        self.assertEqual(self.context(), "")

    def test_silent_when_only_done_tasks(self):
        self.task("TASK-001", "DONE", phase="5")
        self.assertEqual(self.context(), "")

    def test_single_active_task_injects_full_context(self):
        self.task("TASK-001", "ACTIVE")
        ctx = self.context()
        self.assertIn("TASK-001", ctx)
        self.assertIn("본문 마커", ctx)

    def test_several_active_tasks_are_listed_without_bodies(self):
        self.task("TASK-001", "ACTIVE")
        self.task("TASK-002", "ACTIVE")
        ctx = self.context()
        self.assertIn("TASK-001", ctx)
        self.assertIn("TASK-002", ctx)
        self.assertNotIn("본문 마커", ctx)

    def test_blocked_task_is_marked_and_not_to_be_resumed(self):
        self.task("TASK-001", "BLOCKED", blocked_reason="선행 대기", unblock_condition="TASK-002 머지")
        ctx = self.context()
        self.assertIn("차단", ctx)
        self.assertIn("선행 대기", ctx)
        self.assertIn("진행하지 않습니다", ctx)

    def test_never_blocks_session_start_on_broken_state(self):
        self.project.write("memory-bank/TASK-001/activeContext.md", "---\n: : :\n\x00\x01")
        self.assertEqual(self.project.run(SESSION_START).returncode, 0)

    def test_injected_context_is_length_capped(self):
        self.task("TASK-001", "ACTIVE")
        self.project.write(
            "memory-bank/TASK-001/activeContext.md",
            "---\ntask_id: TASK-001\nphase: \"3\"\nstatus: ACTIVE\n---\n" + ("긴 본문 " * 5000),
        )
        ctx = self.context()
        self.assertLess(len(ctx), 7000)
        self.assertIn("길이 제한", ctx)


if __name__ == "__main__":
    unittest.main()
