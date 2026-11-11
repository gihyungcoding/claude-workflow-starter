"""check_sync.py — 스타터와 프로젝트의 어긋남, 그리고 반영이 유실되는 세 경로.

이 점검은 '검사하지 못한 것을 통과로 보고하지 않는다'를 지켜야 한다. 그래서 정상 경로뿐 아니라
검사할 수 없는 경우(원격 없음 · gh 없음)와, 점검이 침묵해도 되는 경우(수용 · 스쿼시)를
함께 확인한다.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import SCRIPTS, Project, ProjectTestCase

sys.path.insert(0, str(SCRIPTS))
import check_sync  # noqa: E402

SKILL = ".claude/skills/wf-x/SKILL.md"
OLD_DATE = "2026-01-01T00:00:00"


class SyncCase(ProjectTestCase):
    """self.project 가 스타터(main), self.proj 가 프로젝트(develop). 둘 다 원격(bare)에 올려 둔다.

    저장소 두 개와 원격을 만드는 데 1.6초가 걸려서(테스트 46개 × ) 클래스마다 한 번만 만들어 두고
    테스트마다 복사한다.
    """

    _templates: dict = {}
    _nogh_bin: Path | None = None

    @staticmethod
    def _build(repo: Project, branch: str) -> None:
        bare = repo.root.parent / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], env=repo.env, check=True)
        repo.git("remote", "add", "origin", str(bare))
        repo.git("push", "-q", "-u", "origin", branch)
        repo.git("remote", "set-head", "origin", branch)

    @classmethod
    def setUpClass(cls):
        if "starter" not in SyncCase._templates:
            starter, proj = Project(), Project()
            proj.git("branch", "-m", "develop")
            cls._build(starter, "main")
            cls._build(proj, "develop")
            SyncCase._templates = {"starter": starter, "project": proj}

    @classmethod
    def tearDownClass(cls):
        pass  # 템플릿은 모든 SyncCase 서브클래스가 공유한다 — 프로세스 끝에서 지운다

    def setUp(self):
        # ProjectTestCase.setUp 이 만드는 빈 저장소는 쓰지 않는다 — 복사본으로 바꾼다
        self.starter = Project.copy_of(SyncCase._templates["starter"])
        self.proj = Project.copy_of(SyncCase._templates["project"])
        self.project = self.starter
        for repo in (self.starter, self.proj):
            self.addCleanup(repo.cleanup)
            repo.git("remote", "set-url", "origin", str(repo.root.parent / "origin.git"))

    # --- 도구 ---

    def publish(self, repo: Project, branch: str) -> None:
        repo.git("push", "-q", "origin", branch)

    def both_have(self, rel: str, text: str) -> None:
        for repo, branch in ((self.starter, "main"), (self.proj, "develop")):
            repo.write(rel, text)
            repo.commit(f"feat: {rel}")
            self.publish(repo, branch)

    def edit(self, repo: Project, branch: str, rel: str, text: str) -> None:
        repo.write(rel, text)
        repo.commit(f"fix: {rel} 수정")
        self.publish(repo, branch)

    def env_without_gh(self) -> dict:
        """PATH 에 git 만 둔다. 호스트에 gh 가 있는지 · 로그인했는지에 테스트가 기대지 않게 하고,
        임시 저장소(GitHub 가 아님)에서 항상 실패할 gh 를 매번 띄우는 비용도 없앤다."""
        if SyncCase._nogh_bin is None:
            SyncCase._nogh_bin = Path(tempfile.mkdtemp(prefix="wf-nogh-"))
            os.symlink(shutil.which("git"), SyncCase._nogh_bin / "git")
        return dict(self.starter.env, PATH=str(SyncCase._nogh_bin))

    def sync(self, *args: str, env: dict | None = None):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "check_sync.py"), "--project", str(self.proj.root),
             "--starter", str(self.starter.root), *args],
            capture_output=True, text=True, env=env or self.env_without_gh(), cwd=self.starter.root)

    def report(self, *args: str) -> tuple[int, dict]:
        out = self.sync("--json", *args)
        try:
            return out.returncode, json.loads(out.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"JSON 이 아니다: {exc}\n{out.stdout}\n{out.stderr}") from exc

    def files(self, *args: str) -> dict:
        return self.report(*args)[1]["files"]


class FileComparisonTest(SyncCase):
    def test_identical_files_are_counted_and_quiet(self):
        self.both_have(SKILL, "v1\n")
        code, rep = self.report()
        f = rep["files"]
        self.assertEqual((f["same"], f["project_behind"], f["starter_behind"], f["diverged"]), (1, [], [], []))
        self.assertFalse(rep["drifted"])

    def test_project_behind_when_the_starter_moved_on(self):
        self.both_have(SKILL, "v1\n")
        self.edit(self.starter, "main", SKILL, "v2\n")
        self.assertEqual([i["path"] for i in self.files()["project_behind"]], [SKILL])

    def test_starter_behind_when_the_project_moved_on(self):
        self.both_have(SKILL, "v1\n")
        self.edit(self.proj, "develop", SKILL, "v2 project\n")
        self.assertEqual([i["path"] for i in self.files()["starter_behind"]], [SKILL])

    def test_diverged_when_both_edited_the_same_base_differently(self):
        self.both_have(SKILL, "v1\n")
        self.edit(self.starter, "main", SKILL, "starter edit\n")
        self.edit(self.proj, "develop", SKILL, "project edit\n")
        self.assertEqual([i["path"] for i in self.files()["diverged"]], [SKILL])

    def test_a_file_the_project_already_caught_up_on_is_not_behind(self):
        # 스타터가 v2 로 갔다가 프로젝트도 v2 를 받았다 — 이력이 달라도 같은 내용이면 동일하다
        self.both_have(SKILL, "v1\n")
        self.edit(self.starter, "main", SKILL, "v2\n")
        self.edit(self.proj, "develop", SKILL, "v2\n")
        f = self.files()
        self.assertEqual((f["same"], f["project_behind"], f["diverged"]), (1, [], []))

    def test_files_present_on_one_side_only(self):
        self.edit(self.starter, "main", "scripts/only_starter.py", "x\n")
        self.edit(self.proj, "develop", "scripts/only_project.py", "x\n")
        f = self.files()
        self.assertEqual((f["only_starter"], f["only_project"]), (["scripts/only_starter.py"], ["scripts/only_project.py"]))

    def test_uncommitted_working_tree_changes_are_not_compared(self):
        self.both_have(SKILL, "v1\n")
        self.starter.write(SKILL, "uncommitted\n")
        self.assertEqual(self.files()["project_behind"], [])

    def test_unpushed_commits_on_the_default_branch_are_not_compared(self):
        self.both_have(SKILL, "v1\n")
        self.proj.write(SKILL, "local only\n")
        self.proj.commit("fix: 푸시 안 함")
        self.assertEqual(self.files()["starter_behind"], [])

    def test_only_shared_roots_are_compared(self):
        self.both_have("CLAUDE.md", "starter\n")
        self.edit(self.proj, "develop", "CLAUDE.md", "project specific\n")
        self.edit(self.proj, "develop", "src/app.py", "x\n")
        f = self.files()
        self.assertEqual(f["same"] + sum(len(f[k]) for k in ("project_behind", "starter_behind", "diverged")), 0)

    def test_excluded_paths_are_ignored(self):
        for rel in (".claude/settings.local.json", ".claude/worktrees/x/a.md", "scripts/__pycache__/m.pyc"):
            self.edit(self.starter, "main", rel, "s\n")
            self.edit(self.proj, "develop", rel, "p\n")
        f = self.files()
        self.assertEqual((f["same"], f["diverged"], f["only_starter"], f["only_project"]), (0, [], [], []))

    def test_drift_alone_does_not_fail_but_strict_does(self):
        self.both_have(SKILL, "v1\n")
        self.edit(self.starter, "main", SKILL, "v2\n")
        self.assertEqual(self.sync().returncode, 0)
        self.assertEqual(self.sync("--strict").returncode, 1)


class AcceptedDifferencesTest(SyncCase):
    def setUp(self):
        super().setUp()
        self.both_have(SKILL, "v1\n")
        self.edit(self.proj, "develop", SKILL, "v1 + TASK-008 사례 인용\n")

    def accept(self, reason: str = "프로젝트 사례를 인용한 문장"):
        return self.sync("--accept", SKILL, "--reason", reason)

    def commit_acceptance(self):
        self.proj.commit("chore: 수용")
        self.publish(self.proj, "develop")

    def test_accepting_records_both_sides_content_and_silences_the_difference(self):
        self.assertEqual(self.accept().returncode, 0)
        self.commit_acceptance()
        code, rep = self.report("--strict")
        f = rep["files"]
        self.assertEqual((f["accepted"][0]["path"], f["starter_behind"]), (SKILL, []))
        self.assertEqual(code, 0, "수용한 차이는 --strict 에서도 실패가 아니다")

    def test_acceptance_is_not_visible_until_committed(self):
        self.accept()
        self.assertEqual([i["path"] for i in self.files()["starter_behind"]], [SKILL])

    def test_acceptance_expires_when_the_project_file_changes_again(self):
        self.accept(); self.commit_acceptance()
        self.edit(self.proj, "develop", SKILL, "v1 + 다른 변경\n")
        code, rep = self.report()
        self.assertEqual([i["path"] for i in rep["files"]["accepted_stale"]], [SKILL])
        self.assertEqual(code, 1, "수용이 풀린 것은 유실 위험으로 본다")

    def test_acceptance_expires_when_the_starter_file_changes_too(self):
        self.accept(); self.commit_acceptance()
        self.edit(self.starter, "main", SKILL, "v2 starter\n")
        self.assertEqual([i["path"] for i in self.files()["accepted_stale"]], [SKILL])

    def test_acceptance_without_a_reason_is_refused(self):
        out = self.accept(reason="   ")
        self.assertEqual(out.returncode, 2)
        self.assertFalse((self.proj.root / check_sync.ACCEPTED_PATH).exists())

    def test_blank_reason_edited_into_the_file_is_flagged(self):
        self.accept();
        path = self.proj.root / check_sync.ACCEPTED_PATH
        data = json.loads(path.read_text(encoding="utf-8"))
        data["accepted"][0]["reason"] = " "
        path.write_text(json.dumps(data), encoding="utf-8")
        self.commit_acceptance()
        self.assertEqual([i["path"] for i in self.files()["accepted_invalid"]], [SKILL])

    def test_cannot_accept_what_is_not_different_or_not_shared(self):
        self.both_have(".claude/skills/wf-y/SKILL.md", "same\n")
        self.assertEqual(self.sync("--accept", ".claude/skills/wf-y/SKILL.md", "--reason", "x").returncode, 2)
        self.assertEqual(self.sync("--accept", "src/app.py", "--reason", "x").returncode, 2)

    def test_record_is_not_compared_as_a_shared_file(self):
        self.accept(); self.commit_acceptance()
        f = self.files()
        self.assertEqual(f["only_project"], [])

    def test_corrupt_record_is_reported_as_a_problem_not_silently_ignored(self):
        self.proj.write(check_sync.ACCEPTED_PATH, "{broken")
        self.commit_acceptance()
        code, rep = self.report()
        self.assertIn("읽을 수 없다", rep["files"]["problem"])
        self.assertEqual(code, 1)

    def test_accepting_a_second_file_keeps_the_first(self):
        self.both_have(".claude/skills/wf-z/SKILL.md", "a\n")
        self.edit(self.proj, "develop", ".claude/skills/wf-z/SKILL.md", "b\n")
        self.accept()
        self.assertEqual(self.sync("--accept", ".claude/skills/wf-z/SKILL.md", "--reason", "다른 이유").returncode, 0)
        data = json.loads((self.proj.root / check_sync.ACCEPTED_PATH).read_text(encoding="utf-8"))
        self.assertEqual(len(data["accepted"]), 2)


class UnpushedWorkTest(SyncCase):
    def branch_with_commit(self, repo: Project, name: str, date: str | None = None) -> None:
        repo.git("switch", "-q", "-c", name)
        repo.write(f"notes/{name.replace('/', '_')}.md", "x\n")
        env = dict(repo.env)
        if date:
            env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        subprocess.run(["git", "add", "-A"], cwd=repo.root, env=env, check=True)
        subprocess.run(["git", "commit", "-q", "-m", f"chore: {name}"], cwd=repo.root, env=env, check=True)
        repo.git("switch", "-q", repo.git("rev-parse", "--abbrev-ref", "origin/HEAD").split("/", 1)[1])

    def unpushed(self, side: str = "starter") -> dict:
        return self.report()[1][side]["unpushed"]

    def test_old_local_only_branch_is_a_loss_risk(self):
        self.branch_with_commit(self.starter, "fix/forgotten", OLD_DATE)
        code, rep = self.report()
        b = rep["starter"]["unpushed"]["branches"][0]
        self.assertEqual((b["branch"], b["commits"], b["stale"]), ("fix/forgotten", 1, True))
        self.assertEqual(code, 1)

    def test_fresh_local_only_branch_is_just_reported(self):
        self.branch_with_commit(self.starter, "feat/in-progress")
        code, rep = self.report()
        b = rep["starter"]["unpushed"]["branches"][0]
        self.assertEqual((b["stale"], code), (False, 0))

    def test_stale_days_threshold_is_adjustable(self):
        self.branch_with_commit(self.starter, "feat/in-progress")
        self.assertEqual(self.report("--stale-days", "0")[0], 1)

    def test_pushed_branch_is_not_reported(self):
        self.branch_with_commit(self.starter, "feat/pushed", OLD_DATE)
        self.starter.git("push", "-q", "origin", "feat/pushed")
        self.assertEqual(self.unpushed()["branches"], [])

    def test_squash_merged_branch_is_not_a_loss(self):
        # 스쿼시·리베이스 머지: 커밋은 원격에 없지만 같은 패치가 기본 브랜치에 있다
        self.branch_with_commit(self.starter, "feat/squashed", OLD_DATE)
        self.starter.git("cherry-pick", "feat/squashed")
        self.publish(self.starter, "main")
        self.assertEqual(self.unpushed()["branches"], [])

    def test_default_branch_ahead_of_its_remote_is_reported(self):
        self.proj.write("notes/x.md", "x\n")
        env = dict(self.proj.env, GIT_AUTHOR_DATE=OLD_DATE, GIT_COMMITTER_DATE=OLD_DATE)
        subprocess.run(["git", "add", "-A"], cwd=self.proj.root, env=env, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "chore: 푸시 안 함"], cwd=self.proj.root, env=env, check=True)
        names = [b["branch"] for b in self.unpushed("project")["branches"]]
        self.assertEqual(names, ["develop"])

    def test_no_remote_means_not_checked_rather_than_clean(self):
        lone = Project()
        self.addCleanup(lone.cleanup)
        u = check_sync.unpushed(lone.root, 2)
        self.assertFalse(u["checked"])
        self.assertIn("원격이 없어", u["why"])

    def test_human_output_marks_the_unchecked_case(self):
        text = self.sync().stdout
        self.assertNotIn("검사하지 못함: 원격이 없어", text)  # 원격이 있으면 이 문구는 나오지 않는다


class PullRequestClassificationTest(unittest.TestCase):
    """classify_prs 는 순수 함수다 — gh 없이 판정 로직을 본다."""

    @staticmethod
    def pr(n, base, head, oid="a" * 40, state="MERGED"):
        return {"number": n, "title": f"PR {n}", "baseRefName": base, "headRefName": head,
                "mergeCommit": {"oid": oid} if oid else None, "state": state}

    def classify(self, merged, open_prs=(), reaches=lambda oid: False, accepted=None):
        return check_sync.classify_prs(list(merged), list(open_prs), "develop", reaches, accepted)

    def test_merge_into_the_default_branch_is_never_lost(self):
        r = self.classify([self.pr(1, "develop", "feature/a")])
        self.assertEqual((r["lost"], r["unknown"]), ([], []))

    def test_merge_into_another_branch_that_never_reached_default_is_lost(self):
        # 실제 사례: #19 는 #18 의 브랜치로 머지됐고 그 내용은 develop 에 들어오지 않았다
        r = self.classify([self.pr(18, "develop", "chore/probe"), self.pr(19, "chore/probe", "chore/hist")])
        self.assertEqual([i["number"] for i in r["lost"]], [19])

    def test_merge_into_another_branch_that_did_reach_default_is_fine(self):
        r = self.classify([self.pr(19, "chore/probe", "chore/hist")], reaches=lambda oid: True)
        self.assertEqual(r["lost"], [])

    def test_unknown_merge_commit_is_unknown_not_lost_and_not_fine(self):
        r = self.classify([self.pr(19, "chore/probe", "x")], reaches=lambda oid: None)
        self.assertEqual(([i["number"] for i in r["unknown"]], r["lost"]), ([19], []))

    def test_missing_merge_commit_is_unknown(self):
        r = self.classify([self.pr(19, "chore/probe", "x", oid="")])
        self.assertEqual([i["number"] for i in r["unknown"]], [19])

    def test_open_pr_whose_base_branch_was_already_merged_is_flagged(self):
        # #19 를 머지하기 전에 잡을 수 있었던 상태: base(#18 브랜치)가 이미 develop 으로 머지됨
        r = self.classify([self.pr(18, "develop", "chore/probe")],
                          [self.pr(19, "chore/probe", "chore/hist", state="OPEN")])
        self.assertTrue(r["stacked"][0]["base_already_merged"])

    def test_open_stacked_pr_with_an_unmerged_base_is_only_informational(self):
        r = self.classify([], [self.pr(19, "chore/probe", "chore/hist", state="OPEN")])
        self.assertFalse(r["stacked"][0]["base_already_merged"])

    def test_open_pr_targeting_the_default_branch_is_not_stacked(self):
        self.assertEqual(self.classify([], [self.pr(5, "develop", "x", state="OPEN")])["stacked"], [])

    def test_accepted_pr_is_moved_out_of_lost_while_the_merge_commit_matches(self):
        merged = [self.pr(19, "chore/probe", "x", oid="b" * 40)]
        r = self.classify(merged, accepted=[{"pr": 19, "merge_commit": "b" * 40, "reason": "#41 로 복구"}])
        self.assertEqual((r["lost"], [i["number"] for i in r["accepted"]]), ([], [19]))

    def test_acceptance_for_a_different_merge_commit_does_not_apply(self):
        merged = [self.pr(19, "chore/probe", "x", oid="b" * 40)]
        r = self.classify(merged, accepted=[{"pr": 19, "merge_commit": "c" * 40, "reason": "r"}])
        self.assertEqual(([i["number"] for i in r["lost"]], r["lost"][0]["accept_stale"]), ([19], True))

    def test_acceptance_without_a_reason_does_not_apply(self):
        merged = [self.pr(19, "chore/probe", "x", oid="b" * 40)]
        r = self.classify(merged, accepted=[{"pr": 19, "merge_commit": "b" * 40, "reason": " "}])
        self.assertEqual([i["number"] for i in r["lost"]], [19])


class WhenPullRequestsCannotBeChecked(SyncCase):
    def test_missing_gh_is_reported_as_not_checked_and_does_not_fail_the_run(self):
        out = self.sync(env=self.env_without_gh())
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("검사하지 못함: gh 가 없다", out.stdout)
        self.assertNotIn("닿지 못한 머지 PR 없음", out.stdout, "확인하지 못한 것을 '없음'으로 쓰면 안 된다")

    def test_missing_gh_is_recorded_in_json(self):
        out = self.sync("--json", env=self.env_without_gh())
        prs = json.loads(out.stdout)["project"]["prs"]
        self.assertEqual((prs["checked"], prs["lost"]), (False, []))
        self.assertIn("gh", prs["why"])


class ArgumentsAndExitCodesTest(SyncCase):
    def test_same_repository_twice_is_refused(self):
        out = subprocess.run([sys.executable, str(SCRIPTS / "check_sync.py"), "--project", str(self.starter.root),
                              "--starter", str(self.starter.root)], capture_output=True, text=True, env=self.env_without_gh())
        self.assertEqual(out.returncode, 2)

    def test_non_repository_is_refused(self):
        out = subprocess.run([sys.executable, str(SCRIPTS / "check_sync.py"), "--project", tempfile.gettempdir(),
                              "--starter", str(self.starter.root)], capture_output=True, text=True, env=self.env_without_gh())
        self.assertEqual(out.returncode, 2)

    def test_human_output_summarises_the_verdict(self):
        self.both_have(SKILL, "v1\n")
        self.assertIn("어긋남 없음", self.sync().stdout)
        self.edit(self.starter, "main", SKILL, "v2\n")
        self.assertIn("파일 어긋남이 있다", self.sync().stdout)


class DocsTest(unittest.TestCase):
    def test_readme_lists_the_script(self):
        readme = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
        self.assertIn("check_sync.py", readme)


def tearDownModule():
    for repo in SyncCase._templates.values():
        repo.cleanup()
    if SyncCase._nogh_bin is not None:
        shutil.rmtree(SyncCase._nogh_bin, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
