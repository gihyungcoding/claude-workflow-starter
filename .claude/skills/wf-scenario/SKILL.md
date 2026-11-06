---
name: wf-scenario
description: >-
  Phase 2a — Given/When/Then 시나리오를 설계하고 독립검증자에게 검증받는다. 사람 승인(HITL#1)은
  Red 테스트와 함께 Phase 2b 끝에서 받는다. Use when Phase 2a를 시작할 때, "시나리오 설계", "GWT 작성", "테스트 케이스 도출"
  요청을 받을 때, 또는 Phase 1 설계가 끝나 Red 코드 이전 단계로 넘어갈 때.
---

# Phase 2a — Scenario Design

Plan의 `flows` 를 **검증 가능한 Given/When/Then**으로 옮긴다. 이 시나리오가 Phase 2b의
테스트 코드가 되고, Phase 4 검증의 기준이 된다.

## MUST

1. 시나리오 **2건 이상** — happy 최소 1, error 최소 1
2. 모든 `acceptance_criteria` 를 시나리오가 덮는다
3. **PLAN 이 정한 입력 경계 칸을 전부 판정한다** — `coverage_matrix.py` 가 PLAN 의
   `design.input_fields` 에서 칸을 펼친다. 칸마다 `covered`(SC-ID) 또는 `n/a`(사유). 길이 상한 +1,
   null 원소, 소수는 Phase 4 가 찾을 일이 아니라 여기서 쓸 일이다 (→ `references/coverage-policy.md` §2-1)
4. `SCENARIO_<ID>.md` 를 SoT로 쓴다. JSON은 MD에서 파생시킨다
5. **독립검증자 서브에이전트**를 호출한다 (`scenario-validator`)
6. 검증자 응답을 `VALIDATION_<ID>.json` 에 **가공 없이 그대로** 저장한다
7. 독립검증을 통과하면 **사람을 부르지 않고** Phase 2b 로 넘어간다. 시나리오 승인(HITL#1)은
   Red 테스트 승인(HITL#2)과 합쳐 2b 끝에서 한 번 받는다 (→ `wf-red` Step 6)

## FORBIDDEN

1. ❌ **자기 검증** — 스스로 "검증 통과"라고 판정하고 넘어가기. 검증자는 별도 에이전트다
2. ❌ 검증자 응답에서 불리한 항목만 빼고 저장하기
3. ❌ Then에 **관찰할 수 없는 것**을 쓰기 (예: "내부적으로 캐시된다")
4. ❌ 독립검증 통과 없이 Phase 2b 진입
5. ❌ 시나리오를 구현 방식으로 쓰기 (→ `references/gwt-canonical.md`)

## EXIT GATE

- `SCENARIO_<ID>.md` 와 `SCENARIO_<ID>.json` 존재
- `scenarios.length ≥ 2`, happy ≥ 1, error ≥ 1
- 모든 `acceptance_criteria` 가 최소 1개 시나리오에 매핑됨
- **`coverage_matrix.py` exit 0** — 입력 경계 칸이 빠짐없이 판정됨
- `validator/VALIDATION_<ID>.json` 의 `overall.pass == true`
- `CP-2.2` 저장 및 커밋 — 시나리오 작성·독립검증마다 **같은 파일을 갱신**한다
- `human_input.generate_red_trigger` 는 `false` 로 둔다 — 2b 끝의 통합 승인에서 채운다

```bash
python scripts/validate_phase2a_gate.py --task-id TASK-001    # exit 0 이어야 함
```

---

## 절차

### Step 1 — 입력 로드

```bash
cat workflow_design/04_plan/PLAN_TASK-001.json
```

`design.flows` 와 `acceptance_criteria` 가 시나리오의 재료다. 태스크 원문을 다시 읽을
필요는 없다 — Phase 1이 이미 정규화했다.

새로 쓰는지 기존 것을 확장하는지는 `CP-2.2` 의 `decisions` 에 남긴다.

### Step 2 — 시나리오 작성

작성 규칙은 `references/gwt-canonical.md`, 개수 판단은 `references/coverage-policy.md` 를 읽는다.

`workflow_design/05_scenario/SCENARIO_<ID>.md` 에 쓴다.

```markdown
# TASK-001 시나리오

## SC-01 (happy) 담당 매장이 검색된다

- **Given** 슈퍼바이저 S가 매장 A, B를 담당한다
- **And** 매장 A의 이름은 "강남점"이다
- **When** S가 "강남"으로 검색한다
- **Then** 결과에 매장 A가 포함된다
- **And** 결과 개수는 1이다

covers: 담당하지 않는 매장은 검색 결과에 나오지 않는다
flow: F1

## SC-02 (error) 담당하지 않는 매장은 403

- **Given** 슈퍼바이저 S가 매장 A만 담당한다
- **When** S가 매장 C를 직접 조회한다
- **Then** 403이 반환된다
- **And** 응답 본문에 매장 C의 정보가 없다

covers: 권한 없는 직접 조회는 403을 반환한다
flow: F2
```

각 시나리오에 `covers`(어느 acceptance_criteria) 와 `flow`(어느 Plan flow) 를 반드시 단다.
이 매핑이 없으면 검증자가 대응 관계를 확인할 수 없다.

`CP-2.2_canonical-scenarios.md` 저장.

**PLAN 의 입력 제약도 한 항목씩 대조한다.** `design.inputs[].constraints` 의 각 항목이 어느
시나리오의 Then 에서 단언되는지 찾는다. 단언하는 시나리오가 없는 제약은 시나리오를 추가하거나,
「Phase 4 수동 증거」로 확인한다고 `CP-2.2` 의 `decisions` 에 적는다. 시나리오에 없는 제약은
테스트도 없어서, 구현에서 지워도 아무것도 실패하지 않는다 (→ TASK-013 변이 M15 생존 —
주소 정리 제약).


### Step 3 — JSON 파생

MD를 읽어 `SCENARIO_<ID>.json` 을 만든다. **MD가 SoT다** — JSON을 고치고 MD를 두면 안 된다.

```jsonc
{
  "task_id": "TASK-001",
  "scenarios": [
    { "id": "SC-01", "type": "happy", "title": "담당 매장이 검색된다",
      "given": ["슈퍼바이저 S가 매장 A, B를 담당한다", "매장 A의 이름은 \"강남점\"이다"],
      "when": ["S가 \"강남\"으로 검색한다"],
      "then": ["결과에 매장 A가 포함된다", "결과 개수는 1이다"],
      "covers": ["담당하지 않는 매장은 검색 결과에 나오지 않는다"],
      "flow": "F1" }
  ],
  "coverage_matrix": [
    { "cell": "keyword@F1:string.max+1", "state": "covered", "by": ["SC-03"] },
    { "cell": "keyword@F1:string_stored.nul", "state": "n/a", "reason": "저장하지 않고 LIKE 비교만 — PLAN constraints" }
  ],
  "coverage": {
    "acceptance_criteria_total": 3,
    "acceptance_criteria_covered": 3,
    "uncovered": []
  },
  "human_input": { "generate_red_trigger": false }
}
```

`coverage.uncovered` 가 비어 있지 않으면 **Step 2로 돌아간다.**

**MD 를 고친 뒤에는 JSON 을 통째로 다시 만든다** — 롤백·경고 반영·검증 FAIL 수정 모두.
바뀐 시나리오만 JSON 에 덧대면 규약 표·`notes` 같은 다른 칸이 옛 MD 를 가리킨 채 남고,
검증자가 MD 와 JSON 의 불일치로 FAIL 을 낸다 (→ TASK-017 롤백 검증 1회차 V1).

### Step 3.5 — 입력 경계 행렬을 채운다

**검증자를 부르기 전에** 기계가 셀 수 있는 누락을 없앤다. 빠진 칸은 검증자 회차를 쓸 일이 아니다.

```bash
python3 scripts/coverage_matrix.py --task-id TASK-001 --skeleton   # 아직 판정 안 된 칸의 초안
python3 scripts/coverage_matrix.py --task-id TASK-001              # exit 0 이 될 때까지
```

- 칸마다 시나리오를 쓰거나 기존 시나리오 표에 행을 더해 `covered` 로 닫는다. 같은 검사는 시나리오
  하나의 표로 묶는다 (→ `coverage-policy.md` 「개수를 불리지 않는 법」)
- 해당하지 않는 칸은 `n/a` 와 **PLAN 에 근거한 사유**로 닫는다 (예: 「PLAN constraints — 서버 400 에
  맡긴다」). 근거 없는 `n/a` 는 검증자가 FAIL 로 돌려보낸다
- **칸이 없어서 못 덮는 경계를 발견하면** — 필드나 종류가 PLAN 에서 빠진 것이다. `input_fields` 를
  고치고 `check_plan.py` 를 다시 돌린다. 분류 보완은 설계 변경이 아니므로 `ROLLBACK_PLAN` 으로 세지
  않되, `CP-2.2` 의 `decisions` 에 무엇을 더했는지 적는다

### Step 4 — 독립검증

`scenario-validator` 서브에이전트를 호출한다. 이 에이전트는 `Read`/`Grep`/`Glob` 만 갖고 있어
파일을 고칠 수 없다 — 검증자가 시나리오를 "고쳐서 통과시키는" 일이 구조적으로 불가능하다.

```
Agent({
  subagent_type: "scenario-validator",
  description: "TASK-001 시나리오 독립검증",
  run_in_background: false,
  prompt: `
TASK-001 의 시나리오를 검증해주세요.

읽을 파일:
- workflow_design/04_plan/PLAN_TASK-001.json
- workflow_design/05_scenario/SCENARIO_TASK-001.md
- workflow_design/05_scenario/SCENARIO_TASK-001.json

지정된 JSON 형식으로만 응답하세요.
`
})
```

**검증자에게 "통과시켜달라"거나 "이 부분은 괜찮다"는 유도를 넣지 않는다.** 파일 경로와
태스크 ID만 준다.

**2회차부터는 이전 판정을 원문 그대로 붙인다.** 검증자는 매번 새로 시작하므로 이전 회차를 모르면
처음부터 다시 찾고, 그때마다 새 지적이 나온다. 이전 판정이 있으면 검증자는 「지적한 것이 고쳐졌나 ·
고치다 새로 깨진 것이 있나」를 판정하고, 처음 보는 지적은 경고로 낸다 (→ 검증자 「회차 규칙」).

```bash
git show HEAD:workflow_design/05_scenario/validator/VALIDATION_TASK-001.json   # 직전 회차 원문
```

```
이전 회차 판정 (원문, 2회차):
<위 출력 그대로>
이번 회차에 고친 시나리오: SC-03, SC-07 (추가: SC-11)
```

응답을 `workflow_design/05_scenario/validator/VALIDATION_<ID>.json` 에 **그대로** 저장한다.
요약·정리·불리한 항목 제거 금지.

- `overall.pass == false` → 지적된 항목을 고치고 Step 2부터 다시. 재검증은 최대 3회.
  **V11 fail 은 셋 중 하나다** — 지적의 `kind` 를 보고 고친다.
  - `false_cover` — `covered` 라고 적었는데 시나리오가 그 값을 쓰지 않는다 → 시나리오를 고친다.
    **같은 시나리오를 근거로 든 다른 칸도 전부** 다시 본다
  - `bad_na` — `n/a` 사유가 PLAN 과 맞지 않는다 → 시나리오를 쓰거나 근거를 고친다
  - `plan_gap` — PLAN `input_fields` 에 필드·종류가 빠졌다 → Step 3.5 마지막 항목대로 PLAN 을
    고치고, 새로 생긴 칸을 **모두** 채운 뒤 재검증한다
- `overall.pass == true` 이고 **경고만** 있으면 **재검증하지 않는다.** 반영할 경고를 고치고
  통합 HITL(2b 끝) 요약에 무엇을 반영·보류했는지 적는다. 경고는 사람이 판단할 몫이다 — 경고를
  고칠 때마다 검증자를 다시 부르면 같은 시나리오를 세 번 검증하게 된다
- 3회를 넘으면 Phase 1 롤백을 사용자에게 제안한다 (→ `docs/workflow/reject-state-machine.md`)

**Phase 4 FAIL 로 들어왔다면** `VERIFY_<ID>.json` 의 `root_causes` 에서 `probe: reproduced`
변종과 `not_probed` 변종을 **전부** 이번에 시나리오로 가져온다(`not_probed` 는 Phase 3 의
테스트가 프로브한다). 증상 하나만 추가해 돌려보내면 같은 뿌리의 다음
변종 때문에 이 단계를 다시 거친다 (→ `wf-verify/references/root-cause-sweep.md`).

`CP-2.2` 를 갱신한다 — 검증 결과 원문은 `VALIDATION_<ID>.json` 에 있으므로 `summary` 한 줄과
반영하기로 한 경고만 `decisions` 에 적는다.

### Step 5 — Phase 2b 로 넘기기

**여기서 사람을 부르지 않는다.** 시나리오만 보고 승인하던 HITL#1 은 Red 테스트와 합쳐졌다.
14개 태스크에서 HITL#2 는 한 번도 거절되지 않았고, 두 승인 사이 대기만 태스크당 15~30분이었다.
사람은 2b 끝에서 시나리오와 그것을 옮긴 테스트를 나란히 보고 한 번에 판단한다.

그 대신 **사람에게 보일 것을 지금 정리해 둔다.** 통합 HITL 요약이 그대로 가져다 쓴다.

- 반영한 경고와 보류한 경고 — `CP-2.2` 의 `decisions`
- 검증자 회차 수와 회차마다 무엇이 FAIL 이었는지 — `CP-2.2` 의 `attempts`

```bash
python scripts/validate_phase2a_gate.py --task-id TASK-001     # exit 0 — HITL 조건은 아직 안 본다
git add workflow_design/05_scenario memory-bank/TASK-001
git commit -m "chore(workflow): TASK-001 Phase 2a 시나리오 독립검증 통과

Refs: TASK-001"
```

`CP-2.2` 의 `next_steps` 를 Phase 2b 로 바꾸고 `activeContext.md` 를 갱신한 뒤 `wf-red` 로 간다.

**시나리오에 사람이 정해야 할 질문이 있으면** 넘어가기 전에 묻는다. 예: 정책이 두 가지로 읽히는데
Plan 이 정하지 않았다. 이것은 승인이 아니라 질문이므로 `AskUserQuestion` 으로 묻고 답을
`decisions` 에 적는다. 승인 필드는 쓰지 않는다. 답에 따라 테스트가 달라지는 질문을 2b 끝까지
미루면 Red 작업을 버리게 된다.
