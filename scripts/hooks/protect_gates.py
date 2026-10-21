#!/usr/bin/env python3
"""PreToolUse 훅 — 게이트를 통과시키려고 게이트 자체를 고치는 수정을 사람에게 묻는다.

왜 필요한가
-----------
에이전트가 검사에 막히면 코드를 고치는 대신 검사를 바꾸는 쪽이 쉬울 때가 있다.
린트 설정에서 규칙을 끄고, 아키텍처 제약을 지우고, 실패하는 테스트의 단언을 약화한다.
`wf-develop` 은 "테스트를 고쳐서 통과시키기"를 금지하고 절대 규칙 7 은 "제약을 어기려면
제약을 먼저 고친다(ADR 과 함께)"고 하지만, 둘 다 문서일 뿐 막는 것이 없었다.

무엇을 보호하나
---------------
    constraints   docs/architecture/constraints.yaml
    gate-config   린트·타입·포맷 설정 (eslint, tsconfig, prettier, biome, ruff, mypy,
                  checkstyle, .pre-commit-config.yaml)
    approved-test HITL#2 에서 승인된 Red 테스트 (TEST_<ID>.json 의 test_files)

언제 묻나 — Phase 3·4 의 ACTIVE 태스크가 있을 때만
------------------------------------------------
검사를 약화하고 싶은 유혹은 구현(Phase 3)과 검증(Phase 4) 중에 생긴다. 그 밖에서는
정당한 수정이 대부분이다 — /wf-init 의 제약 작성, ADR 과 함께하는 제약 변경, Red 단계의
테스트 작성. 항상 묻는 훅은 사람이 승인 버튼을 습관적으로 누르게 만들어 무력해진다.

차단(deny)이 아니라 확인(ask)인 이유
----------------------------------
정당한 경우가 있다 — Phase 3 에서 리팩토링으로 테스트 파일을 옮기거나, 제약 glob 이
틀려 있었음을 발견한 경우. 막으면 사람이 훅을 끄게 되고, 묻기만 하면 사람이 판단한다.
이 훅이 하는 일은 수정이 *조용히* 일어나지 않게 하는 것이다.

새 파일을 만드는 것은 묻지 않는다 (Write 로 새로 만드는 설정, 새 테스트).

이 검사가 못 잡는 것
-------------------
- Edit/Write/NotebookEdit 만 본다. `sed -i`, `git checkout`, 셸 리다이렉션 같은 Bash 로
  하는 수정은 보지 못한다. 그것까지 막으려면 Bash 명령을 해석해야 하는데 우회가 쉽고
  오탐이 많아 넣지 않았다.
- 보호 목록은 아래 상수다. 프로젝트가 쓰는 다른 설정 파일(예: 빌드 도구의 린트 플러그인
  설정)은 GATE_CONFIG_PATTERNS 에 추가해야 한다. build.gradle 같은 빌드 파일은 의존성
  추가로 정당하게 자주 바뀌므로 넣지 않았다.
- 훅 자신과 게이트 스크립트(scripts/)는 보호하지 않는다. 스타터를 유지보수하는 일이
  바로 그 파일을 고치는 일이다.
- 어떤 태스크가 어느 Phase 인지는 activeContext.md 의 기록을 믿는다.
- 심볼릭 링크는 resolve() 로 실제 대상을 따라가 잡지만, 하드링크는 같은 파일이어도
  다른 경로 이름이라 보지 못한다.

exit code 는 항상 0 이다. 훅이 고장 나서 작업을 막아서는 안 된다.
"""

from __future__ import annotations

import fnmatch
import json
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _utils import artifact_path, constraints_path, list_tasks, load_json, repo_root  # noqa: E402

#: 이 Phase 의 ACTIVE 태스크가 있을 때만 묻는다.
GUARDED_PHASES = {"3", "4"}

#: 린트·타입·포맷 설정. 파일명(basename) 기준 glob.
GATE_CONFIG_PATTERNS = (
    ".eslintrc",
    ".eslintrc.*",
    "eslint.config.*",
    ".prettierrc",
    ".prettierrc.*",
    "prettier.config.*",
    "biome.json",
    "biome.jsonc",
    "tsconfig.json",
    "tsconfig.*.json",
    "ruff.toml",
    ".ruff.toml",
    "mypy.ini",
    ".mypy.ini",
    "checkstyle*.xml",
    ".pre-commit-config.yaml",
)


def path_key(value: str) -> str:
    """경로 비교용 키. 유니코드 정규화(NFC) 후 대소문자를 접는다.

    macOS(APFS)·Windows 기본 설정은 대소문자를 구분하지 않고, APFS 는 유니코드 정규화
    형태(NFC/NFD)도 구분하지 않는다. `Docs/Architecture/Constraints.YAML` 은 같은 파일인데
    resolve() 는 표기를 그대로 남기므로, 문자열 그대로 비교하면 보호를 우회할 수 있다.
    대소문자를 구분하는 파일시스템에서는 다른 파일을 잘못 묻게 될 수 있다 — 불필요한 확인
    한 번이 비용이고, 반대 방향의 실패는 보호가 뚫리는 것이라 보수적으로 접는다.
    """
    return unicodedata.normalize("NFC", value).casefold()


def matches_gate_config(name: str) -> bool:
    key = path_key(name)
    return any(fnmatch.fnmatchcase(key, path_key(pattern)) for pattern in GATE_CONFIG_PATTERNS)


def guarded_tasks() -> list[dict]:
    return [t for t in list_tasks() if t["status"] == "ACTIVE" and t["phase"] in GUARDED_PHASES]


def approved_test_files(task_id: str) -> set[str]:
    """HITL#2 에서 승인된 Red 테스트 경로. 승인 전이거나 읽을 수 없으면 빈 집합."""
    path = artifact_path(task_id, "2b")
    if path is None:
        return set()
    data, err = load_json(path)
    if err or not isinstance(data, dict):
        return set()
    if (data.get("human_review") or {}).get("approved") is not True:
        return set()
    files = data.get("test_files") or []
    return {str(f).replace("\\", "/") for f in files if isinstance(f, str)}


def is_approved_test(rel: str, approved: set[str]) -> bool:
    # 항목이 '/' 로 끝나면 디렉터리로 본다
    key = path_key(rel)
    for entry in approved:
        a = path_key(entry)
        if key == a or (a.endswith("/") and key.startswith(a)):
            return True
    return False


def classify(rel: str, tasks: list[dict]) -> tuple[str, dict] | None:
    """보호 대상이면 (종류, 근거가 된 태스크). 아니면 None."""
    root = repo_root()
    try:
        constraints_rel = str(constraints_path().relative_to(root))
    except ValueError:
        constraints_rel = "docs/architecture/constraints.yaml"

    if path_key(rel) == path_key(constraints_rel):
        return "constraints", tasks[0]

    if matches_gate_config(rel.rsplit("/", 1)[-1]):
        return "gate-config", tasks[0]

    for task in tasks:
        if is_approved_test(rel, approved_test_files(task["task_id"])):
            return "approved-test", task
    return None


def reason_for(kind: str, rel: str, task: dict) -> str:
    where = f"{task['task_id']} 가 Phase {task['phase']} 에 있다"
    if kind == "constraints":
        return (
            f"아키텍처 제약 파일 수정: {rel}\n"
            f"  {where}. 구현·검증 중에 제약을 바꾸면 위반을 고치지 않고 통과시킬 수 있다.\n"
            "  제약이 틀렸다면 ADR 과 함께 고친다(절대 규칙 7). 위반을 피하려는 수정이면 코드를 고친다."
        )
    if kind == "gate-config":
        return (
            f"린트·타입·포맷 설정 수정: {rel}\n"
            f"  {where}. 규칙을 끄거나 범위를 줄여 통과시키는 수정이 아닌지 확인한다.\n"
            "  이 태스크의 범위에 필요한 변경이면 승인한다."
        )
    return (
        f"HITL#2 에서 승인된 테스트 수정: {rel}\n"
        f"  {where}. 단언 약화·skip·기대값 변경으로 통과시키는 것은 금지다(wf-develop).\n"
        "  시나리오 자체가 틀렸다면 Phase 2a/2b 로 되돌아가 다시 승인받는다."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    try:
        tool_input = payload.get("tool_input") or {}
        target = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path") or ""
        if not target:
            return 0

        root = repo_root().resolve()
        path = Path(target)
        try:
            rel = str(path.resolve().relative_to(root))
        except ValueError:
            return 0  # 저장소 밖
        if not path.exists():
            return 0  # 새 파일 만들기는 묻지 않는다

        tasks = guarded_tasks()
        if not tasks:
            return 0

        hit = classify(rel, tasks)
        if hit is None:
            return 0
        kind, task = hit

        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "ask",
                        "permissionDecisionReason": reason_for(kind, rel, task),
                    }
                },
                ensure_ascii=False,
            )
        )
    except Exception as exc:  # noqa: BLE001 — 훅은 작업을 막지 않는다
        print(f"[protect_gates] 판정하지 못했습니다: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
