#!/usr/bin/env python3
"""요청 계획(BRIEF)의 게이트를 검사한다 — Lock(HITL#0) 전에, Dispatch 가 끝났을 때.

왜 필요한가
-----------
계획 대화는 길어지고, "다 정했다"는 판단은 대화를 진행한 에이전트가 내린다. 미결 결정이
남았는데 확정을 묻거나, 완료 조건에 오류 경우가 없거나, 시안이 덮지 못한 완료 조건이
있는 채로 확정되면 그 비용은 2a·4 에서 치른다. 이 스크립트가 그 판단을 파일로 대신한다.

게이트
------
    --gate draft      1차 계획이 최소한의 모양을 갖췄나
    --gate lock       사람에게 확정을 물어도 되나 (기본값)
    --gate locked     확정됐나 — lock 조건 + human_review.approved + locked_commit
    --gate dispatch   후속 작업이 다 끝났나 — locked 조건 + dispatch 전부 처리 + 태스크 연결

사용
----
    python3 scripts/check_brief.py --req REQ-001
    python3 scripts/check_brief.py --req REQ-001 --gate dispatch --json

exit code
---------
    0  통과 (경고는 있을 수 있다)
    1  위반 있음
    2  인자 오류 / BRIEF 를 읽을 수 없음

이 검사가 못 잡는 것
-------------------
human_review.approved 가 실제로 AskUserQuestion 응답에서 왔는지는 모른다 — 필드가 있는지만 본다.
결정의 내용이 옳은지, 완료 조건이 요구를 다 덮는지도 보지 않는다. 모양과 빠짐만 본다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _utils import (  # noqa: E402
    brief_path,
    is_valid_req_id,
    load_json,
    mockup_dir,
    repo_root,
    tasks_json_path,
)

STATUSES = ("drafting", "refining", "locked", "dispatched", "done", "abandoned")
POSTURES = ("hold", "selective", "expand", "reduce")
ROUTES = ("Backend", "Frontend", "Database")
DECISION_CLASSES = ("mechanical", "taste", "user_challenge")
DECISION_STATUSES = ("unresolved", "approved", "declined", "deferred", "reopened")
OPEN_DECISION = ("unresolved", "reopened")
UI_MODES = ("none", "annotate", "mockup")
MOCKUP_STATUSES = ("none", "draft", "approved")
FEEDBACK_IMPACTS = ("visual", "state", "screen", "data")
JOB_STATUSES = ("pending", "done", "skipped")
GATES = ("draft", "lock", "locked", "dispatch")

#: 완전성 보강을 묻지 않고 넣을 수 있는 상한 (brief-schema.md §5)
COMPLETENESS_MAX_DELTA_H = 2
WRU_MIN_H, WRU_MAX_H = 4, 16


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def _list(brief: dict, key: str, rep: Report) -> list:
    value = brief.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        rep.err(f"{key} 는 배열이어야 한다")
        return []
    return value


def check_draft(brief: dict, req_id: str, rep: Report) -> None:
    if brief.get("id") != req_id:
        rep.err(f"id 가 파일명과 다르다: {brief.get('id')!r} ≠ {req_id!r}")
    if brief.get("status") not in STATUSES:
        rep.err(f"status 는 {STATUSES} 중 하나: {brief.get('status')!r}")
    for key in ("prompt", "goal"):
        if not str(brief.get(key) or "").strip():
            rep.err(f"{key} 가 비어 있다")
    posture = brief.get("posture")
    if posture is not None and posture not in POSTURES:
        rep.err(f"posture 는 {POSTURES} 중 하나: {posture!r}")


def check_acceptance(brief: dict, scope: dict, rep: Report) -> dict[str, dict]:
    acs = _list(brief, "acceptance_criteria", rep)
    by_id: dict[str, dict] = {}
    for ac in acs:
        if not isinstance(ac, dict) or not ac.get("id") or not str(ac.get("text") or "").strip():
            rep.err(f"완료 조건 항목에 id·text 가 없다: {ac!r}")
            continue
        if ac["id"] in by_id:
            rep.err(f"완료 조건 id 중복: {ac['id']}")
        if ac.get("kind") not in ("happy", "error"):
            rep.err(f"{ac['id']}: kind 는 happy | error")
        by_id[ac["id"]] = ac
    if scope.get("wru", True):
        kinds = {ac.get("kind") for ac in by_id.values()}
        if "happy" not in kinds or "error" not in kinds:
            rep.err("완료 조건에 정상(happy)과 오류(error)가 각각 1건 이상 있어야 한다")
    if "out_of_scope" not in brief:
        rep.err("out_of_scope 가 없다 — 하지 않는 것이 없으면 빈 배열로 적는다")
    return by_id


def check_decisions(brief: dict, rep: Report) -> None:
    seen: set[str] = set()
    for d in _list(brief, "decisions", rep):
        if not isinstance(d, dict) or not d.get("id"):
            rep.err(f"결정 항목에 id 가 없다: {d!r}")
            continue
        did = d["id"]
        if did in seen:
            rep.err(f"결정 id 중복: {did}")
        seen.add(did)
        if d.get("class") not in DECISION_CLASSES:
            rep.err(f"{did}: class 는 {DECISION_CLASSES} 중 하나")
        status = d.get("status")
        if status not in DECISION_STATUSES:
            rep.err(f"{did}: status 는 {DECISION_STATUSES} 중 하나")
        elif status in OPEN_DECISION:
            rep.err(f"{did}: 아직 정하지 않은 결정이다 ({status}) — {d.get('question', '')}")
        elif d.get("class") == "user_challenge" and not str(d.get("answer") or "").strip():
            rep.err(f"{did}: 사용자 결정인데 answer 가 없다 — 사람의 답을 그대로 적는다")


def check_completeness(brief: dict, rep: Report) -> None:
    for c in _list(brief, "completeness", rep):
        if not isinstance(c, dict) or not c.get("id"):
            rep.err(f"완전성 보강 항목에 id 가 없다: {c!r}")
            continue
        if c.get("status") not in ("included", "dropped"):
            rep.err(f"{c['id']}: status 는 included | dropped")
            continue
        if c["status"] != "included":
            continue
        if c.get("in_radius") is not True:
            rep.err(f"{c['id']}: 영향 범위 밖인데 자동 포함했다 — 사용자 결정으로 올린다")
        delta = c.get("estimate_delta_h")
        if not isinstance(delta, (int, float)) or delta > COMPLETENESS_MAX_DELTA_H:
            rep.err(f"{c['id']}: 추정 증가 {delta!r}h — {COMPLETENESS_MAX_DELTA_H}h 를 넘으면 사용자 결정으로 올린다")


def check_scope(brief: dict, rep: Report) -> dict:
    scope = brief.get("scope")
    if not isinstance(scope, dict):
        rep.err("scope 가 없다 — 수정 범위가 정해져야 후속 작업을 정할 수 있다")
        return {}
    for key in ("wru", "product_change", "design_tokens", "migration"):
        if not isinstance(scope.get(key), bool):
            rep.err(f"scope.{key} 는 true | false")
    arch = scope.get("architecture")
    if not isinstance(arch, dict) or not isinstance(arch.get("change"), bool):
        rep.err("scope.architecture.change 는 true | false")
    elif arch["change"] and not arch.get("adr"):
        rep.err("scope.architecture.change 가 true 인데 남길 ADR(adr) 이 없다")
    if scope.get("ui") not in UI_MODES:
        rep.err(f"scope.ui 는 {UI_MODES} 중 하나: {scope.get('ui')!r}")
    routes = scope.get("routes")
    if scope.get("wru"):
        if not isinstance(routes, list) or not routes or any(r not in ROUTES for r in routes):
            rep.err(f"scope.routes 는 {ROUTES} 의 부분집합(비어 있지 않음)")
    return scope


def check_split(brief: dict, scope: dict, acs: dict[str, dict], rep: Report) -> None:
    split = _list(brief, "split", rep)
    if not scope.get("wru"):
        if split:
            rep.warn("scope.wru 가 false 인데 split 이 있다 — 코드 변경이 없으면 태스크를 만들지 않는다")
        return
    if not split:
        rep.err("코드 변경이 있는데 태스크 분할(split)이 없다")
        return
    keys: set[str] = set()
    covered: set[str] = set()
    for t in split:
        key = t.get("key") if isinstance(t, dict) else None
        if not key:
            rep.err(f"split 항목에 key 가 없다: {t!r}")
            continue
        if key in keys:
            rep.err(f"split key 중복: {key}")
        keys.add(key)
        if t.get("route") not in ROUTES:
            rep.err(f"split {key}: route 는 {ROUTES} 중 하나")
        est = t.get("estimate_h")
        if not isinstance(est, (int, float)):
            rep.err(f"split {key}: estimate_h 가 숫자가 아니다")
        elif not WRU_MIN_H <= est <= WRU_MAX_H:
            rep.warn(f"split {key}: 추정 {est}h — WRU 는 {WRU_MIN_H}~{WRU_MAX_H}h (task-schema.md §1)")
        for ref in t.get("ac") or []:
            if ref not in acs:
                rep.err(f"split {key}: 없는 완료 조건을 가리킨다: {ref}")
            covered.add(ref)
    for t in split:
        for dep in (t.get("depends_on") or []) if isinstance(t, dict) else []:
            if dep not in keys:
                rep.err(f"split {t.get('key')}: depends_on 이 없는 key 를 가리킨다: {dep}")
    missing = sorted(set(acs) - covered)
    if missing:
        rep.err(f"어느 태스크도 맡지 않은 완료 조건: {', '.join(missing)}")


def check_mockup(brief: dict, req_id: str, scope: dict, acs: dict[str, dict], rep: Report) -> None:
    if scope.get("ui") != "mockup":
        return
    mock = brief.get("mockup")
    if not isinstance(mock, dict):
        rep.err("scope.ui 가 mockup 인데 mockup 기록이 없다")
        return
    if mock.get("status") != "approved":
        rep.err(f"시안이 확정되지 않았다 (mockup.status={mock.get('status')!r})")
    if not isinstance(mock.get("rev"), int) or mock["rev"] < 1:
        rep.err("mockup.rev 는 1 이상의 정수")
    for fb in mock.get("feedback") or []:
        if isinstance(fb, dict) and fb.get("impact") not in FEEDBACK_IMPACTS:
            rep.err(f"시안 의견의 impact 는 {FEEDBACK_IMPACTS} 중 하나: {fb!r}")

    d = mockup_dir(req_id)
    screens_file = d / "screens.json"
    screens, msg = load_json(screens_file)
    if screens is None:
        rep.err(f"시안 증거가 없다 — {screens_file.relative_to(repo_root())} ({msg})")
        return
    ids = {s.get("id") for s in screens.get("screens", []) if isinstance(s, dict)}
    ids |= {s.get("id") for s in screens.get("desktop", []) if isinstance(s, dict)}
    coverage = mock.get("coverage") or {}
    for ac_id, ac in acs.items():
        if not ac.get("ui"):
            continue
        refs = coverage.get(ac_id) or []
        if not refs:
            rep.err(f"{ac_id}: 화면에서 보여야 하는 완료 조건인데 어느 시안 화면도 덮지 않는다")
        for ref in refs:
            if ref not in ids:
                rep.err(f"{ac_id}: 시안에 없는 화면을 가리킨다: {ref}")


def check_locked(brief: dict, rep: Report) -> None:
    hr = brief.get("human_review")
    if not isinstance(hr, dict) or hr.get("approved") is not True:
        rep.err("human_review.approved 가 true 가 아니다 — HITL#0 승인 전이다")
    elif not str(hr.get("locked_commit") or "").strip():
        rep.err("human_review.locked_commit 이 없다 — 확정한 커밋을 남긴다")
    if not brief.get("draft_commit"):
        rep.warn("draft_commit 이 없다 — 1차 계획과 확정본을 비교할 수 없다")


def check_dispatch(brief: dict, req_id: str, rep: Report) -> None:
    jobs = _list(brief, "dispatch", rep)
    if not jobs:
        rep.err("dispatch 가 비어 있다 — route_brief.py --write 로 후속 작업을 만든다")
    for j in jobs:
        status = j.get("status") if isinstance(j, dict) else None
        if status not in JOB_STATUSES:
            rep.err(f"dispatch 항목 status 는 {JOB_STATUSES} 중 하나: {j!r}")
        elif status == "pending":
            rep.err(f"아직 하지 않은 후속 작업: {j.get('job')}")
    if not (brief.get("scope") or {}).get("wru"):
        return
    task_ids = brief.get("tasks") or []
    if not task_ids:
        rep.err("코드 변경이 있는데 연결된 태스크(tasks)가 없다")
        return
    tasks, msg = load_json(tasks_json_path())
    if not isinstance(tasks, list):
        rep.err(f"tasks.json 을 읽을 수 없다 — {msg}")
        return
    by_id = {t.get("id"): t for t in tasks if isinstance(t, dict)}
    for tid in task_ids:
        t = by_id.get(tid)
        if t is None:
            rep.err(f"tasks.json 에 없는 태스크: {tid}")
        elif (t.get("source_refs") or {}).get("request_id") != req_id:
            rep.err(f"{tid}: source_refs.request_id 가 {req_id} 가 아니다")


def run(req_id: str, gate: str) -> tuple[Report, dict | None, str]:
    rep = Report()
    path = brief_path(req_id)
    brief, msg = load_json(path)
    if not isinstance(brief, dict):
        return rep, None, msg or f"BRIEF 가 객체가 아니다: {path}"
    check_draft(brief, req_id, rep)
    if gate == "draft":
        return rep, brief, ""
    scope = check_scope(brief, rep)
    acs = check_acceptance(brief, scope, rep)
    check_decisions(brief, rep)
    check_completeness(brief, rep)
    check_split(brief, scope, acs, rep)
    check_mockup(brief, req_id, scope, acs, rep)
    if gate in ("locked", "dispatch"):
        check_locked(brief, rep)
    if gate == "dispatch":
        check_dispatch(brief, req_id, rep)
    return rep, brief, ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--req", required=True, help="요청 ID (REQ-001)")
    ap.add_argument("--gate", choices=GATES, default="lock")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not is_valid_req_id(args.req):
        print(f"요청 ID 형식이 아니다: {args.req!r} — 'REQ-' + 숫자 3자리 이상", file=sys.stderr)
        return 2
    rep, brief, fatal = run(args.req, args.gate)
    if fatal:
        if args.json:
            print(json.dumps({"req": args.req, "gate": args.gate, "fatal": fatal}, ensure_ascii=False))
        else:
            print(f"✗ {fatal}", file=sys.stderr)
        return 2

    ok = not rep.errors
    if args.json:
        print(json.dumps({"req": args.req, "gate": args.gate, "pass": ok,
                          "errors": rep.errors, "warnings": rep.warnings}, ensure_ascii=False, indent=2))
    else:
        print(f"{'✓' if ok else '✗'} {args.req} — {args.gate} 게이트 {'통과' if ok else '불통과'}")
        for e in rep.errors:
            print(f"  ✗ {e}")
        for w in rep.warnings:
            print(f"  ⚠ {w}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
