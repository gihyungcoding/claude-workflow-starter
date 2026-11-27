#!/usr/bin/env python3
"""Phase 4 가 수렴하는가 — 태스크별 라운드 수와 뒤늦은 변종, 그리고 실패 유형 카탈로그 후보.

왜 필요한가
-----------
Phase 4 FAIL 이 같은 노출면의 다른 칸 때문에 3~4라운드 반복됐다(ssirleague TASK-004 4라운드 · ticket-booking TASK-009
Phase 4 커밋 7개). 그래서 세 장치를 두었다 — 이 변경이 만든 결함만 FAIL(scope), 기대 결과가 정해진 결함은
2a 대신 Phase 3 에서(RETRY_FIX), 노출면의 칸을 2a 에서 미리(실패 유형 카탈로그). 이 스크립트는 그것이 **효과가 있는지**를
숫자로 보이고, 카탈로그를 키울 재료를 모은다. 이것이 자기 개선 루프의 측정과 입력이다:

    Phase 4 의 later·넘긴 변종 ─► --candidates ─► 회고 rule_proposals ─► /wf-retro 승인 ─► failure-modes.md
         ▲                                                                                       │
         └──────────── 다음 태스크의 2a 가 그 칸을 시나리오로 (coverage_matrix) ◄──────────────────┘

보는 것 (VERIFY_*.json 전부)
---------------------------
- 라운드 — VERIFY 의 `history`(이전 라운드 판정)와 지금 판정. `history` 가 없는 예전 VERIFY 는 git 이력에서 사이에 소스가
  바뀐 커밋을 새 라운드로 센다(check_root_causes.py 와 같은 기준) — 롤백 중에 기록만 고친 커밋이 한 라운드로 셀 수 있다
- `later` 변종 수 — 첫 라운드 스윕이 놓친 것. 카탈로그가 자라면 줄어야 한다
- 후속 태스크로 넘긴 변종 수 — 범위 판단이 늘기만 하면 사람이 본다
- `--candidates` — `later` 이거나 넘긴 변종 중 카탈로그 출처 열에 `TASK-NNN RC-n` 이 아직 없는 것

사용
----
    python3 scripts/verify_convergence.py                 # 태스크별 표와 평균
    python3 scripts/verify_convergence.py --candidates    # 카탈로그 후보 (회고·/wf-retro 가 쓴다)
    python3 scripts/verify_convergence.py --json

exit code — 0 (보고만 한다), 2 (읽을 수 없는 파일이 있어도 나머지는 보고하고 0)

이 검사가 못 잡는 것
-------------------
후보가 정말 노출면의 일반 규칙인지, 이 태스크에만 있던 일인지는 모른다. 사람이 /wf-retro 에서 고른다.
라운드 수는 커밋된 VERIFY 에 기댄다 — 판정을 커밋하지 않고 넘긴 라운드는 세지 못한다.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _utils import load_json, repo_root, source_changed_between, workflow_design_root  # noqa: E402

CATALOG_REL = "docs/architecture/failure-modes.md"
TASK_RE = re.compile(r"VERIFY_(TASK-\d{3,})\.json$")


def _variants(data: dict):
    for rc in data.get("root_causes") or []:
        if isinstance(rc, dict):
            for v in rc.get("variants") or []:
                if isinstance(v, dict):
                    yield rc, v


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=repo_root(), capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def round_statuses(path: Path, data: dict) -> list[object]:
    """라운드마다 판정. `history` 가 있으면 그것을, 없으면(예전 VERIFY) git 이력을 쓴다."""
    history = [h for h in data.get("history") or [] if isinstance(h, dict)]
    if history:
        statuses = [h.get("status") for h in history]
        if history[-1].get("human_review") != data.get("human_review"):
            statuses.append(data.get("status"))   # history 의 마지막이 지금 판정이 아니면 더한다
        return statuses
    # git 이력: 커밋 사이에 소스가 바뀌면 새 라운드 (check_root_causes.py 와 같은 기준)
    rel = str(path.resolve().relative_to(repo_root().resolve()))
    rounds: list[object] = []
    prev = None
    for sha in (_git("log", "--reverse", "--format=%H", "--", rel) or "").split():
        blob = _git("show", f"{sha}:{rel}")
        try:
            status = json.loads(blob).get("status") if blob else None
        except (json.JSONDecodeError, AttributeError):
            continue
        if prev is None or source_changed_between(prev, sha):
            rounds.append(status)
        else:
            rounds[-1] = status
        prev = sha
    if rounds:
        rounds[-1] = data.get("status")   # 작업 트리의 지금 판정
        return rounds
    return [data.get("status")]


def summarize(task_id: str, data: dict, path: Path) -> dict:
    statuses = round_statuses(path, data)
    later = deferred = 0
    for _, v in _variants(data):
        later += v.get("origin") == "later"
        deferred += bool(v.get("deferred_to"))
    return {"task_id": task_id, "rounds": len(statuses), "fail_rounds": statuses.count("FAIL"),
            "status": data.get("status"), "later": later, "deferred": deferred}


def candidates(task_id: str, data: dict, catalog_text: str) -> list[dict]:
    out = []
    for rc, v in _variants(data):
        if not (v.get("origin") == "later" or v.get("deferred_to")):
            continue
        ref = f"{task_id} {rc.get('id')}"
        if re.search(rf"\b{re.escape(task_id)}\b[^|\n]*\b{re.escape(str(rc.get('id')))}\b", catalog_text):
            continue   # 카탈로그 출처 열에 이미 있다
        out.append({"ref": ref, "root_cause": rc.get("summary", ""), "case": v.get("case", ""),
                    "why": "later" if v.get("origin") == "later" else f"넘김 → {v.get('deferred_to')}"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--candidates", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    catalog = repo_root() / CATALOG_REL
    catalog_text = catalog.read_text(encoding="utf-8") if catalog.is_file() else ""
    rows, cands, unreadable = [], [], []
    for path in sorted((workflow_design_root() / "07_verify").glob("VERIFY_TASK-*.json")):
        m = TASK_RE.search(path.name)
        data, err = load_json(path)
        if not m or not isinstance(data, dict):
            unreadable.append(path.name)
            continue
        rows.append(summarize(m.group(1), data, path))
        cands += candidates(m.group(1), data, catalog_text)

    def mean(key: str, rs: list[dict]) -> float:
        return round(sum(r[key] for r in rs) / len(rs), 2) if rs else 0.0

    recent = rows[-5:]
    report = {"tasks": rows, "mean_fail_rounds": mean("fail_rounds", rows), "mean_later": mean("later", rows),
              "recent5_fail_rounds": mean("fail_rounds", recent), "recent5_later": mean("later", recent),
              "candidates": cands, "unreadable": unreadable}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.candidates:
        print(f"실패 유형 카탈로그 후보 — {len(cands)}건 ({CATALOG_REL} 출처 열에 아직 없는 later·넘긴 변종)")
        for c in cands:
            print(f"  {c['ref']:<16} [{c['why']}] {c['case'][:90]}")
            print(f"  {'':<16} 뿌리: {c['root_cause'][:90]}")
        if not catalog_text:
            print(f"  ⚠ {CATALOG_REL} 가 없다 — 스타터의 것을 복사하면 시작 칸이 들어 있다")
        return 0
    print(f"Phase 4 수렴 — 태스크 {len(rows)}건")
    for r in rows:
        bar = "■" * r["fail_rounds"]
        print(f"  {r['task_id']:<10} 라운드 {r['rounds']} · FAIL {r['fail_rounds']} {bar:<5} "
              f"later {r['later']:<3} 넘김 {r['deferred']:<3} {r['status'] or ''}")
    print()
    print(f"  FAIL 라운드 평균 {report['mean_fail_rounds']} (최근 5건 {report['recent5_fail_rounds']}) · "
          f"later 평균 {report['mean_later']} (최근 5건 {report['recent5_later']})")
    print(f"  카탈로그 후보 {len(cands)}건 — --candidates")
    for name in unreadable:
        print(f"  ⚠ 읽을 수 없다: {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
