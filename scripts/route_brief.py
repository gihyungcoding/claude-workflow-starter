#!/usr/bin/env python3
"""확정한 계획의 수정 범위(scope)를 후속 작업 목록(dispatch)으로 바꾼다.

왜 필요한가
-----------
"계획이 무엇을 바꾸는가"에 따라 뒤에 해야 할 일이 달라진다 — product.md 를 고칠지,
ADR 을 쓸지, 기능 문서를 만들지, 태스크를 몇 개 만들지. 이 판단을 매번 대화에서 다시 하면
빠뜨린다. 범위 플래그는 사람이 확정한 판단이고, 플래그 → 작업 변환은 기계적이므로 여기서 한다.

또 플래그는 에이전트의 판단이라 틀릴 수 있다. 근거 경로(scope.paths)로 교차 확인해
어긋나면 경고한다 — 마이그레이션 경로가 있는데 migration 이 false 인 경우 같은 것.

작업 순서 (brief-schema.md · wf-plan Dispatch)
--------------------------------------------
    init          Foundation 문서가 없거나 미완성 — 막지 않고 안내만 (/wf-init)
    product       product.md 범위 갱신
    adr           ADR 한 건마다
    architecture  architecture.md · constraints.yaml
    design        design.md §4·§5 · design-tokens.css
    feature_doc   태스크가 2개 이상이거나 새 화면 시안이 있으면 기능 문서(§1-2 표)
    tasks         tasks.json 에 태스크 생성
    start         첫 번째로 시작할 수 있는 태스크를 /wf-start
    direct        코드 변경이 없음 — 파이프라인 밖에서 처리

사용
----
    python3 scripts/route_brief.py --req REQ-001            # 작업 목록을 보여 준다
    python3 scripts/route_brief.py --req REQ-001 --write    # BRIEF.dispatch 에 쓴다 (이미 끝난 작업 상태는 보존)
    python3 scripts/route_brief.py --req REQ-001 --json

exit code
---------
    0  작업 목록을 만들었다 (경고는 있을 수 있다)
    1  확정되지 않은 계획이라 만들지 않았다 (--write 일 때)
    2  인자 오류 / BRIEF 를 읽을 수 없음
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _utils import brief_path, docs_root, is_valid_req_id, load_json  # noqa: E402

#: 경로 → 범위 교차 확인. 근거가 있으면 경고만 한다 (판단은 사람이 확정했다).
MIGRATION_RE = re.compile(r"(^|/)(migrations?|db/migrate|alembic|flyway|db/migration|liquibase)(/|$)", re.I)
FRONTEND_RE = re.compile(r"(^|/)(frontend|web|client|app/components|src/components|src/pages|src/screens)(/|$)"
                         r"|\.(tsx|jsx|vue|svelte|css|scss)$", re.I)

LOCKED_STATUSES = ("locked", "dispatched", "done")


def foundation_gaps() -> list[str]:
    """Foundation 문서 중 없거나 TODO 가 남은 것."""
    gaps = []
    for rel in ("product/product.md", "architecture/architecture.md"):
        p = docs_root() / rel
        if not p.is_file():
            gaps.append(f"docs/{rel} 없음")
        elif "TODO" in p.read_text(encoding="utf-8", errors="replace"):
            gaps.append(f"docs/{rel} 에 TODO 가 남아 있음")
    return gaps


def cross_check(scope: dict) -> list[str]:
    paths = [str(p) for p in scope.get("paths") or []]
    warns = []
    if any(MIGRATION_RE.search(p) for p in paths) and not scope.get("migration"):
        warns.append("근거 경로에 마이그레이션이 있는데 scope.migration 이 false 다")
    if any(FRONTEND_RE.search(p) for p in paths) and "Frontend" not in (scope.get("routes") or []):
        warns.append("근거 경로에 화면 코드가 있는데 scope.routes 에 Frontend 가 없다")
    if "Frontend" in (scope.get("routes") or []) and scope.get("ui") == "none":
        warns.append("Frontend 변경인데 scope.ui 가 none 이다 — 화면이 안 바뀌는지 확인한다")
    return warns


def plan_jobs(brief: dict) -> list[dict]:
    scope = brief.get("scope") or {}
    jobs: list[dict] = []

    def add(job: str, why: str, ref: str | None = None) -> None:
        jobs.append({"job": job, "why": why, **({"ref": ref} if ref else {})})

    gaps = foundation_gaps()
    if gaps:
        add("init", "; ".join(gaps))
    if not scope.get("wru"):
        add("direct", "프로덕션 코드 변경이 없다 — 태스크를 만들지 않고 처리한다")
        return jobs
    if scope.get("product_change"):
        add("product", "product.md 범위를 바꾼다")
    arch = scope.get("architecture") or {}
    for title in arch.get("adr") or []:
        add("adr", "확정한 결정을 ADR 로", ref=str(title))
    if arch.get("change"):
        add("architecture", "새 계층·의존 방향 — architecture.md 와 constraints.yaml")
    if scope.get("design_tokens"):
        add("design", "design.md §4·§5 와 design-tokens.css")
    split = brief.get("split") or []
    if len(split) >= 2 or scope.get("ui") == "mockup":
        add("feature_doc", "태스크 분할·화면 설계를 기능 문서로 남긴다")
    add("tasks", f"태스크 {len(split)}개 생성")
    ready = [t for t in split if isinstance(t, dict) and not t.get("depends_on")]
    add("start", "선행이 없는 첫 태스크", ref=(ready[0].get("key") if ready else None))
    return jobs


def merge(existing: list[dict], planned: list[dict]) -> list[dict]:
    """이미 끝낸 작업의 상태는 보존한다 — 같은 (job, ref) 를 같은 작업으로 본다."""
    done = {(j.get("job"), j.get("ref")): j for j in existing if isinstance(j, dict)}
    out = []
    for j in planned:
        prev = done.get((j["job"], j.get("ref")))
        out.append({**j, "status": prev.get("status", "pending") if prev else "pending",
                    **({"result": prev["result"]} if prev and "result" in prev else {})})
    return out


def write_atomic(path: Path, data: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".brief-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--req", required=True)
    ap.add_argument("--write", action="store_true", help="BRIEF.dispatch 에 쓴다")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not is_valid_req_id(args.req):
        print(f"요청 ID 형식이 아니다: {args.req!r}", file=sys.stderr)
        return 2
    path = brief_path(args.req)
    brief, msg = load_json(path)
    if not isinstance(brief, dict):
        print(f"✗ {msg or 'BRIEF 가 객체가 아니다'}", file=sys.stderr)
        return 2

    jobs = merge(brief.get("dispatch") or [], plan_jobs(brief))
    warnings = cross_check(brief.get("scope") or {})

    if args.write:
        if brief.get("status") not in LOCKED_STATUSES:
            print(f"✗ 확정되지 않은 계획이다 (status={brief.get('status')!r}) — Lock 뒤에 만든다", file=sys.stderr)
            return 1
        brief["dispatch"] = jobs
        write_atomic(path, brief)

    if args.json:
        print(json.dumps({"req": args.req, "jobs": jobs, "warnings": warnings}, ensure_ascii=False, indent=2))
    else:
        print(f"{args.req} 후속 작업 {len(jobs)}건{' (BRIEF 에 씀)' if args.write else ''}")
        for j in jobs:
            ref = f" [{j['ref']}]" if j.get("ref") else ""
            print(f"  {j['status']:8} {j['job']}{ref} — {j['why']}")
        for w in warnings:
            print(f"  ⚠ {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
