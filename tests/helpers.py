"""테스트 공용 도구 — 임시 git 저장소를 만들고 스크립트를 그 안에서 실행한다.

스크립트들은 `git rev-parse --show-toplevel` 로 저장소 루트를 찾는다. 그래서 테스트도
실제 저장소를 흉내 내는 임시 git 저장소를 만들어 CWD 로 두고 서브프로세스로 실행한다.
스크립트 함수를 직접 import 하면 이 루트 탐색을 우회하게 되어, 실제로 쓰이는 경로를
검사하지 못한다.

전역 git 설정(workflow.baseBranch 등)이 테스트에 새어 들어오지 않도록 격리한다.
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

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _git_env(home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "HOME": str(home),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            # 스크립트 디렉터리에 __pycache__ 를 만들지 않는다
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return env


class Project:
    """임시 git 저장소 하나."""

    def __init__(self, parent: Path | None = None) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="wf-test-", dir=parent)).resolve()
        self.root = self._tmp / "repo"
        self.root.mkdir()
        self.env = _git_env(self._tmp)
        self.git("init", "-q", "-b", "main")
        self.write("README.md", "# fixture\n")
        self.commit("chore: init")

    def cleanup(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    # --- 파일 ---

    def path(self, rel: str) -> Path:
        return self.root / rel

    def write(self, rel: str, content: str = "") -> Path:
        p = self.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def write_json(self, rel: str, data: object) -> Path:
        return self.write(rel, json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    # --- git ---

    def git(self, *args: str) -> str:
        out = subprocess.run(
            ["git", *args], cwd=self.root, env=self.env, capture_output=True, text=True
        )
        if out.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} 실패: {out.stderr.strip()}")
        return out.stdout.strip()

    def commit(self, message: str = "chore: fixture") -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    # --- 스크립트 실행 ---

    def run(
        self, script: str, *args: str, stdin: str | None = None
    ) -> subprocess.CompletedProcess:
        """scripts/ 아래 스크립트를 이 저장소를 CWD 로 해서 실행한다."""
        return subprocess.run(
            [sys.executable, str(SCRIPTS / script), *args],
            cwd=self.root,
            env=self.env,
            input=stdin if stdin is not None else "",
            capture_output=True,
            text=True,
        )

    def run_json(self, script: str, *args: str) -> tuple[int, dict]:
        out = self.run(script, *args)
        try:
            return out.returncode, json.loads(out.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"JSON 출력이 아니다 (exit {out.returncode}): {exc}\n"
                f"stdout={out.stdout!r}\nstderr={out.stderr!r}"
            ) from exc


class ProjectTestCase(unittest.TestCase):
    """각 테스트마다 새 임시 저장소를 만든다."""

    def setUp(self) -> None:
        self.project = Project()
        self.addCleanup(self.project.cleanup)
