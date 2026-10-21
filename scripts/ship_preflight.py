#!/usr/bin/env python3
"""머지 전 최종 검사 — /wf-ship 이 PR 을 만들기 전에 통과해야 하는 것들.

왜 필요한가
-----------
Phase 1~5의 게이트를 다 통과했더라도, 머지 직전에만 확인할 수 있는 것들이 있다.
승인 이후 코드가 바뀌었는지, 기준 브랜치와 충돌하는지, 작업 트리에 커밋 안 된 것이
남았는지. 이 검사들이 흩어져 있으면 그때그때 빠뜨린다.

각 항목은 기존 스크립트를 호출한다 — 검사 로직을 두 벌로 만들지 않는다.
CI 도 같은 스크립트를 부르므로 로컬에서 통과한 것이 CI 에서 막히는 일이 없다.

사용
----
    python3 scripts/ship_preflight.py --task-id TASK-001
    python3 scripts/ship_preflight.py --task-id TASK-001 --json
    python3 scripts/ship_preflight.py --task-id TASK-001 --skip-merge-check

exit code
---------
    0  전부 통과 — PR 을 만들어도 된다
    1  하나 이상 실패
    2  인자 오류

이 검사가 하지 않는 것
---------------------
PR 을 만들지 않는다. 테스트를 실행하지 않는다(Phase 3·4에서 이미 했고, 그 결과가
산출물에 기록되어 있다). 여기서 다시 돌리면 같은 것을 두 번 하는 것이다.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _utils import (  # noqa: E402
    artifact_path,
    base_branch,
    branch_exists,
    current_branch,
    is_valid_task_id,
    load_json,
    parse_frontmatter,
    repo_root,
    task_dir,
    task_id_error,
    worktree_dirty,
)

SCRIPTS = Path(__file__).resolve().parent


class Check:
    def __init__(self, name: str) -> None:
        self.name = name
        self.ok = False
        self.detail = ""
        self.lines: list[str] = []
        self.skipped = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": "skip" if self.skipped else ("pass" if self.ok else "fail"),
            "detail": self.detail,
            "lines": self.lines,
        }


def run_script(name: str, *args: str) -> tuple[int, str]:
    try:
        out = subprocess.run(
            [sys.executable, str(SCRIPTS / name), *args],
            capture_output=True, text=True, cwd=repo_root(),
        )
        return out.returncode, (out.stdout + out.stderr).strip()
    except Exception as exc:  # noqa: BLE001
        return 2, f"{name} 실행 실패: {exc}"


def check_phase_complete(task_id: str) -> Check:
    c = Check("Phase 5 완료")
    ctx = task_dir(task_id) / "activeContext.md"
    if not ctx.is_file():
        c.detail = f"activeContext.md 없음 — /wf-start 로 시작한 태스크가 맞는가"
        return c

    fm = parse_frontmatter(ctx)
    phase, status = str(fm.get("phase") or ""), fm.get("status") or ""

    if status == "BLOCKED":
        c.detail = f"태스크가 차단 상태다 — {fm.get('blocked_reason', '사유 미기록')}"
        return c

    reflect, err = load_json(artifact_path(task_id, "5"))
    approved = (
        isinstance(reflect, dict)
        and (reflect.get("completion_report") or {}).get("approved_by_human") is True
    )
    if not approved:
        c.detail = f"Phase 5 회고 승인이 없다 (현재 Phase {phase or '?'})"
        c.lines = ["회고까지 마쳐야 무엇이 머지되는지 릴리스 시점에 알 수 있다"]
        return c

    c.ok = True
    c.detail = "회고 승인됨"
    return c


def check_artifacts(task_id: str) -> Check:
    c = Check("산출물 완결성")
    code, out = run_script("verify_workflow_artifacts.py", "--task-id", task_id)
    c.ok = code == 0
    if c.ok:
        c.detail = "Phase 1~5 산출물·체크포인트 모두 커밋됨"
    else:
        c.detail = "누락 또는 미커밋"
        c.lines = [l.strip() for l in out.splitlines() if l.strip().startswith(("[", "memory-bank"))][:8]
    return c


def check_freshness(task_id: str) -> Check:
    c = Check("신선도 — 승인한 코드 그대로인가")
    code, out = run_script("check_freshness.py", "--task-id", task_id, "--json")
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        c.detail = "판정 불가"
        c.lines = out.splitlines()[:4]
        return c

    if data["status"] == "fresh":
        c.ok = True
        c.detail = data["reason"]
    elif data["status"] == "stale":
        c.detail = data["reason"]
        c.lines = data["changed_source"][:8] + ["→ Phase 4 재검증이 필요하다"]
    else:
        c.detail = data["reason"]
    return c


def check_architecture() -> Check:
    c = Check("아키텍처 제약")
    code, out = run_script("check_architecture.py", "--json")
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        c.detail = "판정 불가"
        c.lines = out.splitlines()[:4]
        return c

    status = data.get("status")
    if status in ("skipped", "empty"):
        c.ok, c.skipped = True, True
        c.detail = "정의된 제약 없음"
        return c

    if status == "fail":
        c.detail = "error 위반 있음"
        c.lines = [
            f"{r['id']}  {r['rule']}"
            for r in data.get("results", [])
            if r.get("violations") and r.get("severity") == "error"
        ][:6]
        return c

    c.ok = True
    total = len(data.get("results", []))
    unscanned = data.get("no_target") or []
    if unscanned:
        # 대상 파일이 없어 검사되지 않은 제약은 통과가 아니다. 막지는 않는다 — 아직 없는
        # 계층에 대한 제약일 수 있다 — 하지만 '통과'로 뭉뚱그리지 않고 무엇인지 적는다.
        c.detail = (
            f"제약 {total - len(unscanned)}건 통과, {len(unscanned)}건은 검사되지 않음 "
            f"({', '.join(unscanned)})"
        )
        c.lines = ["검사 대상 파일이 없었다 — detect.paths 의 glob 이 실제 경로와 맞는지 확인하라"]
    else:
        c.detail = f"제약 {total}건 통과 — 파일 {data.get('files_scanned', 0)}개 검사"
    for item in data.get("overdue_promotions") or []:
        c.lines.append(f"승격 기한 지남: {item['id']} ({item['promote_after']} 완료)")
    return c


def check_worktree() -> Check:
    c = Check("작업 트리")
    dirty = worktree_dirty()
    if not dirty:
        c.ok = True
        c.detail = "커밋되지 않은 변경 없음"
    else:
        c.detail = f"커밋되지 않은 변경 {len(dirty)}건"
        c.lines = dirty[:8]
    return c


def check_branch(task_id: str) -> Check:
    c = Check("브랜치")
    branch, base = current_branch(), base_branch()

    if not branch:
        c.detail = "현재 브랜치를 알 수 없다 (detached HEAD?)"
        return c
    if branch == base:
        c.detail = f"기준 브랜치({base}) 위에서 작업 중이다 — feature 브랜치가 필요하다"
        return c

    number = task_id.split("-", 1)[1].lstrip("0") or "0"
    if number not in branch and task_id.lower() not in branch.lower():
        c.lines = [f"브랜치명에 태스크 번호가 없다 — 추적이 끊길 수 있다"]

    c.ok = True
    c.detail = f"{branch} → {base}"
    return c


def check_mergeable() -> Check:
    c = Check("기준 브랜치 병합 가능")
    base = base_branch()
    if not branch_exists(base):
        c.skipped, c.ok = True, True
        c.detail = f"기준 브랜치 {base} 없음 — 건너뜀"
        return c

    try:
        merge_base = subprocess.run(
            ["git", "merge-base", "HEAD", base],
            capture_output=True, text=True, cwd=repo_root(),
        )
        if merge_base.returncode != 0:
            c.skipped, c.ok = True, True
            c.detail = "공통 조상 없음 — 건너뜀"
            return c

        tree = subprocess.run(
            ["git", "merge-tree", merge_base.stdout.strip(), "HEAD", base],
            capture_output=True, text=True, cwd=repo_root(),
        )
        conflicts = [
            l for l in tree.stdout.splitlines()
            if l.startswith("<<<<<<<") or l.startswith("changed in both")
        ]
        if conflicts:
            c.detail = f"{base} 와 충돌 가능성 {len(conflicts)}건"
            c.lines = ["git rebase " + base + " 로 먼저 정리하라"]
        else:
            c.ok = True
            c.detail = f"{base} 와 충돌 없음"
    except FileNotFoundError:
        c.skipped, c.ok = True, True
        c.detail = "git 없음 — 건너뜀"
    return c


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--skip-merge-check", action="store_true")
    args = parser.parse_args()

    if not is_valid_task_id(args.task_id):
        print(task_id_error(args.task_id), file=sys.stderr)
        return 2

    checks = [
        check_phase_complete(args.task_id),
        check_artifacts(args.task_id),
        check_freshness(args.task_id),
        check_architecture(),
        check_worktree(),
        check_branch(args.task_id),
    ]
    if not args.skip_merge_check:
        checks.append(check_mergeable())

    failed = [c for c in checks if not c.ok]

    if args.json:
        print(json.dumps({
            "task_id": args.task_id,
            "status": "fail" if failed else "pass",
            "base_branch": base_branch(),
            "branch": current_branch(),
            "checks": [c.to_dict() for c in checks],
        }, ensure_ascii=False, indent=2))
        return 1 if failed else 0

    print(f"Ship 사전 검사 — {args.task_id}")
    print()
    for c in checks:
        mark = "–" if c.skipped else ("✓" if c.ok else "✗")
        print(f"  {mark} {c.name}")
        if c.detail:
            print(f"      {c.detail}")
        for line in c.lines:
            print(f"        {line}")
    print()

    if failed:
        print(f"{len(failed)}건 미통과 — PR 을 만들 수 없습니다.")
        return 1
    print("전부 통과 — PR 을 만들어도 됩니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
