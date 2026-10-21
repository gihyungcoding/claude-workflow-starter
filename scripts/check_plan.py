#!/usr/bin/env python3
"""Phase 1 EXIT GATE 를 검사한다 — PLAN 의 경로가 실제로 있는가.

왜 필요한가
-----------
`wf-plan` 의 EXIT GATE 는 "target_files 의 모든 경로가 실재" 를 요구했지만 그것을 확인하는
스크립트가 없었다. Phase 1 을 수행한 에이전트가 스스로 확인했다고 보고하는 구조였다.
조사를 서브에이전트(Explore)에 맡기면 결과를 요약으로 돌려받으므로, 경로를 지어내도 잡을
장치가 없다. 이 스크립트가 그 장치다.

또 그 규칙은 문구 자체가 틀렸다. ticket-booking 11개 태스크에서 target_files 76개 중 44개
(58%)가 **새로 만들 파일**이었다. 그래서 기존 파일은 실재해야 하고, 새 파일은 `new: true` 로
명시한다. 과거 PLAN 은 `change` 문장에 "신규" 라고만 적었으므로 그것도 새 파일로 읽되,
문장으로 표시했다는 사실을 알린다.

검사하는 것
-----------
- PLAN 존재, 파싱, design.inputs/outputs/flows 가 비어 있지 않음, route 값
- target_files: 경로가 하나이고 구체적이다 · 새 파일이 아니면 실재 · 새 파일이면 아직 없음
- reusable · existing_tests: 실재 (재사용하겠다는 것이 없는 파일이면 안 된다)
- architecture.md 가 있으면 architecture_refs 가 채워져 있음
- CP-1.3 체크포인트 존재

사용
----
    python3 scripts/check_plan.py --task-id TASK-001
    python3 scripts/check_plan.py --task-id TASK-001 --json

exit code
---------
    0  통과
    1  위반 있음
    2  인자 오류 / PLAN 을 읽을 수 없음

이 검사가 못 잡는 것
-------------------
경로가 *있는지*만 본다. 그 파일이 이 태스크에 맞는 파일인지, reusable 의 symbol 이 그 파일에
실제로 있는지, 빠뜨린 파일이 없는지는 보지 않는다. 빠뜨린 파일은 Phase 3 의 scope_deviations
로 나중에 드러난다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _utils import (  # noqa: E402
    artifact_path,
    docs_root,
    is_valid_task_id,
    load_json,
    repo_root,
    task_dir,
    task_id_error,
)

ROUTES = ("Backend", "Frontend", "Database")

#: 과거 PLAN 이 새 파일을 표시한 방식 — change 문장
NEW_IN_PROSE_RE = re.compile(r"신규|새로\s*만|새\s*파일|생성|\bnew\b|\bcreate", re.IGNORECASE)

#: 경로 뒤에 붙이는 줄번호·심볼 (Foo.java:42, Foo.java#bar) 는 떼고 본다
SUFFIX_RE = re.compile(r"(:\d+(-\d+)?|#.*)$")


def _path_of(entry: object) -> str:
    if isinstance(entry, dict):
        return str(entry.get("path") or "").strip()
    return str(entry or "").strip()


def split_path(raw: str) -> tuple[str, str]:
    """(경로, 뒤에 붙은 설명). 과거 PLAN 은 경로 뒤에 '— 설명', '(23개 시나리오)' 를 붙였다.

    공백이 든 경로는 다루지 않는다 — 첫 토큰을 경로로 본다.
    """
    head, _, rest = raw.partition(" ")
    return head, rest.strip()


def path_problem(raw: str) -> str:
    """경로 문자열이 구체적인 하나의 경로인가. 아니면 사유."""
    if not raw:
        return "path 가 비어 있다"
    head, _ = split_path(raw)
    # 'a/B.java, C.java' — 둘째 파일은 디렉터리도 없어 존재를 확인할 수 없다
    if head.endswith(",") or "," in head or ";" in head:
        return f"한 항목에 경로가 여럿이다 — 항목을 나눈다: {raw!r}"
    if any(ch in head for ch in "*?[]"):
        return f"glob 이 아니라 구체적인 경로를 쓴다: {raw!r}"
    if head.startswith("/") or ".." in Path(head).parts:
        return f"저장소 기준 상대경로를 쓴다: {raw!r}"
    return ""


def exists(root: Path, raw: str) -> bool:
    head, _ = split_path(raw)
    return (root / SUFFIX_RE.sub("", head)).exists()


def check(task_id: str) -> tuple[list[str], list[str], dict]:
    """(위반, 알림, 집계)"""
    problems: list[str] = []
    notes: list[str] = []
    stats = {"target_existing": 0, "target_new": 0, "target_new_in_prose": 0,
             "reusable": 0, "existing_tests": 0, "unresolved": 0, "exploration": None}

    path = artifact_path(task_id, "1")
    plan, err = load_json(path) if path else (None, "경로 계산 실패")
    if err or not isinstance(plan, dict):
        raise FileNotFoundError(err or "PLAN 이 객체가 아니다")

    root = repo_root()

    design = plan.get("design") or {}
    for key in ("inputs", "outputs", "flows"):
        if not design.get(key):
            problems.append(f"design.{key} 가 비어 있다")
    if plan.get("route") not in ROUTES:
        problems.append(f"route 가 {list(ROUTES)} 중 하나가 아니다: {plan.get('route')!r}")

    ca = plan.get("codebase_analysis") or {}
    stats["exploration"] = (ca.get("exploration") or {}).get("method")
    stats["unresolved"] = len(ca.get("unresolved") or [])

    targets = ca.get("target_files") or []
    if not targets:
        problems.append("codebase_analysis.target_files 가 비어 있다")
    for i, entry in enumerate(targets):
        raw = _path_of(entry)
        where = f"target_files[{i}]"
        bad = path_problem(raw)
        if bad:
            problems.append(f"{where}: {bad}")
            continue

        flag = entry.get("new") if isinstance(entry, dict) else None
        if flag is not None and not isinstance(flag, bool):
            problems.append(f"{where}: new 는 true/false 여야 한다: {flag!r}")
            continue
        present = exists(root, raw)

        if flag is True:
            stats["target_new"] += 1
            if present:
                problems.append(
                    f"{where}: 새 파일로 표시했는데 이미 있다 — {raw}. 기존 파일을 고치는 것이면 "
                    "new 를 빼고, 정말 새 파일이면 다른 경로를 쓴다"
                )
        elif present:
            stats["target_existing"] += 1
        else:
            # new 가 없고 파일도 없다. 과거 PLAN 처럼 change 문장에 '신규' 라고 적었으면
            # 새 파일로 받아준다 — 문장 추론은 없는 파일을 변명하는 데만 쓴다. 있는 파일을
            # 고발하는 데 쓰면 'createTheme()', '좌석 생성 검증' 같은 문장에 오탐이 난다.
            change = str(entry.get("change", "")) if isinstance(entry, dict) else ""
            if flag is None and NEW_IN_PROSE_RE.search(change):
                stats["target_new"] += 1
                stats["target_new_in_prose"] += 1
            else:
                problems.append(
                    f"{where}: 존재하지 않는다 — {raw}. 새로 만들 파일이면 \"new\": true 를 적는다"
                )

    if stats["target_new_in_prose"]:
        notes.append(
            f"새 파일 {stats['target_new_in_prose']}건을 change 문장의 '신규' 로 판단했다 — "
            "\"new\": true 로 적으면 추측하지 않는다"
        )

    for key in ("reusable", "existing_tests"):
        items = ca.get(key) or []
        stats[key] = len(items)
        for i, entry in enumerate(items):
            raw = _path_of(entry)
            bad = path_problem(raw)
            if bad:
                problems.append(f"{key}[{i}]: {bad}")
            elif not exists(root, raw):
                problems.append(f"{key}[{i}]: 존재하지 않는다 — {raw}")

    if (docs_root() / "architecture" / "architecture.md").is_file() and not plan.get("architecture_refs"):
        problems.append("architecture.md 가 있는데 architecture_refs 가 비어 있다")

    cp = task_dir(task_id) / "checkpoints" / "phase1" / "CP-1.3_context-plan.md"
    if not cp.is_file():
        problems.append(f"체크포인트 누락: {cp.name}")

    return problems, notes, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not is_valid_task_id(args.task_id):
        print(task_id_error(args.task_id), file=sys.stderr)
        return 2
    try:
        problems, notes, stats = check(args.task_id)
    except FileNotFoundError as exc:
        print(f"PLAN 을 읽을 수 없다: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"task_id": args.task_id, "ok": not problems, "problems": problems,
                          "notes": notes, "stats": stats}, ensure_ascii=False, indent=2))
        return 1 if problems else 0

    print(f"Phase 1 EXIT GATE — {args.task_id}")
    print()
    for p in problems:
        print(f"  ✗ {p}")
    for n in notes:
        print(f"  ⚠ {n}")
    print(
        f"  변경 대상 {stats['target_existing'] + stats['target_new']}건 "
        f"(기존 {stats['target_existing']} · 신규 {stats['target_new']}) · "
        f"재사용 {stats['reusable']} · 기존 테스트 {stats['existing_tests']} · "
        f"미해결 {stats['unresolved']} · 조사 {stats['exploration'] or '기록 없음'}"
    )
    print()
    print(f"{len(problems)}건 위반 — Phase 2a 진입 불가" if problems else "통과 — Phase 2a 진입 가능")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
