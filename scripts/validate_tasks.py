#!/usr/bin/env python3
"""tasks.json 을 검증한다 — 스키마, WRU 적격성, ID 유일성, 의존 관계.

왜 필요한가
-----------
태스크가 잘못 만들어지면 그 비용을 Phase 1~5 전체가 나눠 낸다. 추정 2시간짜리
태스크는 워크플로우 오버헤드가 작업보다 크고, 순환 의존은 어느 것도 시작할 수 없게
만들고, 중복 ID 는 산출물 경로를 충돌시킨다. 태스크를 만드는 두 경로(/wf-task-new,
/wf-tasks-from-doc)가 모두 이것을 통과해야 tasks.json 에 들어간다.

판정 기준의 정본은 docs/workflow/task-schema.md 다. 이 스크립트는 그중
기계로 확인 가능한 것만 검사한다.

사용
----
    python3 scripts/validate_tasks.py
    python3 scripts/validate_tasks.py --file /tmp/candidate.json
    python3 scripts/validate_tasks.py --json
    python3 scripts/validate_tasks.py --strict      # 경고도 실패로 취급

exit code
---------
    0  통과 (--strict 가 아니면 경고는 통과)
    1  오류 있음
    2  파일을 읽을 수 없음

이 검사가 못 잡는 것
-------------------
"이 태스크가 정말 4~16시간인가"는 판단하지 않는다 — 적힌 추정치를 믿는다.
acceptance_criteria 가 실제로 검증 가능한지도 보지 않는다(사람과 Phase 2a 의 몫).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _utils import REQ_ID_RE, TASK_ID_RE, load_json, task_id_error, workflow_design_root  # noqa: E402

VALID_CATEGORIES = {"Backend", "Frontend", "Database"}
VALID_PRIORITY = {"High", "Medium", "Low"}
VALID_STATUS = {"todo", "in_progress", "done", "blocked"}

MIN_HOURS = 4
MAX_HOURS = 16
MIN_COMPLEXITY = 30


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, task_id: str, message: str) -> None:
        self.errors.append(f"{task_id}: {message}")

    def warn(self, task_id: str, message: str) -> None:
        self.warnings.append(f"{task_id}: {message}")


def check_schema(task: dict, report: Report) -> str:
    task_id = str(task.get("id", "<id 없음>"))

    if not task.get("id"):
        report.error("<id 없음>", "id 필드가 없다")
    elif not TASK_ID_RE.match(task_id):
        report.error(task_id, task_id_error(task_id))

    for field in ("title", "description"):
        if not str(task.get(field, "")).strip():
            report.error(task_id, f"{field} 가 비어 있다")

    category = task.get("primary_category")
    if category not in VALID_CATEGORIES:
        report.error(task_id, f"primary_category 가 {sorted(VALID_CATEGORIES)} 중 하나가 아니다: {category!r}")

    subs = task.get("sub_categories")
    if not isinstance(subs, list):
        report.error(task_id, "sub_categories 는 배열이어야 한다")
    elif category != "Frontend" and subs:
        report.warn(task_id, f"primary_category 가 {category} 인데 sub_categories 가 채워져 있다")

    priority = task.get("priority")
    if priority is not None and priority not in VALID_PRIORITY:
        report.warn(task_id, f"priority 가 {sorted(VALID_PRIORITY)} 중 하나가 아니다: {priority!r}")

    status = task.get("status")
    if status is not None and status not in VALID_STATUS:
        report.error(task_id, f"status 가 {sorted(VALID_STATUS)} 중 하나가 아니다: {status!r}")

    if not isinstance(task.get("depends_on", []), list):
        report.error(task_id, "depends_on 은 배열이어야 한다")

    return task_id


def check_wru(task: dict, task_id: str, report: Report) -> None:
    """WRU 적격성. docs/workflow/task-schema.md §1"""
    meta = task.get("meta") or {}

    criteria = meta.get("acceptance_criteria")
    if not isinstance(criteria, list) or not criteria:
        report.error(task_id, "meta.acceptance_criteria 가 비어 있다 — 완료를 판정할 수 없다")
    elif len(criteria) < 2:
        report.warn(task_id, f"acceptance_criteria 가 {len(criteria)}건뿐이다 — 오류 경로를 빠뜨렸을 수 있다")

    estimate = meta.get("estimate") or {}
    value = estimate.get("value")
    if value is None:
        report.error(task_id, "meta.estimate.value 가 없다")
    elif not isinstance(value, (int, float)):
        report.error(task_id, f"meta.estimate.value 가 숫자가 아니다: {value!r}")
    else:
        if value < MIN_HOURS:
            report.error(
                task_id,
                f"추정 {value}h — {MIN_HOURS}h 미만은 워크플로우 오버헤드가 더 크다. "
                "인접 태스크와 합쳐라 (task-schema.md §1 크기 기준)",
            )
        elif value > MAX_HOURS:
            report.error(
                task_id,
                f"추정 {value}h — {MAX_HOURS}h 초과는 WRU 하나로 크다. 둘로 나눠라",
            )

    complexity = meta.get("complexity") or {}
    total = complexity.get("total_score")
    if isinstance(total, (int, float)) and total < MIN_COMPLEXITY:
        report.warn(
            task_id,
            f"complexity.total_score {total} < {MIN_COMPLEXITY} — WRU 부적격 후보다",
        )

    spec = meta.get("implementation_spec") or {}
    paths = spec.get("paths")
    if paths is not None and not isinstance(paths, list):
        report.error(task_id, "meta.implementation_spec.paths 는 배열이어야 한다")


def check_graph(tasks: list[dict], report: Report) -> None:
    """ID 유일성, 의존 대상 존재, 순환 의존."""
    seen: dict[str, int] = {}
    for index, task in enumerate(tasks):
        task_id = str(task.get("id", ""))
        if not task_id:
            continue
        if task_id in seen:
            report.error(task_id, f"ID 중복 — {seen[task_id]}번째와 {index}번째 항목")
        seen[task_id] = index

    known = set(seen)
    edges: dict[str, list[str]] = {}
    for task in tasks:
        task_id = str(task.get("id", ""))
        deps = task.get("depends_on") or []
        if not isinstance(deps, list):
            continue
        edges[task_id] = [str(d) for d in deps]
        for dep in deps:
            if str(dep) not in known:
                report.error(task_id, f"depends_on 이 존재하지 않는 태스크를 가리킨다: {dep}")
            elif str(dep) == task_id:
                report.error(task_id, "자기 자신에 의존한다")

    # 순환 탐지 (DFS)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {task_id: WHITE for task_id in edges}

    def visit(node: str, stack: list[str]) -> None:
        color[node] = GRAY
        for nxt in edges.get(node, []):
            if nxt not in color:
                continue
            if color[nxt] == GRAY:
                cycle = stack[stack.index(nxt):] + [nxt] if nxt in stack else [node, nxt]
                report.error(node, "순환 의존: " + " → ".join(cycle))
            elif color[nxt] == WHITE:
                visit(nxt, stack + [nxt])
        color[node] = BLACK

    for task_id in list(color):
        if color[task_id] == WHITE:
            visit(task_id, [task_id])

    # 요청(REQ)에서 나온 태스크 — 요청 ID 형식 (brief-schema.md §1)
    for task in tasks:
        req = (task.get("source_refs") or {}).get("request_id")
        if req is not None and not REQ_ID_RE.match(str(req)):
            report.error(str(task.get("id", "")),
                         f"source_refs.request_id 형식이 아니다: {req!r} — 'REQ-' + 숫자 3자리 이상")

    # FE 태스크가 BE 를 선행으로 두는 관행 확인
    by_id = {str(t.get("id", "")): t for t in tasks}
    for task in tasks:
        if task.get("primary_category") != "Frontend":
            continue
        deps = task.get("depends_on") or []
        if not any(by_id.get(str(d), {}).get("primary_category") == "Backend" for d in deps):
            source = (task.get("source_refs") or {}).get("source_file")
            if source:  # 문서에서 추출된 태스크만 — 단독 FE 태스크는 정상일 수 있다
                report.warn(
                    str(task.get("id", "")),
                    "Frontend 태스크인데 Backend 선행이 없다 — 같은 문서에 BE 태스크가 있다면 "
                    "depends_on 을 확인하라 (docs/README.md BE/FE 분리 원칙)",
                )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--file", help="검사할 파일 (기본: workflow_design/02_tasks/tasks.json)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="경고도 실패로 취급")
    args = parser.parse_args()

    path = Path(args.file) if args.file else workflow_design_root() / "02_tasks" / "tasks.json"
    data, err = load_json(path)
    if err:
        print(err, file=sys.stderr)
        return 2
    if not isinstance(data, list):
        print(f"tasks.json 은 태스크 객체의 배열이어야 한다 (받은 타입: {type(data).__name__})", file=sys.stderr)
        return 2

    report = Report()
    for task in data:
        if not isinstance(task, dict):
            report.errors.append(f"<배열 항목>: 객체가 아니다: {task!r}")
            continue
        task_id = check_schema(task, report)
        check_wru(task, task_id, report)
    check_graph([t for t in data if isinstance(t, dict)], report)

    failed = bool(report.errors) or (args.strict and bool(report.warnings))

    if args.json:
        print(
            json.dumps(
                {
                    "status": "fail" if failed else "pass",
                    "task_count": len(data),
                    "errors": report.errors,
                    "warnings": report.warnings,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if failed else 0

    for message in report.errors:
        print(f"  ✗ {message}")
    for message in report.warnings:
        print(f"  ⚠ {message}")

    print()
    if report.errors:
        print(f"태스크 {len(data)}건 중 오류 {len(report.errors)}건, 경고 {len(report.warnings)}건")
        return 1
    if report.warnings:
        print(f"태스크 {len(data)}건 — 오류 없음, 경고 {len(report.warnings)}건")
        return 1 if args.strict else 0
    print(f"태스크 {len(data)}건 모두 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
