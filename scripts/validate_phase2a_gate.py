#!/usr/bin/env python3
"""Phase 2a EXIT GATE 를 자동 검증한다.

왜 필요한가
-----------
Phase 2a 를 수행한 에이전트가 스스로 "게이트 통과"라고 판정하면 검증이 순환한다. 이 스크립트는
산출물 파일만 보고 판정하므로 에이전트의 자기신고와 무관하다. wf-scenario 스킬이 HITL#1 승인
직후 실행하고, exit 0 이 아니면 Phase 2b 로 넘어갈 수 없다.

원본 대비 간소화
---------------
원본의 같은 게이트는 14조건이었고 그중 상당수가 plan_hash sha256 대조, 검증자 모델 ID 확인,
프롬프트 이중 저장 검사 같은 위변조 방지 장치였다. 여기서는 검증자 서브에이전트가
tools allowlist 상 파일을 쓸 수 없으므로 위변조 경로 자체가 없다. 남은 6조건은 모두
"산출물이 실제로 그렇게 되어 있는가"를 묻는다.

사용
----
    python scripts/validate_phase2a_gate.py --task-id TASK-001
    python scripts/validate_phase2a_gate.py --task-id TASK-001 --skip-hitl

exit code
---------
    0  전 조건 통과
    1  하나 이상 실패
    2  인자 오류 / 파일 부재로 판정 불가

이 검사가 못 잡는 것
-------------------
시나리오 문장의 품질은 보지 않는다. Then 이 관찰 가능한지, 구현이 누출됐는지는
scenario-validator 서브에이전트가 판정하고, 이 스크립트는 그 결과(overall.pass)만 확인한다.
"""

from __future__ import annotations

import argparse
import sys

from _utils import (
    artifact_path,
    is_valid_task_id,
    load_json,
    task_dir,
    task_id_error,
    workflow_design_root,
)


class Result:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def check(self, name: str, passed: bool, detail: str = "") -> bool:
        self.rows.append((name, passed, detail))
        return passed

    @property
    def failed(self) -> int:
        return sum(1 for _, ok, _ in self.rows if not ok)

    def render(self, task_id: str) -> str:
        lines = [f"Phase 2a EXIT GATE — {task_id}", ""]
        for name, ok, detail in self.rows:
            mark = "✓" if ok else "✗"
            lines.append(f"  {mark} {name}")
            if detail:
                lines.append(f"      {detail}")
        lines.append("")
        if self.failed:
            lines.append(f"실패 {self.failed}/{len(self.rows)} — Phase 2b 진입 불가")
        else:
            lines.append(f"통과 {len(self.rows)}/{len(self.rows)} — Phase 2b 진입 가능")
        return "\n".join(lines)


def validate(task_id: str, skip_hitl: bool) -> Result:
    result = Result()
    scenario_dir = workflow_design_root() / "05_scenario"
    md_path = scenario_dir / f"SCENARIO_{task_id}.md"
    json_path = artifact_path(task_id, "2a")
    validation_path = scenario_dir / "validator" / f"VALIDATION_{task_id}.json"
    plan_path = artifact_path(task_id, "1")

    # 1. 산출물 존재
    have_md = md_path.is_file()
    have_json = json_path is not None and json_path.is_file()
    result.check(
        "산출물 존재 (SCENARIO .md + .json)",
        have_md and have_json,
        ""
        if (have_md and have_json)
        else f"md={'있음' if have_md else '없음'}, json={'있음' if have_json else '없음'}",
    )

    data, err = load_json(json_path) if json_path else (None, "경로 계산 실패")
    if not isinstance(data, dict):
        result.check("SCENARIO json 파싱", False, err or "객체가 아니다")
        return result
    result.check("SCENARIO json 파싱", True)

    scenarios = data.get("scenarios") or []

    # 2. 개수 하한
    types = [str(s.get("type", "")).lower() for s in scenarios]
    happy = types.count("happy")
    error = types.count("error")
    result.check(
        "시나리오 하한 (전체≥2, happy≥1, error≥1)",
        len(scenarios) >= 2 and happy >= 1 and error >= 1,
        f"전체 {len(scenarios)}, happy {happy}, error {error}",
    )

    # 3. acceptance_criteria 커버리지
    plan, plan_err = load_json(plan_path) if plan_path else (None, "경로 계산 실패")
    criteria = []
    if isinstance(plan, dict):
        criteria = plan.get("acceptance_criteria") or []
    covered = {c for s in scenarios for c in (s.get("covers") or [])}
    uncovered = [c for c in criteria if c not in covered]
    if not criteria:
        result.check(
            "acceptance_criteria 커버리지",
            False,
            plan_err or "PLAN 에 acceptance_criteria 가 없다 — Phase 1 을 확인하라",
        )
    else:
        result.check(
            "acceptance_criteria 커버리지",
            not uncovered,
            f"{len(criteria) - len(uncovered)}/{len(criteria)}"
            + (f" — 미커버: {uncovered}" if uncovered else ""),
        )

    # 4. 독립검증 통과
    validation, v_err = load_json(validation_path)
    if not isinstance(validation, dict):
        result.check("독립검증 결과 존재", False, v_err or "객체가 아니다")
    else:
        overall = validation.get("overall") or {}
        passed = overall.get("pass") is True
        fail_count = overall.get("fail_count")
        result.check(
            "독립검증 통과 (overall.pass)",
            passed,
            f"fail {fail_count}건 — {overall.get('summary', '')}" if not passed else "",
        )

    # 5. HITL#1 승인
    if skip_hitl:
        result.check("HITL#1 승인", True, "--skip-hitl 로 건너뜀")
    else:
        trigger = (data.get("human_input") or {}).get("generate_red_trigger")
        result.check(
            "HITL#1 승인 (generate_red_trigger)",
            trigger is True,
            "" if trigger is True else f"값이 {trigger!r} — 사람 승인이 기록되지 않았다",
        )

    # 6. 체크포인트 — Phase 2a 는 하나다.
    # 독립검증 통과는 4번(VALIDATION 파일)이, HITL#1 승인은 5번(generate_red_trigger)이
    # 이미 확인한다. v1 은 같은 사실을 CP-2.3·CP-2.4 파일로 한 번 더 요구했다.
    cp = task_dir(task_id) / "checkpoints" / "phase2a" / "CP-2.2_canonical-scenarios.md"
    result.check(
        "체크포인트 저장 (CP-2.2)",
        cp.is_file(),
        "" if cp.is_file() else f"누락: {cp.name}",
    )

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--task-id", required=True)
    parser.add_argument(
        "--skip-hitl",
        action="store_true",
        help="HITL 승인 조건을 건너뛴다 (승인 전 사전 점검용)",
    )
    args = parser.parse_args()

    if not is_valid_task_id(args.task_id):
        print(task_id_error(args.task_id), file=sys.stderr)
        return 2

    result = validate(args.task_id, args.skip_hitl)
    print(result.render(args.task_id))
    return 1 if result.failed else 0


if __name__ == "__main__":
    sys.exit(main())
