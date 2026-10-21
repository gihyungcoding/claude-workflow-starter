---
name: wf-scenario
description: >-
  Phase 2a — Given/When/Then 시나리오를 설계하고 독립검증자에게 검증받은 뒤 사람 승인(HITL#1)을
  받는다. Use when Phase 2a를 시작할 때, "시나리오 설계", "GWT 작성", "테스트 케이스 도출"
  요청을 받을 때, 또는 Phase 1 설계가 끝나 Red 코드 이전 단계로 넘어갈 때.
---

# Phase 2a — Scenario Design

Plan의 `flows` 를 **검증 가능한 Given/When/Then**으로 옮긴다. 이 시나리오가 Phase 2b의
테스트 코드가 되고, Phase 4 검증의 기준이 된다.

## MUST

1. 시나리오 **2건 이상** — happy 최소 1, error 최소 1
2. 모든 `acceptance_criteria` 를 시나리오가 덮는다
3. **입력을 받는 태스크면 입력 필드마다 타입별 경계값을 대본다**
   (→ `references/coverage-policy.md` §2-1). 길이 상한 +1, null 원소, 소수, 상한 +1 은
   Phase 4 가 찾을 일이 아니라 여기서 쓸 일이다
4. `SCENARIO_<ID>.md` 를 SoT로 쓴다. JSON은 MD에서 파생시킨다
5. **독립검증자 서브에이전트**를 호출한다 (`scenario-validator`)
6. 검증자 응답을 `VALIDATION_<ID>.json` 에 **가공 없이 그대로** 저장한다
7. HITL#1 승인을 `AskUserQuestion` 으로 받는다

## FORBIDDEN

1. ❌ **자기 검증** — 스스로 "검증 통과"라고 판정하고 넘어가기. 검증자는 별도 에이전트다
2. ❌ 검증자 응답에서 불리한 항목만 빼고 저장하기
3. ❌ Then에 **관찰할 수 없는 것**을 쓰기 (예: "내부적으로 캐시된다")
4. ❌ 승인 없이 Phase 2b 진입
5. ❌ 시나리오를 구현 방식으로 쓰기 (→ `references/gwt-canonical.md`)

## EXIT GATE

- `SCENARIO_<ID>.md` 와 `SCENARIO_<ID>.json` 존재
- `scenarios.length ≥ 2`, happy ≥ 1, error ≥ 1
- 모든 `acceptance_criteria` 가 최소 1개 시나리오에 매핑됨
- `validator/VALIDATION_<ID>.json` 의 `overall.pass == true`
- `human_input.generate_red_trigger == true`
- `CP-2.2` 저장 및 커밋 — 시나리오 작성·독립검증·HITL#1 승인마다 **같은 파일을 갱신**한다

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
  "coverage": {
    "acceptance_criteria_total": 3,
    "acceptance_criteria_covered": 3,
    "uncovered": []
  },
  "human_input": { "generate_red_trigger": false }
}
```

`coverage.uncovered` 가 비어 있지 않으면 **Step 2로 돌아간다.**

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

응답을 `workflow_design/05_scenario/validator/VALIDATION_<ID>.json` 에 **그대로** 저장한다.
요약·정리·불리한 항목 제거 금지.

- `overall.pass == false` → 지적된 항목을 고치고 Step 2부터 다시. 재검증은 최대 3회
- `overall.pass == true` 이고 **경고만** 있으면 **재검증하지 않는다.** 반영할 경고를 고치고
  HITL#1 요약에 무엇을 반영·보류했는지 적는다. 경고는 사람이 판단할 몫이다 — 경고를
  고칠 때마다 검증자를 다시 부르면 같은 시나리오를 세 번 검증하게 된다
- 3회를 넘으면 Phase 1 롤백을 사용자에게 제안한다 (→ `docs/workflow/reject-state-machine.md`)

**Phase 4 FAIL 로 들어왔다면** `VERIFY_<ID>.json` 의 `root_causes` 에서 `probe: reproduced`
변종과 `not_probed` 변종을 **전부** 이번에 시나리오로 가져온다(`not_probed` 는 Phase 3 의
테스트가 프로브한다). 증상 하나만 추가해 돌려보내면 같은 뿌리의 다음
변종 때문에 이 단계를 다시 거친다 (→ `wf-verify/references/root-cause-sweep.md`).

`CP-2.2` 를 갱신한다 — 검증 결과 원문은 `VALIDATION_<ID>.json` 에 있으므로 `summary` 한 줄과
반영하기로 한 경고만 `decisions` 에 적는다.

### Step 5 — HITL #1

검증까지 끝나면 사람에게 승인을 받는다 (→ `docs/workflow/hitl-protocol.md` §2).

먼저 요약을 출력한다:

```
Phase 2a — TASK-001

시나리오 6건 (happy 3 / error 2 / boundary 1)
  SC-01  담당 매장이 검색된다
  SC-02  담당하지 않는 매장은 403
  ...

커버리지  acceptance_criteria 3/3
독립검증  PASS
  경고 1건 — SC-04 의 Then "캐시에 저장된다"는 관찰 불가

전문: workflow_design/05_scenario/SCENARIO_TASK-001.md
```

그다음 `AskUserQuestion`:

- **승인** → Phase 2b로
- **시나리오 보완** → Step 2로 (무엇을 고칠지 받는다)
- **설계로 롤백** → Phase 1로

승인을 받으면:
1. `SCENARIO_<ID>.json` 의 `human_input.generate_red_trigger = true`
2. `CP-2.2` 갱신 — `next_steps` 를 Phase 2b 로 (승인 사실은 1번 필드가 정본이다)
3. `activeContext.md` 갱신
4. 커밋

```bash
python scripts/validate_phase2a_gate.py --task-id TASK-001
git add workflow_design/05_scenario memory-bank/TASK-001
git commit -m "chore(workflow): TASK-001 Phase 2a 시나리오 승인

Refs: TASK-001"
```
