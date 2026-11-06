#!/usr/bin/env python3
"""Phase 2a 입력 경계 행렬 — 시나리오가 덮어야 할 칸을 PLAN 에서 기계적으로 만든다.

왜 필요한가
-----------
Phase 2a 재시도의 대부분이 독립검증 V11(입력 경계값) FAIL 이었다. 17개 태스크의 재시도 86회 중
39회가 2a 였고, TASK-016 은 V11 로만 9번 FAIL 했다. 원인은 **덮어야 할 칸이 정해져 있지 않았던 것**
이다. 검증자가 회차마다 `coverage-policy.md` §2-1 을 읽고 행렬을 새로 만들었고, 같은 경계를 회차마다
다른 이름으로 적었다(TASK-016 의 v11_matrix 에 행 이름 49가지). 목표가 움직이니 고칠 때마다 옆 칸이
새로 나왔다.

여기서는 칸을 **PLAN 이 정한다.** Phase 1 이 입력 필드마다 종류(`kinds`)를 고르면, 이 스크립트가
아래 목록(`KINDS`)에서 칸을 펼친다. 작성자는 모든 칸에 `covered`(SC-ID) 또는 `n/a`(사유)를 적고,
게이트가 빠진 칸을 기계로 센다. 검증자는 칸을 찾는 대신 **적힌 판정이 맞는지**를 본다.

칸 목록은 `coverage-policy.md` §2-1 표를 옮긴 것이다. 표에 행을 더하면 여기에도 더한다.

입력 — PLAN `design.input_fields`
--------------------------------
    "input_fields": [
      { "field": "password", "flows": ["F1"], "kinds": ["required", "string", "string_stored"],
        "max": 72, "note": "UTF-8 72바이트" }
    ]

입력이 없는 태스크는 `"input_fields": []` 와 `"input_fields_none_reason"` 을 적는다.

출력 — SCENARIO json `coverage_matrix`
-------------------------------------
    "coverage_matrix": [
      { "cell": "password@F1:string.max+1", "state": "covered", "by": ["SC-04"] },
      { "cell": "password@F1:string_stored.nul", "state": "n/a",
        "reason": "클라이언트는 검사하지 않고 서버 400 에 맡긴다 — PLAN constraints" }
    ]

사용
----
    python3 scripts/coverage_matrix.py --kinds                     # 고를 수 있는 종류와 칸
    python3 scripts/coverage_matrix.py --task-id TASK-001          # 칸별 상태
    python3 scripts/coverage_matrix.py --task-id TASK-001 --skeleton   # coverage_matrix 초안 JSON
    python3 scripts/coverage_matrix.py --task-id TASK-001 --json
    python3 scripts/coverage_matrix.py --check-policy              # §2-1 표와 KINDS 가 맞는가

exit code
    0  모든 칸이 판정됨
    1  빠진 칸·잘못된 판정·PLAN 결함
    2  인자 오류 / 파일을 읽을 수 없음

이 검사가 못 잡는 것
-------------------
`covered` 라고 적은 시나리오가 그 값을 *실제로* 쓰는지, `n/a` 사유가 타당한지는 보지 않는다.
그것은 scenario-validator 의 V11 이 본다. 종류를 잘못 고른 필드(저장되는 문자열인데
`string_stored` 를 빠뜨림)도 검증자가 PLAN 결함으로 지적한다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _utils import artifact_path, is_valid_task_id, load_json, task_id_error  # noqa: E402

#: 종류 → (칸 ID, 설명). coverage-policy.md §2-1 의 행과 같은 순서로 둔다.
KINDS: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "required": ("필수 필드", [
        ("missing", "누락"),
        ("null", "null"),
    ]),
    "json_field": ("JSON 본문의 필드", [
        ("wrong_type", "다른 JSON 타입(숫자·객체·배열·불리언 등)"),
    ]),
    "json_body": ("JSON 요청 본문 자체", [
        ("empty", "본문 비어 있음"),
        ("not_json", "JSON 아님"),
    ]),
    "string": ("문자열", [
        ("empty", "빈 값"),
        ("blank", "공백만"),
        ("max+1", "최대 길이 + 1"),
    ]),
    "string_stored": ("저장·비교되는 문자열 (로그인처럼 비교만 하는 입력 포함)", [
        ("nul", "NUL"),
        ("surrogate", "짝 없는 서로게이트"),
        ("normalized", "정규화·대소문자 변환 후 길이·동일성"),
    ]),
    "integer": ("정수", [
        ("negative", "음수"),
        ("zero", "0"),
        ("max+1", "상한 + 1"),
        ("fraction", "소수 (1.9)"),
        ("overflow", "타입 범위 초과"),
    ]),
    "integer_notation": ("외부가 적는 정수 (JSON·토큰 클레임)", [
        ("numeric_string", "숫자 문자열 (\"1700000000\")"),
        ("integral_fraction", "정수값 소수 (1700000000.0)"),
        ("exponent", "지수 (1.7e9)"),
        ("type_range", "받는 타입(long·Instant)의 표기 범위 초과"),
    ]),
    "opaque": ("요청에 실린 불투명 문자열 (토큰·코드·서명)", [
        ("affix_entry", "앞뒤에 붙은 문자(=·~·공백·LF·NUL·서로게이트·비 ASCII)를 실제 입구로"),
    ]),
    "multi_param": ("여러 파라미터로 분기하는 입력 — 같은 group 끼리", [
        ("one_empty", "한쪽 빈 + 다른 쪽 유효 (각 방향)"),
        ("both", "둘 다 값"),
        ("none", "둘 다 없음"),
    ]),
    "array": ("배열", [
        ("empty", "빈 배열"),
        ("null_element", "null 원소"),
        ("max+1", "최대 개수 + 1"),
    ]),
    "enum": ("열거형", [
        ("undefined", "정의 밖 값"),
        ("each", "정의된 값 각각 (필터·분기라면)"),
    ]),
    "datetime": ("시각 비교", [
        ("now_eq_boundary", "now == 경계 — 같은 비교를 하는 코드 경로마다"),
    ]),
    "config": ("환경변수·헤더 값", [
        ("unset", "미설정 / 헤더 부재"),
        ("empty", "빈 문자열"),
        ("blank", "공백만"),
        ("case", "대소문자 (TRUE)"),
        ("notation", "표기 변형 (1·yes)"),
        ("list_separator", "쉼표 목록의 연속 구분자·앞뒤 공백"),
        ("prefix_only", "접두사만 일치"),
    ]),
    "server_response": ("서버 응답의 code·본문으로 분기", [
        ("other_code", "같은 상태에 다른 code"),
        ("empty_body", "빈 바디"),
        ("non_json", "비 JSON 본문"),
    ]),
    "error_state": ("오류 상태를 켜는 입력", [
        ("reset_on_resubmit", "재제출 시 꺼짐"),
    ]),
    "async_result": ("비동기 결과를 상태에 적용", [
        ("session_change", "응답 전 로그인·로그아웃"),
        ("leave", "응답 전 언마운트·화면 이동·StrictMode 취소"),
        ("late_failure", "늦게 오는 401·5xx·네트워크 오류·비 JSON"),
    ]),
    "converted": ("프레임워크가 변환한 뒤 판정하는 값", [
        ("raw_vs_converted", "Given 에 변환 전·후 중 어느 쪽인지 + 대소문자·공백·숫자 표기·타입 변형"),
        ("real_entry", "변환 계층을 실제로 통과하는 시나리오"),
    ]),
}

STATES = ("covered", "n/a")
SC_ID_RE = re.compile(r"^SC-\d+$")


POLICY = Path(__file__).resolve().parent.parent / ".claude/skills/wf-scenario/references/coverage-policy.md"


def policy_drift() -> list[str]:
    """coverage-policy.md §2-1 표의 종류 이름과 KINDS 가 어긋난 것."""
    if not POLICY.is_file():
        return [f"{POLICY} 가 없다"]
    text = POLICY.read_text(encoding="utf-8")
    section = text[text.find("### 2-1"):text.find("### 2-2")]
    in_table = set(re.findall(r"^\|[^|\n]*`([a-z_]+)` \|", section, re.M))
    return ([f"표에 없는 kind: {k}" for k in sorted(set(KINDS) - in_table)]
            + [f"KINDS 에 없는 표 행: {k}" for k in sorted(in_table - set(KINDS))])


def cell_key(field: str, flow: str, kind: str, cell: str) -> str:
    return f"{field}@{flow}:{kind}.{cell}"


def required_cells(plan: dict) -> tuple[list[dict], list[str]]:
    """PLAN 의 input_fields 를 칸으로 펼친다. (칸 목록, PLAN 결함)"""
    design = plan.get("design") or {}
    problems: list[str] = []
    if "input_fields" not in design:
        return [], ["PLAN design.input_fields 가 없다 — 입력 필드마다 flows·kinds 를 적는다 "
                    "(입력이 없으면 [] 와 input_fields_none_reason)"]
    fields = design.get("input_fields")
    if not isinstance(fields, list):
        return [], ["design.input_fields 가 배열이 아니다"]
    if not fields:
        if not str(design.get("input_fields_none_reason") or "").strip():
            problems.append("input_fields 가 비었는데 input_fields_none_reason 이 없다")
        return [], problems

    flow_ids = {f.get("id") for f in design.get("flows") or [] if isinstance(f, dict)}
    cells: list[dict] = []
    seen_fields: set[str] = set()
    for i, f in enumerate(fields):
        if not isinstance(f, dict):
            problems.append(f"input_fields[{i}] 가 객체가 아니다")
            continue
        name = str(f.get("field") or "").strip()
        if not name or any(c in name for c in "@:"):
            problems.append(f"input_fields[{i}].field 가 비었거나 '@'·':' 를 담고 있다")
            continue
        if name in seen_fields:
            problems.append(f"input_fields 에 {name!r} 가 두 번 있다 — 흐름은 flows 에 모은다")
        seen_fields.add(name)
        flows = f.get("flows") or []
        kinds = f.get("kinds") or []
        if not flows:
            problems.append(f"{name}: flows 가 비었다")
        if not kinds:
            problems.append(f"{name}: kinds 가 비었다 — `--kinds` 로 목록을 본다")
        for flow in flows:
            if flow_ids and flow not in flow_ids:
                problems.append(f"{name}: flow {flow!r} 가 design.flows 에 없다")
        for kind in kinds:
            if kind not in KINDS:
                problems.append(f"{name}: 알 수 없는 kind {kind!r} — `--kinds` 로 목록을 본다")
                continue
            if kind == "multi_param" and not str(f.get("group") or "").strip():
                problems.append(f"{name}: multi_param 은 함께 분기하는 필드끼리 같은 group 을 적는다")
            for flow in flows:
                for cid, desc in KINDS[kind][1]:
                    cells.append({"cell": cell_key(name, flow, kind, cid), "field": name,
                                  "flow": flow, "kind": kind, "desc": desc})
    return cells, problems


def judge(cells: list[dict], scenario: dict | None) -> dict:
    """SCENARIO 의 coverage_matrix 를 칸 목록에 대본다."""
    entries = (scenario or {}).get("coverage_matrix")
    sc_ids = {s.get("id") for s in (scenario or {}).get("scenarios") or [] if isinstance(s, dict)}
    by_cell: dict[str, dict] = {}
    problems: list[str] = []
    if scenario is not None and not isinstance(entries, list):
        problems.append("SCENARIO json 에 coverage_matrix 배열이 없다 — `--skeleton` 으로 초안을 만든다")
        entries = []
    for e in entries or []:
        if isinstance(e, dict) and isinstance(e.get("cell"), str):
            if e["cell"] in by_cell:
                problems.append(f"{e['cell']}: 두 번 적혀 있다")
            by_cell[e["cell"]] = e

    rows = []
    for c in cells:
        e = by_cell.get(c["cell"])
        state, note = "missing", ""
        if e is not None:
            state = e.get("state")
            if state == "covered":
                by = e.get("by") or []
                bad = [b for b in by if not (isinstance(b, str) and SC_ID_RE.match(b) and b in sc_ids)]
                if not by:
                    note = "covered 인데 by 가 비었다"
                elif bad:
                    note = f"by 에 없는 시나리오 {bad}"
                else:
                    note = ", ".join(by)
            elif state == "n/a":
                note = str(e.get("reason") or "").strip()
                if not note:
                    note = "n/a 인데 reason 이 없다"
                    state = "invalid"
            else:
                note = f"state 는 {STATES} 중 하나 — {state!r}"
                state = "invalid"
            if state == "covered" and (not e.get("by") or note.startswith("by 에")):
                state = "invalid"
        rows.append({**c, "state": state, "note": note})

    required = {c["cell"] for c in cells}
    extra = sorted(k for k in by_cell if k not in required)
    missing = [r["cell"] for r in rows if r["state"] == "missing"]
    invalid = [f"{r['cell']} — {r['note']}" for r in rows if r["state"] == "invalid"]
    return {"rows": rows, "missing": missing, "invalid": invalid, "extra": extra,
            "problems": problems}


def evaluate(task_id: str) -> tuple[dict, int]:
    plan_path = artifact_path(task_id, "1")
    plan, err = load_json(plan_path) if plan_path else (None, "경로 계산 실패")
    if not isinstance(plan, dict):
        return {"error": f"PLAN 을 읽을 수 없다 — {err}"}, 2
    cells, plan_problems = required_cells(plan)
    sc_path = artifact_path(task_id, "2a")
    scenario = None
    if sc_path and sc_path.is_file():
        scenario, _ = load_json(sc_path)
        if not isinstance(scenario, dict):
            scenario = None
    result = judge(cells, scenario) if scenario is not None else {
        "rows": [{**c, "state": "missing", "note": ""} for c in cells],
        "missing": [c["cell"] for c in cells], "invalid": [], "extra": [],
        "problems": ["SCENARIO json 이 아직 없다"]}
    result["plan_problems"] = plan_problems
    result["total"] = len(cells)
    failed = plan_problems or result["missing"] or result["invalid"] or result["problems"]
    return result, 1 if failed else 0


def render(task_id: str, r: dict) -> str:
    lines = [f"입력 경계 행렬 — {task_id}   칸 {r['total']}", ""]
    for p in r["plan_problems"]:
        lines.append(f"  ✗ PLAN  {p}")
    for p in r["problems"]:
        lines.append(f"  ✗ {p}")
    for row in r["rows"]:
        mark = {"covered": "✓", "n/a": "–"}.get(row["state"], "✗")
        lines.append(f"  {mark} {row['cell']:<48} {row['state']:<8} {row['note'] or row['desc']}")
    for e in r["extra"]:
        lines.append(f"  ? {e}  — PLAN 이 만들지 않는 칸 (kind·field 이름을 확인)")
    done = r["total"] - len(r["missing"]) - len(r["invalid"])
    lines += ["", f"판정 {done}/{r['total']} · 빠짐 {len(r['missing'])} · 잘못 {len(r['invalid'])}"
              + (f" · 목록 밖 {len(r['extra'])}" if r["extra"] else "")]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--task-id")
    parser.add_argument("--kinds", action="store_true", help="고를 수 있는 종류와 칸을 보여준다")
    parser.add_argument("--skeleton", action="store_true",
                        help="SCENARIO json 의 coverage_matrix 초안(모든 칸 state 빈 값)을 출력한다")
    parser.add_argument("--check-policy", action="store_true",
                        help="coverage-policy.md §2-1 표와 KINDS 가 맞는지 본다")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.check_policy:
        drift = policy_drift()
        print("\n".join(drift) if drift else f"일치 — kind {len(KINDS)}")
        return 1 if drift else 0
    if args.kinds:
        for kind, (title, cells) in KINDS.items():
            print(f"{kind:<18} {title}")
            for cid, desc in cells:
                print(f"    .{cid:<20} {desc}")
        return 0
    if not args.task_id or not is_valid_task_id(args.task_id):
        print(task_id_error(args.task_id or ""), file=sys.stderr)
        return 2

    result, code = evaluate(args.task_id)
    if "error" in result:
        print(result["error"], file=sys.stderr)
        return code
    if args.skeleton:
        done = {row["cell"]: row for row in result["rows"] if row["state"] in STATES}
        skel = []
        for row in result["rows"]:
            if row["cell"] in done:
                continue
            skel.append({"cell": row["cell"], "state": "", "by": [], "reason": "",
                         "desc": row["desc"]})
        print(json.dumps(skel, ensure_ascii=False, indent=2))
        return 0
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render(args.task_id, result))
    return code


if __name__ == "__main__":
    sys.exit(main())
