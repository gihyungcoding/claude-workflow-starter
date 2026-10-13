#!/usr/bin/env python3
"""산출물 경로가 규약을 지키는지 검사한다. (docs/workflow/artifact-paths.md)

왜 필요한가
-----------
경로 규약을 문서에만 적어두면 지켜지지 않는다. 원본 저장소에서 실제로 벌어진 일:
  - workflow_design/memory-bank/ 에 파일 7개가 새어 들어감 (CWD 착각)
  - TASK-task-0021 같은 이중접두 167건
  - 05_chain_data_plan/, 06_chain_data_dev/ 등 오타 디렉터리 3개가 각 1파일씩 품고 생존
전부 "문서에 쓰여 있었지만 막지 않았기 때문에" 생긴 것이다. 이 훅은 쓰기를 실제로 차단한다.

화이트리스트인 이유
------------------
원본은 금지 패턴 목록(블랙리스트)이라 아무도 예상 못 한 새 오타를 잡지 못했다.
여기서는 허용 목록에 없으면 거부한다.

두 가지 모드
-----------
1. PreToolUse 훅 — stdin 으로 Claude Code 훅 페이로드를 받아 Write/Edit 대상 경로를 검사
2. CLI        — 파일 경로를 인자로 받거나 --all 로 저장소 전체 검사 (pre-commit / CI)

    python scripts/hooks/check_artifact_paths.py --all
    python scripts/hooks/check_artifact_paths.py path/to/file.md
    echo '<hook payload>' | python scripts/hooks/check_artifact_paths.py --hook

exit code
---------
    0  위반 없음
    1  위반 (CLI 모드)
    2  위반 (훅 모드 — Claude Code 가 도구 호출을 차단하고 stderr 를 모델에 전달)

이 검사가 못 잡는 것
-------------------
경로 문자열만 본다. 파일 내용, 태스크가 tasks.json 에 실재하는지, 체크포인트가 올바른
Phase 에서 저장됐는지는 보지 않는다.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _utils import (  # noqa: E402
    ALL_CHECKPOINTS,
    ALLOWED_DOC_DIRS,
    ALLOWED_WORKFLOW_DIRS,
    DOC_NAME_EXEMPT,
    KEBAB_RE,
    TASK_ID_RE,
    repo_root,
)

# 레거시(v1) 파일명도 허용한다 — 이미 만들어진 프로젝트의 체크포인트가 걸리지 않게.
# 새로 쓸 이름은 _utils.CHECKPOINTS 의 6개뿐이고, 그건 스킬이 지시한다.
ALLOWED_CP_FILENAMES = {name for _, name, _ in ALL_CHECKPOINTS}
ALLOWED_CP_DIRS = {phase for phase, _, _ in ALL_CHECKPOINTS}

#: v1 재시도 체크포인트: CP-2.2_canonical-scenarios_retry1.md
#: v2 에서는 같은 파일을 덮어쓰고 attempts 에 한 줄을 남긴다. 기존 파일 호환을 위해 허용만 한다.
RETRY_SUFFIX_RE = re.compile(r"_retry\d+(?=\.md$)")

DOC_REF = "docs/workflow/artifact-paths.md"


def violations_for(rel: str) -> list[str]:
    """저장소 기준 상대경로 하나를 검사한다. 위반 사유 목록을 반환."""
    rel = rel.replace("\\", "/").lstrip("./")
    parts = rel.split("/")
    problems: list[str] = []

    # --- 1. memory-bank 오배치 ---
    for i, part in enumerate(parts[:-1]):
        if part in ("memory-bank", "memory_bank") and i > 0:
            problems.append(
                f"memory-bank 오배치: '{rel}' — memory-bank 는 저장소 루트에만 둔다. "
                f"쉘에서는 $(git rev-parse --show-toplevel) 기준 절대경로를 쓴다. ({DOC_REF} §3)"
            )
            break
    if parts[0] == "memory_bank":
        problems.append(f"디렉터리명 오타: '{rel}' — 'memory-bank' (하이픈) 이다.")

    # --- 2. 이중접두 ---
    for part in parts:
        if re.search(r"(TASK-)+(task-|TASK-)", part, re.IGNORECASE):
            problems.append(
                f"이중접두: '{part}' — 접두사는 하나만 쓴다 (TASK-001). ({DOC_REF} §1)"
            )
            break

    # --- 3. memory-bank 내부 ---
    if parts[0] == "memory-bank" and len(parts) >= 2:
        if parts[1] not in ("index.md", "templates") and not parts[1].startswith("."):
            task_id = parts[1]
            if not TASK_ID_RE.match(task_id):
                problems.append(
                    f"태스크 폴더명이 규약에 맞지 않는다: '{task_id}' — "
                    f"'TASK-' + 숫자 3자리 이상. ({DOC_REF} §1)"
                )
            # 체크포인트 경로
            if len(parts) >= 5 and parts[2] == "checkpoints":
                phase_dir, filename = parts[3], parts[4]
                if phase_dir not in ALLOWED_CP_DIRS:
                    problems.append(
                        f"체크포인트 phase 디렉터리가 허용 목록에 없다: '{phase_dir}' — "
                        f"{sorted(ALLOWED_CP_DIRS)} 중 하나여야 한다. ({DOC_REF} §3)"
                    )
                canonical = RETRY_SUFFIX_RE.sub("", filename)
                if canonical not in ALLOWED_CP_FILENAMES:
                    problems.append(
                        f"체크포인트 파일명이 고정 목록에 없다: '{filename}' — "
                        f"자유 작명 금지. 허용 목록은 {DOC_REF} §3 참조."
                    )

    # --- 4. workflow_design 내부 ---
    if parts[0] == "workflow_design" and len(parts) >= 2:
        top = parts[1]
        if not top.startswith(".") and "." not in top:
            if top not in ALLOWED_WORKFLOW_DIRS:
                problems.append(
                    f"workflow_design 하위 디렉터리가 허용 목록에 없다: '{top}' — "
                    f"{sorted(ALLOWED_WORKFLOW_DIRS)} 중 하나여야 한다. ({DOC_REF} §2)"
                )

    # --- 5. docs 내부 ---
    if parts[0] == "docs" and len(parts) >= 2:
        top = parts[1]
        # docs/README.md 처럼 최상위 파일은 허용한다
        if "." not in top and not top.startswith("."):
            if top not in ALLOWED_DOC_DIRS:
                problems.append(
                    f"docs 하위 디렉터리가 허용 목록에 없다: '{top}' — "
                    f"{sorted(ALLOWED_DOC_DIRS)} 중 하나여야 한다. (docs/README.md)"
                )
        # 파일명은 케밥케이스. 원본 저장소는 케밥·스네이크가 섞여 찾기 어려웠다.
        name = parts[-1]
        if "." in name and name not in DOC_NAME_EXEMPT and not name.startswith("."):
            # ADR 은 대문자 접두사를 쓴다
            if not name.startswith("ADR-") and not KEBAB_RE.match(name):
                problems.append(
                    f"문서 파일명이 케밥케이스가 아니다: '{name}' — "
                    "소문자와 하이픈만 쓴다 (store-search-permission.md). (docs/README.md 작성 규약)"
                )

    return problems


def scan_repo() -> dict[str, list[str]]:
    """저장소 전체(git 추적 파일)를 검사한다."""
    import subprocess

    root = repo_root()
    try:
        # 추적 파일 + 아직 add 하지 않은 새 파일.
        # 미추적을 빼면 방금 만든 파일이 검사되지 않아 커밋 직전까지 위반이 드러나지 않는다.
        tracked = subprocess.run(
            ["git", "ls-files"], capture_output=True, text=True, cwd=root, check=True
        )
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, cwd=root, check=True,
        )
        files = tracked.stdout.splitlines() + untracked.stdout.splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        files = [
            str(p.relative_to(root))
            for p in root.rglob("*")
            if p.is_file() and ".git" not in p.parts
        ]

    found = {}
    for rel in files:
        problems = violations_for(rel)
        if problems:
            found[rel] = problems
    return found


def hook_mode() -> int:
    """PreToolUse 훅. stdin 으로 페이로드를 받는다."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # 페이로드를 못 읽으면 통과시킨다 — 훅이 작업을 막아서는 안 된다

    tool_input = payload.get("tool_input") or {}
    target = tool_input.get("file_path") or tool_input.get("path") or ""
    if not target:
        return 0

    root = repo_root()
    try:
        rel = str(Path(target).resolve().relative_to(root))
    except ValueError:
        return 0  # 저장소 밖 — 이 훅의 관심사가 아니다

    problems = violations_for(rel)
    if not problems:
        return 0

    reason = "산출물 경로 규약 위반:\n" + "\n".join(f"  - {p}" for p in problems)
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            },
            ensure_ascii=False,
        )
    )
    print(reason, file=sys.stderr)
    return 2


def main() -> int:
    args = sys.argv[1:]

    if "--hook" in args:
        return hook_mode()

    if "--all" in args:
        found = scan_repo()
        if not found:
            print("경로 규약 위반 없음")
            return 0
        for rel, problems in sorted(found.items()):
            print(f"✗ {rel}")
            for problem in problems:
                print(f"    {problem}")
        print(f"\n위반 {len(found)}건")
        return 1

    if not args:
        print(__doc__.split("\n\n")[0], file=sys.stderr)
        print("\n사용: --all | --hook | <파일 경로...>", file=sys.stderr)
        return 1

    failed = False
    for arg in args:
        problems = violations_for(arg)
        if problems:
            failed = True
            print(f"✗ {arg}")
            for problem in problems:
                print(f"    {problem}")
    if not failed:
        print("경로 규약 위반 없음")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
