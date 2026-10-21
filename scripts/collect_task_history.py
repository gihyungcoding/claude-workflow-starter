#!/usr/bin/env python3
"""태스크 하나의 이력을 모은다 — Phase 5 회고(wf-reflect Step 1)의 입력.

왜 필요한가
-----------
회고는 "이 태스크에서 실제로 무슨 일이 있었나" 에서 시작한다. 그 재료가 체크포인트 6개,
VERIFY · DEV · PLAN · VALIDATION 산출물, 그리고 그 파일들의 git 이력에 흩어져 있다.
에이전트가 매번 grep 으로 모으면 빠뜨리는 것이 생기고, 읽은 원문이 그대로 컨텍스트에
쌓인다. 결정적인 집계라 LLM 이 할 일이 아니다.

특히 **라운드 수**는 파일을 읽어서는 알 수 없다. VERIFY 는 라운드마다 덮어써지므로 마지막
판정만 남는다. git 이력에서 VERIFY 버전을 라운드로 묶어야 Phase 4 가 몇 번 FAIL 했는지 보인다.
(라운드 = 두 VERIFY 버전 사이에 이 브랜치에서 소스가 바뀌었으면 다른 라운드 —
`_utils.source_changed_between`)

모으는 것
---------
- 태스크 상태 (activeContext)
- 시간 — 이 태스크 산출물의 첫 커밋 ~ 마지막 커밋
- 되돌아감 — 모든 체크포인트의 attempts (v1 이면 _retry 파일 수)
- 결정 — 모든 체크포인트의 decisions
- Phase 2a 독립검증 — 커밋된 VALIDATION 버전의 통과/실패 수
- Phase 4 라운드 — 커밋된 VERIFY 버전을 라운드로 묶은 판정 목록
- 최종 VERIFY — 판정, 승인, 예외, PASS 가 아닌 acceptance_criteria, 뿌리 원인(later · not_probed)
- DEV — scope_deviations, rollback_fixes
- PLAN — unresolved, 조사 방식(exploration — Explore 시험의 판정 재료)

사용
----
    python3 scripts/collect_task_history.py --task-id TASK-001
    python3 scripts/collect_task_history.py --task-id TASK-001 --json

exit code
---------
    0  모음 (없는 산출물은 '없음' 으로 보고한다 — 실패가 아니다)
    2  인자 오류 / memory-bank 에 태스크가 없음

이 스크립트가 하지 않는 것
-------------------------
판단하지 않는다. 무엇이 문제였는지, 무엇을 고칠지는 회고(사람과 에이전트)의 몫이다.
저장소 파일의 자유 텍스트는 한 줄로 접고 길이를 잘라 출력한다 — 출력이 에이전트 컨텍스트로
들어가므로 줄바꿈·제어 문자로 출력 형식을 흉내 내지 못하게 한다. 원문이 필요하면 파일을 연다.
체크포인트 본문(v1 의 산문)은 읽지 않는다.
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
    display_text,
    is_valid_task_id,
    load_json,
    parse_frontmatter,
    repo_root,
    source_changed_between,
    task_dir,
    task_id_error,
    workflow_design_root,
)
import check_root_causes  # noqa: E402

TEXT_LIMIT = 160
CP_PHASE_DIRS = ["phase1", "phase2a", "phase2b", "phase3", "phase4", "phase5"]


def _t(value: object) -> str:
    return display_text(value, TEXT_LIMIT)


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, cwd=repo_root())
    except FileNotFoundError:
        return None
    return out.stdout if out.returncode == 0 else None


def _rel(path: Path) -> str:
    return str(path.resolve().relative_to(repo_root().resolve()))


def versions_oldest_first(path: Path) -> list[tuple[str, dict]]:
    """커밋된 버전들 (커밋, 내용). 파싱 못 하는 버전은 건너뛴다."""
    try:
        rel = _rel(path)
    except ValueError:
        return []
    log = _git("log", "--format=%H", "--reverse", "--", rel)
    out = []
    for sha in (log or "").split():
        blob = _git("show", f"{sha}:{rel}")
        try:
            data = json.loads(blob) if blob else None
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            out.append((sha, data))
    return out


# --- 모으기 -------------------------------------------------------------------


def task_state(task_id: str) -> dict:
    fm = parse_frontmatter(task_dir(task_id) / "activeContext.md")
    return {k: fm.get(k) for k in ("title", "status", "phase", "track", "branch")}


def timeline(task_id: str) -> dict:
    log = _git(
        "log", "--format=%H %cI", "--",
        f"memory-bank/{task_id}", f":(glob)workflow_design/**/*{task_id}*",
    )
    lines = [line.split(" ", 1) for line in (log or "").splitlines() if " " in line]
    if not lines:
        return {"commits": 0, "first": None, "last": None}
    return {"commits": len(lines), "first": lines[-1][1], "last": lines[0][1]}


def checkpoints(task_id: str) -> dict:
    base = task_dir(task_id) / "checkpoints"
    attempts, decisions, retries = [], [], {}
    for phase_dir in CP_PHASE_DIRS:
        folder = base / phase_dir
        if not folder.is_dir():
            continue
        for cp in sorted(folder.glob("*.md")):
            if "_retry" in cp.stem:
                retries[phase_dir] = retries.get(phase_dir, 0) + 1
            fm = parse_frontmatter(cp)
            for a in fm.get("attempts") or []:
                if isinstance(a, dict):
                    attempts.append({
                        "phase_dir": phase_dir, "n": a.get("n"),
                        "outcome": _t(a.get("outcome")), "back_to": a.get("back_to"),
                    })
            for d in fm.get("decisions") or []:
                if isinstance(d, dict) and d.get("decision"):
                    decisions.append({
                        "phase_dir": phase_dir, "decision": _t(d.get("decision")),
                        "rationale": _t(d.get("rationale")),
                    })
    return {"attempts": attempts, "decisions": decisions, "v1_retry_files": retries}


def validation_history(task_id: str) -> dict:
    path = workflow_design_root() / "05_scenario" / "validator" / f"VALIDATION_{task_id}.json"
    results = [
        (d.get("overall") or {}).get("pass") is True for _, d in versions_oldest_first(path)
    ]
    return {"committed_versions": len(results), "fail": results.count(False), "pass": results.count(True)}


def verify_rounds(task_id: str) -> list[dict]:
    """커밋된 VERIFY 버전을 라운드로 묶는다. 라운드마다 마지막 버전의 판정."""
    path = artifact_path(task_id, "4")
    rounds: list[dict] = []
    prev_sha = None
    for sha, data in versions_oldest_first(path) if path else []:
        if prev_sha is None or source_changed_between(prev_sha, sha):
            rounds.append({"round": len(rounds) + 1})
        rounds[-1].update({"status": data.get("status"), "commit": sha[:7],
                           "reason": _t(data.get("status_reason"))})
        prev_sha = sha
    return rounds


def final_verify(task_id: str) -> dict | None:
    path = artifact_path(task_id, "4")
    data, err = load_json(path) if path else (None, "경로 계산 실패")
    if err or not isinstance(data, dict):
        return None
    review = data.get("human_review") or {}
    non_pass = [
        {"criterion": _t(c.get("criterion")), "verdict": c.get("verdict")}
        for c in data.get("acceptance_criteria") or []
        if isinstance(c, dict) and c.get("verdict") not in (None, "PASS")
    ]
    _, stats = check_root_causes.validate_record(data)
    later, unprobed = [], []
    for rc_id, case, v in check_root_causes._variants(data):
        if v.get("origin") == "later":
            later.append(f"{rc_id}: {_t(case)}")
        if v.get("probe") == "not_probed":
            unprobed.append(f"{rc_id}: {_t(case)} — {_t(v.get('reason'))}")
    return {
        "status": data.get("status"),
        "status_reason": _t(data.get("status_reason")),
        "decision": review.get("decision"),
        "exceptions": [_t(e) for e in data.get("exceptions") or []],
        "non_pass_criteria": non_pass,
        "root_causes": stats,
        "later_variants": later,
        "not_probed_variants": unprobed,
    }


def dev_summary(task_id: str) -> dict | None:
    data, err = load_json(artifact_path(task_id, "3"))
    if err or not isinstance(data, dict):
        return None
    deviations = data.get("scope_deviations")
    fixes = data.get("rollback_fixes")
    return {
        "scope_deviations": [_t(d) for d in deviations] if isinstance(deviations, list) else [],
        "rollback_fixes": len(fixes) if isinstance(fixes, list) else 0,
        "fix_locus": sorted({f.get("fix_locus") for f in fixes or [] if isinstance(f, dict) and f.get("fix_locus")}),
    }


def plan_summary(task_id: str) -> dict | None:
    data, err = load_json(artifact_path(task_id, "1"))
    if err or not isinstance(data, dict):
        return None
    ca = data.get("codebase_analysis") or {}
    return {
        "target_files": len(ca.get("target_files") or []),
        "unresolved": len(ca.get("unresolved") or []),
        "exploration": ca.get("exploration"),
    }


def collect(task_id: str) -> dict:
    return {
        "task_id": task_id,
        "state": task_state(task_id),
        "timeline": timeline(task_id),
        "checkpoints": checkpoints(task_id),
        "validation": validation_history(task_id),
        "verify_rounds": verify_rounds(task_id),
        "verify": final_verify(task_id),
        "dev": dev_summary(task_id),
        "plan": plan_summary(task_id),
    }


# --- 출력 ---------------------------------------------------------------------


def render(h: dict) -> str:
    s, tl, cp = h["state"], h["timeline"], h["checkpoints"]
    out = [f"이력 — {h['task_id']}  {_t(s.get('title'))}",
           f"  상태 {s.get('status')} · Phase {s.get('phase')} · track {s.get('track') or '—'}",
           f"  커밋 {tl['commits']}건  {tl['first'] or '—'} → {tl['last'] or '—'}", ""]

    rounds = h["verify_rounds"]
    fails = sum(1 for r in rounds if r.get("status") == "FAIL")
    out.append(f"Phase 4 라운드 {len(rounds)} (FAIL {fails})")
    for r in rounds:
        out.append(f"  {r['round']}. {r.get('status')}  {r['commit']}  {r.get('reason') or ''}".rstrip())
    v = h["validation"]
    out.append(f"Phase 2a 독립검증 — 커밋된 결과 {v['committed_versions']}건 (FAIL {v['fail']} · PASS {v['pass']})")
    out.append("")

    retries = cp["v1_retry_files"]
    if cp["attempts"] or not retries:
        out.append(f"되돌아감 {len(cp['attempts'])}건 (체크포인트 attempts)")
    else:
        out.append("되돌아감 — v1 체크포인트라 attempts 대신 _retry 파일로 기록됨")
    for a in cp["attempts"]:
        out.append(f"  [{a['phase_dir']}] #{a['n']} → {a['back_to'] or '—'}  {a['outcome']}")
    if retries:
        out.append("  v1 _retry 파일: " + ", ".join(f"{k} {n}" for k, n in retries.items()))
    if fails and not cp["attempts"] and not retries:
        # 두 출처가 어긋난다 — VERIFY 이력에는 FAIL 이 있는데 체크포인트에는 되돌아간 기록이 없다
        out.append(f"  ⚠ Phase 4 FAIL {fails}회가 있었는데 체크포인트에 되돌아간 기록이 없다 — 기록 누락")
    out.append("")

    out.append(f"결정 {len(cp['decisions'])}건")
    for d in cp["decisions"]:
        out.append(f"  [{d['phase_dir']}] {d['decision']}")
        if d["rationale"]:
            out.append(f"      왜: {d['rationale']}")
    out.append("")

    vf = h["verify"]
    if vf is None:
        out.append("VERIFY 없음")
    else:
        out.append(f"VERIFY {vf['status']} · 승인 {vf['decision'] or '—'}  {vf['status_reason']}")
        for c in vf["non_pass_criteria"]:
            out.append(f"  {c['verdict']}  {c['criterion']}")
        for e in vf["exceptions"]:
            out.append(f"  예외  {e}")
        rc = vf["root_causes"]
        if rc["root_causes"]:
            o = rc["by_origin"]
            out.append(f"  뿌리 {rc['root_causes']} · 변종 {rc['variants']} "
                       f"(found {o['found']} · predicted {o['predicted']} · later {o['later']}) · 미확인 {rc['not_probed']}")
            for x in vf["later_variants"]:
                out.append(f"    later       {x}")
            for x in vf["not_probed_variants"]:
                out.append(f"    not_probed  {x}")
    dv = h["dev"]
    if dv is not None:
        out.append(f"DEV  범위 이탈 {len(dv['scope_deviations'])} · 롤백 수정 {dv['rollback_fixes']}"
                   + (f" ({', '.join(dv['fix_locus'])})" if dv["fix_locus"] else ""))
        for d in dv["scope_deviations"]:
            out.append(f"  {d}")
    pl = h["plan"]
    if pl is not None:
        ex = pl["exploration"] or {}
        out.append(f"PLAN 변경 대상 {pl['target_files']} · 미해결 {pl['unresolved']} · 조사 "
                   + (f"{ex.get('method')} (calls {ex.get('calls')}, main_reads {ex.get('main_reads')})" if ex else "기록 없음"))
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not is_valid_task_id(args.task_id):
        print(task_id_error(args.task_id), file=sys.stderr)
        return 2
    if not (task_dir(args.task_id) / "activeContext.md").is_file():
        print(f"memory-bank/{args.task_id}/activeContext.md 가 없다 — 시작하지 않은 태스크다", file=sys.stderr)
        return 2

    history = collect(args.task_id)
    print(json.dumps(history, ensure_ascii=False, indent=2) if args.json else render(history))
    return 0


if __name__ == "__main__":
    sys.exit(main())
