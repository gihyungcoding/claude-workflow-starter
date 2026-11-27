#!/usr/bin/env python3
"""Phase 3 이 더한 추가 시나리오(RETRY_FIX)의 형식을 검사한다.

왜 필요한가
-----------
Phase 4 FAIL 이 2a 로 돌아가면 독립검증 · HITL#1·2 · Red · Green · Phase 4 · HITL#3 를 다 다시 돈다.
ssirleague TASK-004 는 그렇게 4라운드 · 11시간을 썼는데, 되돌아간 이유 대부분이 「415 여야 할 것이 500 이다」처럼
**기대 결과는 이미 문서가 정해 두었고 시나리오에 적지 않았을 뿐**인 결함이었다.
그래서 그런 결함은 Phase 3 이 추가 시나리오와 테스트를 먼저 쓰고 고친 뒤, 사람이 HITL#3 에서 함께 본다
(→ docs/workflow/reject-state-machine.md §2.5). 독립검증과 HITL#1·2 를 건너뛰는 대신 이 스크립트가 형식을 지킨다.

검사하는 것
-----------
- TEST json `addenda[]` 마다: round(1 이상) · scenarios · test_files · red_commit · red_evidence
- 추가 시나리오가 SCENARIO json 에 있고 `addendum` 회차가 맞고 `basis`(근거 문서)가 비어 있지 않다
- SCENARIO json 에서 `addendum` 이 붙은 시나리오는 모두 어느 addenda 항목에 속한다 — 몰래 더한 시나리오가 없다
- 테스트 파일은 **새 파일**이다 — 통합 HITL 에서 승인된 `test_files` 와 겹치지 않는다
- 테스트 파일이 지금 있고, `red_commit` 이 HEAD 의 조상이며 **그 커밋에 이미 테스트 파일이 있다** — 수정보다 테스트가 먼저
- VERIFY 가 승인(APPROVE·EXCEPTION_APPROVE)이면 모든 addenda 가 `approved: true` — 사람이 본 것만 남는다

사용
----
    python3 scripts/check_addenda.py --task-id TASK-001 [--json]

exit code
---------
    0  추가 시나리오가 없거나 형식에 문제 없음
    1  위반 있음
    2  인자 오류 / TEST json 을 읽을 수 없음

이 검사가 못 잡는 것
-------------------
`basis` 가 정말 그 기대 결과를 정하는지는 보지 않는다 — 문장이 있는지만 본다. 근거가 틀리면 그것은 사람이 새로 정할
일이었다는 뜻이고, HITL#3 에서 사람이 「시나리오로 롤백」을 고른다. 완료 조건을 바꾸지 않았는지도 보지 않는다.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _utils import artifact_path, is_valid_task_id, load_json, repo_root, task_id_error  # noqa: E402

APPROVED = ("APPROVE", "EXCEPTION_APPROVE")


def _text(v: object) -> str:
    return v.strip() if isinstance(v, str) else ""


def _git_ok(*args: str) -> bool:
    try:
        subprocess.run(["git", *args], cwd=repo_root(), capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check(task_id: str) -> tuple[list[str], dict] | str:
    test_path = artifact_path(task_id, "2b")
    test, err = load_json(test_path) if test_path else (None, "경로 계산 실패")
    if not isinstance(test, dict):
        return f"TEST json 을 읽을 수 없다 — {err or '객체가 아니다'}"
    sc_path = artifact_path(task_id, "2a")
    scenario, _ = load_json(sc_path) if sc_path else (None, "")
    scenarios = {s.get("id"): s for s in ((scenario or {}).get("scenarios") or []) if isinstance(s, dict)}
    approved_files = {str(f) for f in test.get("test_files") or [] if isinstance(f, str)}

    problems: list[str] = []
    addenda = test.get("addenda") or []
    if not isinstance(addenda, list):
        return ["addenda 는 배열이어야 한다"], {"addenda": 0, "scenarios": 0}
    claimed: set[str] = set()
    for i, a in enumerate(addenda):
        where = f"addenda[{i}]"
        if not isinstance(a, dict):
            problems.append(f"{where} 가 객체가 아니다")
            continue
        rnd = a.get("round")
        if not isinstance(rnd, int) or isinstance(rnd, bool) or rnd < 1:
            problems.append(f"{where}: round 는 1 이상의 정수 — {rnd!r}")
        ids = [x for x in a.get("scenarios") or [] if isinstance(x, str)]
        if not ids:
            problems.append(f"{where}: scenarios 가 비었다")
        for sid in ids:
            claimed.add(sid)
            sc = scenarios.get(sid)
            if sc is None:
                problems.append(f"{where}: {sid} 가 SCENARIO json 에 없다 — MD 에 쓰고 JSON 을 다시 만든다")
                continue
            if sc.get("addendum") != rnd:
                problems.append(f"{where}: {sid} 의 addendum 이 {sc.get('addendum')!r} — 회차 {rnd!r} 와 다르다")
            if not _text(sc.get("basis")):
                problems.append(f"{where}: {sid} 에 basis 가 없다 — 기대 결과를 정한 문서와 그 문장(완료 조건·"
                                "conventions·ADR·기존 시나리오·표준). 근거가 없으면 사람이 정할 일이다(RETRY_SCENARIO)")
        files = [f for f in a.get("test_files") or [] if isinstance(f, str)]
        if not files:
            problems.append(f"{where}: test_files 가 비었다")
        for f in files:
            if f in approved_files:
                problems.append(f"{where}: {f} 는 통합 HITL 에서 승인된 테스트 파일이다 — 추가분은 새 파일에 쓴다")
            if not (repo_root() / f).is_file():
                problems.append(f"{where}: 테스트 파일이 없다 — {f}")
        if not _text(a.get("red_evidence")):
            problems.append(f"{where}: red_evidence 가 없다 — 수정 전에 실행해 실패한 출력 요약")
        red = _text(a.get("red_commit"))
        if not red:
            problems.append(f"{where}: red_commit 이 없다 — 테스트를 수정보다 먼저 커밋한 그 커밋")
        elif not _git_ok("merge-base", "--is-ancestor", red, "HEAD"):
            problems.append(f"{where}: red_commit {red} 가 HEAD 의 조상이 아니다")
        else:
            for f in files:
                if not _git_ok("cat-file", "-e", f"{red}:{f}"):
                    problems.append(f"{where}: red_commit {red} 에 {f} 가 없다 — 테스트가 수정보다 먼저여야 한다")

    for sid, sc in scenarios.items():
        if sc.get("addendum") is not None and sid not in claimed:
            problems.append(f"{sid}: addendum 이 붙었는데 TEST json addenda 어디에도 없다")

    verify_path = artifact_path(task_id, "4")
    verify, _ = load_json(verify_path) if verify_path and verify_path.is_file() else (None, "")
    decision = ((verify or {}).get("human_review") or {}).get("decision") if isinstance(verify, dict) else None
    if decision in APPROVED:
        for i, a in enumerate(addenda):
            if isinstance(a, dict) and a.get("approved") is not True:
                problems.append(f"addenda[{i}]: HITL#3 을 승인했는데 approved 가 true 가 아니다 — 승인 요약에 "
                                "추가 시나리오를 보이고 답을 받은 뒤 쓴다")
    return problems, {"addenda": len(addenda), "scenarios": len(claimed)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not is_valid_task_id(args.task_id):
        print(task_id_error(args.task_id), file=sys.stderr)
        return 2
    result = check(args.task_id)
    if isinstance(result, str):
        print(result, file=sys.stderr)
        return 2
    problems, stats = result
    if args.json:
        print(json.dumps({"task_id": args.task_id, "ok": not problems, "problems": problems, "stats": stats},
                         ensure_ascii=False, indent=2))
    else:
        print(f"추가 시나리오 점검 — {args.task_id}")
        if not stats["addenda"]:
            print("  – 추가 시나리오 없음")
        else:
            print(f"  추가 {stats['addenda']}회 · 시나리오 {stats['scenarios']}건")
        for p in problems:
            print(f"  ✗ {p}")
        print(f"{len(problems)}건 위반" if problems else "문제 없음")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
