#!/usr/bin/env python3
"""계획이 바뀌었을 때 어디부터 다시 해야 하는지 정한다 — PLAN 또는 BRIEF 의 두 버전을 비교한다.

왜 필요한가
-----------
Phase 2a~4 에서 계획 결함이 드러나면 계획을 고치고 되돌아간다. 그런데 "어디까지 되돌아가나"를
매번 판단에 맡기면, 과하게 되돌아가 승인된 시나리오·테스트를 다시 만들거나, 덜 되돌아가
고친 완료 조건이 시나리오에 반영되지 않는다. 무엇이 바뀌었는지(키)로 다시 시작할 가장 이른
지점을 기계적으로 정한다. reject-state-machine.md 의 영향 표가 정본이다.

다시 시작할 곳 (이른 순)
-----------------------
    task       태스크 재구성 (ROLLBACK_TASK) — 목표·분할·route 가 바뀜
    dispatch   후속 작업 추가 — 수정 범위(scope)가 바뀜 (ADR·기능 문서·태스크)
    1          Phase 1 정규화 다시 (ROLLBACK_PLAN)
    2a         시나리오 (RETRY_SCENARIO) — 완료 조건·입출력·흐름·입력 필드
    2b         Red 테스트 (RETRY_RED_CODE) — 테스트 힌트·기존 테스트
    3          구현 — 동작은 같고 변경 대상·재사용·접근이 바뀜
    none       기록만

사용
----
    python3 scripts/plan_impact.py --task-id TASK-001 --from <커밋>          # 그 커밋 이후 작업 트리까지
    python3 scripts/plan_impact.py --req REQ-001 --from <locked_commit> --to HEAD --json

--task-id 면 memory-bank 의 현재 Phase 와 비교해 되돌아갈지까지 말한다.

exit code
---------
    0  바뀐 것이 없거나, 지금 Phase 보다 뒤에서 반영하면 된다
    1  지금 Phase 이전으로 되돌아가야 한다
    2  인자 오류 / 파일을 읽을 수 없음
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _utils import (  # noqa: E402
    PHASE_ORDER,
    artifact_path,
    brief_path,
    is_valid_req_id,
    is_valid_task_id,
    parse_frontmatter,
    repo_root,
    task_dir,
)

ORDER = ["task", "dispatch", "1", "2a", "2b", "3", "none"]
REJECT_TYPE = {"task": "ROLLBACK_TASK", "dispatch": "DISPATCH", "1": "ROLLBACK_PLAN",
               "2a": "RETRY_SCENARIO", "2b": "RETRY_RED_CODE", "3": "PHASE_3", "none": None}

#: PLAN — 키(점 경로 앞부분) → 다시 시작할 곳. 위에서부터 가장 긴 접두사가 이긴다.
PLAN_RULES = [
    ("route", "task"),
    ("acceptance_criteria", "2a"),
    ("design", "2a"),
    ("codebase_analysis.unresolved", "2a"),
    ("codebase_analysis.existing_tests", "2b"),
    ("test_hints", "2b"),
    ("codebase_analysis", "3"),
    ("architecture_refs", "3"),
    ("adr_refs", "3"),
]
#: BRIEF — 진행 상태·기록 필드는 계획 내용이 아니므로 비교하지 않는다. 시안은 의견(feedback)만 따로 본다.
BRIEF_IGNORE = {"status", "dispatch", "tasks", "human_review", "reviews", "draft_commit", "mockup"}
BRIEF_RULES = [
    ("goal", "task"),
    ("split", "task"),
    ("scope", "dispatch"),
    ("acceptance_criteria", "2a"),
    ("completeness", "2a"),
    ("decisions", "1"),
    ("assumptions", "1"),
    ("approach", "3"),
    ("out_of_scope", "none"),
    ("posture", "none"),
    ("prompt", "none"),
]
FEEDBACK_IMPACT = {"visual": "3", "state": "2a", "screen": "2a", "data": "dispatch"}


def leaves(obj, prefix: str = "", depth: int = 2) -> dict[str, str]:
    """비교용 평탄화 — depth 단계까지는 키로 내려가고, 그 아래는 JSON 문자열로 본다."""
    if isinstance(obj, dict) and depth > 0:
        out: dict[str, str] = {}
        for k, v in obj.items():
            out.update(leaves(v, f"{prefix}.{k}" if prefix else str(k), depth - 1))
        return out
    return {prefix: json.dumps(obj, ensure_ascii=False, sort_keys=True)}


def classify(key: str, rules: list[tuple[str, str]]) -> str:
    best, best_len = "1", -1
    for prefix, target in rules:
        if (key == prefix or key.startswith(prefix + ".")) and len(prefix) > best_len:
            best, best_len = target, len(prefix)
    return best


def changes(old: dict, new: dict, kind: str) -> list[dict]:
    if kind == "brief":
        old = {k: v for k, v in old.items() if k not in BRIEF_IGNORE}
        new_cmp = {k: v for k, v in new.items() if k not in BRIEF_IGNORE}
        rules = BRIEF_RULES
    else:
        new_cmp, rules = new, PLAN_RULES
    a, b = leaves(old), leaves(new_cmp)
    out = []
    for key in sorted(set(a) | set(b)):
        if a.get(key) != b.get(key):
            out.append({"key": key, "restart": classify(key, rules)})
    return out


def mockup_changes(old: dict, new: dict) -> list[dict]:
    """시안 의견 중 새로 생긴 것 — 의견의 영향(impact)이 다시 할 곳을 정한다."""
    seen = {json.dumps(f, sort_keys=True, ensure_ascii=False)
            for f in ((old.get("mockup") or {}).get("feedback") or [])}
    out = []
    for fb in (new.get("mockup") or {}).get("feedback") or []:
        if json.dumps(fb, sort_keys=True, ensure_ascii=False) in seen or not isinstance(fb, dict):
            continue
        out.append({"key": f"mockup.feedback[rev {fb.get('rev')}] {fb.get('impact')}",
                    "restart": FEEDBACK_IMPACT.get(fb.get("impact"), "1")})
    return out


def read_version(rel: str, ref: str | None) -> tuple[dict | None, str]:
    if ref is None:
        p = repo_root() / rel
        try:
            return json.loads(p.read_text(encoding="utf-8")), ""
        except (OSError, json.JSONDecodeError) as exc:
            return None, f"작업 트리의 {rel} 를 읽을 수 없다 — {exc}"
    out = subprocess.run(["git", "show", f"{ref}:{rel}"], capture_output=True, text=True, cwd=repo_root())
    if out.returncode != 0:
        return None, f"{ref}:{rel} 를 읽을 수 없다 — {out.stderr.strip()}"
    try:
        return json.loads(out.stdout), ""
    except json.JSONDecodeError as exc:
        return None, f"{ref}:{rel} JSON 파싱 실패 — {exc}"


def current_phase(task_id: str) -> str | None:
    fm = parse_frontmatter(task_dir(task_id) / "activeContext.md")
    phase = str(fm.get("phase", "")).strip().strip('"')
    return phase if phase in PHASE_ORDER else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    who = ap.add_mutually_exclusive_group(required=True)
    who.add_argument("--task-id")
    who.add_argument("--req")
    ap.add_argument("--from", dest="from_ref", required=True, help="비교 기준 커밋")
    ap.add_argument("--to", dest="to_ref", default=None, help="비교 대상 커밋 (기본: 작업 트리)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.task_id:
        if not is_valid_task_id(args.task_id):
            print(f"태스크 ID 형식이 아니다: {args.task_id!r}", file=sys.stderr)
            return 2
        kind, path = "plan", artifact_path(args.task_id, "1")
    else:
        if not is_valid_req_id(args.req):
            print(f"요청 ID 형식이 아니다: {args.req!r}", file=sys.stderr)
            return 2
        kind, path = "brief", brief_path(args.req)
    rel = str(path.relative_to(repo_root()))

    old, err = read_version(rel, args.from_ref)
    new, err2 = read_version(rel, args.to_ref)
    if old is None or new is None:
        print(f"✗ {err or err2}", file=sys.stderr)
        return 2

    found = changes(old, new, kind)
    if kind == "brief":
        found += mockup_changes(old, new)
    restart = min((c["restart"] for c in found), key=ORDER.index, default="none")
    phase = current_phase(args.task_id) if args.task_id else None
    rewind = False
    if phase and restart in PHASE_ORDER:
        rewind = PHASE_ORDER.index(restart) < PHASE_ORDER.index(phase)
    elif phase and restart in ("task", "dispatch"):
        rewind = True

    result = {"target": args.task_id or args.req, "changes": found, "restart": restart,
              "reject_type": REJECT_TYPE[restart], "current_phase": phase, "rewind": rewind}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if not found:
            print(f"{result['target']}: 계획 내용이 바뀌지 않았다")
        else:
            print(f"{result['target']}: 바뀐 것 {len(found)}건 → 다시 시작할 곳 {restart}"
                  + (f" ({REJECT_TYPE[restart]})" if REJECT_TYPE[restart] else ""))
            for c in found:
                print(f"  {c['restart']:8} {c['key']}")
            if phase:
                print(f"  현재 Phase {phase} — " + ("되돌아가야 한다" if rewind else "지금 이후에 반영하면 된다"))
    return 1 if rewind else 0


if __name__ == "__main__":
    sys.exit(main())
