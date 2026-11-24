#!/usr/bin/env python3
"""AskUserQuestion 전후 훅 — 사람에게 질문을 보낸 시각과 답을 받은 시각을 로컬에 남긴다.

왜 필요한가
-----------
계획 단계에 HITL#0 과 결정 대화를 넣었다. 이것이 대기만 늘리는지, 뒤 Phase 의 재작업을 줄이는지는
재 봐야 안다. 질문 시각은 스킬이 직접 적게 하면 빠뜨린다 — 그래서 도구 호출에 붙는 훅이 적는다.

동작
----
- PreToolUse  → question_asked   (질문 수·머리말)
- PostToolUse → question_answered
- 기록할 대상: 진행 중인 요청(BRIEF status 가 drafting·refining) 중 가장 최근 것, 없으면 ACTIVE 태스크가
  하나뿐일 때 그 태스크. 둘 다 없으면 아무것도 하지 않는다.
- 질문·답의 본문은 남기지 않는다 — 머리말(header)만.

exit code 는 항상 0 이다. 이 훅이 실패해서 질문을 막아서는 안 된다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def target_id() -> str | None:
    from _utils import list_tasks, workflow_design_root

    briefs = []
    for p in (workflow_design_root() / "01_brief").glob("BRIEF_REQ-*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("status") in ("drafting", "refining"):
            briefs.append((p.stat().st_mtime, data.get("id")))
    if briefs:
        return max(briefs)[1]
    active = [t for t in list_tasks() if str(t.get("status", "")).upper() == "ACTIVE"]
    return active[0].get("task_id") if len(active) == 1 else None


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if payload.get("tool_name") != "AskUserQuestion":
            return 0
        rid = target_id()
        if not rid:
            return 0
        from wf_event import append

        questions = (payload.get("tool_input") or {}).get("questions") or []
        data = {"n": len(questions), "headers": [str(q.get("header", ""))[:12] for q in questions if isinstance(q, dict)]}
        event = "question_answered" if payload.get("hook_event_name") == "PostToolUse" else "question_asked"
        append(rid, event, data)
    except Exception:  # noqa: BLE001 — 훅은 어떤 이유로도 질문을 막지 않는다
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
