#!/usr/bin/env python3
"""태스크 워크플로우 현황을 집계한다.

왜 필요한가
-----------
memory-bank/index.md 는 파생물이라 재생성 전까지 낡아 있을 수 있다. 이 스크립트는
각 태스크의 activeContext.md 를 직접 읽으므로 항상 지금 상태를 보여준다.
/wf-status 슬래시 커맨드와 SessionStart 훅이 이것을 쓴다.

사용
----
    python scripts/wf_status.py              # 사람이 읽는 표
    python scripts/wf_status.py --json       # 기계용
    python scripts/wf_status.py --active     # 활성/차단만
    python scripts/wf_status.py --stale-days 14
    python scripts/wf_status.py --proposals      # 미반영 회고 개선안 전체

이 스크립트가 하지 않는 것
-------------------------
산출물이 실제로 있는지는 보지 않는다 (verify_workflow_artifacts.py 가 한다).
여기는 "어느 태스크가 어느 Phase에 있는가"만 답한다.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime

from _utils import (
    PHASE_NAMES,
    RECURRING_THRESHOLD,
    list_tasks,
    load_rule_proposals,
    recurring_proposals,
    saved_checkpoints,
)

DEFAULT_STALE_DAYS = 14


def days_since(value: str) -> int | None:
    """'2026-09-01' 또는 ISO 타임스탬프에서 경과 일수. 파싱 실패 시 None."""
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            parsed = datetime.strptime(text[: len(fmt) + 2].rstrip("Z"), fmt).date()
            return (date.today() - parsed).days
        except ValueError:
            continue
    return None


def phase_label(phase: str) -> str:
    if not phase:
        return "—"
    name = PHASE_NAMES.get(phase)
    return f"Phase {phase} ({name})" if name else f"Phase {phase}"


def collect(stale_days: int) -> dict:
    tasks = list_tasks()
    for task in tasks:
        age = days_since(task["last_updated"])
        task["days_since_update"] = age
        task["stale"] = (
            age is not None and age >= stale_days and task["status"] == "ACTIVE"
        )
        task["checkpoint_count"] = len(saved_checkpoints(task["folder"]))
        task["blocked_days"] = days_since(task["blocked_since"])

    return {
        "active": [t for t in tasks if t["status"] == "ACTIVE"],
        "blocked": [t for t in tasks if t["status"] == "BLOCKED"],
        "done": [t for t in tasks if t["status"] == "DONE"],
        "other": [
            t for t in tasks if t["status"] not in ("ACTIVE", "BLOCKED", "DONE")
        ],
    }


def render(groups: dict, active_only: bool) -> str:
    active, blocked, done = groups["active"], groups["blocked"], groups["done"]
    other = groups["other"]

    lines = [f"활성 {len(active)} / 차단 {len(blocked)} / 완료 {len(done)}"]
    if other:
        lines[0] += f" / 기타 {len(other)}"
    lines.append("")

    if not active and not blocked:
        lines.append("  진행 중인 태스크가 없습니다. /wf-start <TASK-ID> 로 시작하세요.")
        return "\n".join(lines)

    for task in sorted(active, key=lambda t: t["task_id"]):
        age = task["days_since_update"]
        when = f"{age}일 전" if age is not None else "—"
        mark = " ⚠ 정체" if task["stale"] else ""
        lines.append(
            f"  {task['task_id']:<12} {phase_label(task['phase']):<22} "
            f"{when:<8} {task['title']}{mark}"
        )

    for task in sorted(blocked, key=lambda t: t["task_id"]):
        days = task["blocked_days"]
        span = f"{days}일째" if days is not None else "기간 미상"
        lines.append("")
        lines.append(f"  ⛔ {task['task_id']}  차단 {span}  {task['title']}")
        if task["blocked_reason"]:
            lines.append(f"     사유: {task['blocked_reason']}")
        if task["unblock_condition"]:
            lines.append(f"     해제 조건: {task['unblock_condition']}")

    mismatched = [t for t in active + blocked if t["folder_mismatch"]]
    if mismatched:
        lines.append("")
        lines.append("  ⚠ 폴더명과 task_id 불일치 — 확인이 필요합니다:")
        for task in mismatched:
            lines.append(f"     폴더 {task['folder']} vs task_id {task['task_id']}")

    if not active_only and done:
        lines.append("")
        lines.append(f"  완료 {len(done)}건: " + ", ".join(t["task_id"] for t in done[:10]))
        if len(done) > 10:
            lines.append(f"  ... 외 {len(done) - 10}건")

    return "\n".join(lines)


def render_proposals(proposals: list[dict], full: bool) -> str:
    """회고 개선안 현황. 반복 미반영이 있으면 눈에 띄게 한다.

    왜 여기 있나: 실사용 8개 태스크에서 회고가 낸 개선안 22건 중 반영이 확인된 것은
    3건이었다. 같은 파일(coverage-policy.md)에 대한 제안이 세 태스크에 걸쳐 나왔는데,
    그 사이 같은 원인의 재작업이 계속됐다. 미반영 건이 어디에도 보이지 않았기 때문이다.
    """
    if not proposals:
        return ""
    count = {s: sum(1 for p in proposals if p["status"] == s) for s in ("pending", "applied", "rejected")}
    lines = ["", f"회고 개선안   미반영 {count['pending']} · 반영 {count['applied']} · 반려 {count['rejected']}"]

    recurring = recurring_proposals(proposals)
    if recurring:
        lines.append(f"  ⚠ 같은 대상에 {RECURRING_THRESHOLD}건 이상 쌓인 미반영 — 다음 태스크 전에 반영을 권합니다")
        for key, items in recurring.items():
            tasks = " · ".join(sorted({p["task_id"] for p in items}))
            lines.append(f"     {key:<24} ×{len(items)}   {tasks}")

    if full:
        pending = [p for p in proposals if p["status"] == "pending"]
        if pending:
            lines.append("")
            for p in pending:
                change = str(p["change"]).replace("\n", " ")
                lines.append(f"  {p['task_id']} #{p['index']}  [{p['key']}]")
                lines.append(f"     {change[:150]}{'…' if len(change) > 150 else ''}")
    elif count["pending"]:
        lines.append("  전체 목록: python scripts/wf_status.py --proposals")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true", help="JSON 으로 출력")
    parser.add_argument("--active", action="store_true", help="활성/차단만 표시")
    parser.add_argument(
        "--stale-days",
        type=int,
        default=DEFAULT_STALE_DAYS,
        help=f"정체 판정 기준 일수 (기본 {DEFAULT_STALE_DAYS})",
    )
    parser.add_argument("--proposals", action="store_true", help="미반영 회고 개선안을 전부 표시")
    args = parser.parse_args()

    groups = collect(args.stale_days)
    proposals = load_rule_proposals()

    if args.json:
        payload = dict(groups)
        if args.active:
            payload.pop("done", None)
        payload["proposals"] = {
            "pending": [p for p in proposals if p["status"] == "pending"],
            "recurring": recurring_proposals(proposals),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(render(groups, args.active))
    block = render_proposals(proposals, args.proposals)
    if block:
        print(block)
    return 0


if __name__ == "__main__":
    sys.exit(main())
