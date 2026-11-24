#!/usr/bin/env python3
"""워크플로우 이벤트를 로컬에 남기고 요약한다 — 외부로 아무것도 보내지 않는다.

왜 필요한가
-----------
계획 단계를 바꾼 효과는 재 봐야 안다 — 사람이 질문에 답하기까지 얼마나 기다렸는지, 역할별
리뷰의 소견이 실제로 채택됐는지, 확정한 결정이 몇 번 다시 열렸는지. 이 저장소는 HITL#2 를
실측(14개 태스크에서 거절 0건)으로 없앴다. 같은 방식으로 판단할 근거를 남긴다.

기록은 workflow_design/09_telemetry/<ID>.jsonl 에 ID 마다 따로 둔다. 한 파일에 모으면
브랜치마다 줄을 덧붙여 병합 충돌이 난다.

사용
----
    python3 scripts/wf_event.py --id REQ-001 --event question_asked --data '{"decision": "D3"}'
    python3 scripts/wf_event.py --id REQ-001 --summary
    python3 scripts/wf_event.py --summary-all --json

이벤트 이름은 EVENTS 에 있는 것만 받는다 — 자유 작명하면 요약에서 셀 수 없다.

exit code
---------
    0  기록 / 요약 성공
    2  인자 오류
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _utils import is_valid_req_id, is_valid_task_id, telemetry_path, workflow_design_root  # noqa: E402

EVENTS = {
    "draft_saved": "1차 계획 커밋",
    "question_asked": "사람에게 질문을 보냄",
    "question_answered": "사람이 답함",
    "review_finding": "역할별 리뷰 소견 (data.role, data.class)",
    "finding_applied": "소견을 계획에 반영",
    "finding_rejected": "소견을 받아들이지 않음",
    "mockup_rev": "시안 수정 회차 (data.impact)",
    "locked": "HITL#0 확정",
    "dispatched": "후속 작업 완료",
    "reopened": "확정한 결정이 다시 열림 (data.phase)",
    "gate_failed": "게이트 불통과 (data.gate)",
}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append(record_id: str, event: str, data: dict) -> Path:
    path = telemetry_path(record_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"ts": now(), "id": record_id, "event": event, "data": data}, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:   # 한 줄 append — 줄 단위라 부분 기록이 다른 줄을 망치지 않는다
        f.write(line + "\n")
    return path


def read(path: Path) -> list[dict]:
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            continue   # 깨진 줄은 건너뛴다 — 요약이 실패하면 아무것도 못 본다
    return out


def _ts(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def summarize(events: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for e in events:
        counts[e.get("event", "?")] = counts.get(e.get("event", "?"), 0) + 1
    # 질문 대기 — 보낸 뒤 다음 답까지. 짝이 없으면 세지 않는다.
    waits, pending = [], None
    for e in events:
        if e.get("event") == "question_asked":
            pending = _ts(e.get("ts"))
        elif e.get("event") == "question_answered" and pending:
            t = _ts(e.get("ts"))
            if t:
                waits.append((t - pending).total_seconds())
            pending = None
    by_role: dict[str, dict] = {}
    for e in events:
        role = (e.get("data") or {}).get("role")
        if not role:
            continue
        r = by_role.setdefault(role, {"findings": 0, "applied": 0, "rejected": 0})
        key = {"review_finding": "findings", "finding_applied": "applied", "finding_rejected": "rejected"}.get(e.get("event"))
        if key:
            r[key] += 1
    reopened = [(e.get("data") or {}).get("phase") for e in events if e.get("event") == "reopened"]
    return {
        "events": len(events),
        "counts": counts,
        "question_wait_sec": {"n": len(waits), "median": sorted(waits)[len(waits) // 2] if waits else None,
                              "total": sum(waits)},
        "review_by_role": by_role,
        "reopened_in": reopened,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--id", help="TASK-001 또는 REQ-001")
    ap.add_argument("--event", choices=sorted(EVENTS))
    ap.add_argument("--data", default="{}", help="JSON 객체")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--summary-all", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.summary_all:
        files = sorted((workflow_design_root() / "09_telemetry").glob("*.jsonl"))
        result = {p.stem: summarize(read(p)) for p in files}
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else
              "\n".join(f"{k}: 이벤트 {v['events']}건, 질문 대기 {v['question_wait_sec']['n']}회" for k, v in result.items())
              or "기록 없음")
        return 0

    if not args.id or not (is_valid_task_id(args.id) or is_valid_req_id(args.id)):
        print(f"--id 는 TASK-001 또는 REQ-001 형식이어야 한다: {args.id!r}", file=sys.stderr)
        return 2

    if args.summary:
        path = telemetry_path(args.id)
        s = summarize(read(path)) if path.is_file() else summarize([])
        print(json.dumps(s, ensure_ascii=False, indent=2) if args.json else
              f"{args.id}: 이벤트 {s['events']}건 · {s['counts']}")
        return 0

    if not args.event:
        print("--event 가 필요하다 (또는 --summary)", file=sys.stderr)
        return 2
    try:
        data = json.loads(args.data)
    except json.JSONDecodeError as exc:
        print(f"--data 가 JSON 이 아니다: {exc}", file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        print("--data 는 JSON 객체여야 한다", file=sys.stderr)
        return 2
    path = append(args.id, args.event, data)
    if not args.json:
        print(f"기록: {path.name} ← {args.event}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
