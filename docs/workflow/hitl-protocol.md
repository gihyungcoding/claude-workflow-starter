# HITL 프로토콜

워크플로우가 사람의 판단을 기다리는 4개 지점과, 그 승인/거절을 기록하는 방법이다.

> **원본에서 바뀐 점**
> 원본은 "승인/통과/LGTM/진행/OK"를 AI가 해석해 6개 상태로 매핑하는 **자연어 파싱 규칙**을
> 4곳에 중복해서 갖고 있었다(약 200줄). Claude Code에서는 `AskUserQuestion` 이 선택지를
> 구조화해 제시하므로 파싱 자체가 필요 없다. 규칙이 아니라 도구로 해결한다.

---

## 1. HITL 지점 4개

| # | Phase | 무엇을 검토하나 | 승인 기록 — **여기가 정본** |
|---|---|---|---|
| **1** | 2a | Canonical 시나리오 + 독립검증 결과 | `SCENARIO_<ID>.json` → `human_input.generate_red_trigger: true` |
| **2** | 2b | Red 테스트 코드 | `TEST_<ID>.json` → `human_review.approved: true` |
| **3** | 4 | 검증 리포트 | `VERIFY_<ID>.json` → `human_review.decision` |
| **4** | 5 | 회고 + 완료 리포트 | `REFLECT_<ID>.json` → `completion_report.approved_by_human: true` |

> v1 은 승인마다 별도 체크포인트(`CP-2.4`·`2.6`·`4.3`·`5.3`)를 하나씩 더 만들었다.
> 위 필드와 같은 사실을 두 번 적은 것이라 v2 에서 없앴다 (→ `checkpoint-template.md`).

**HITL 승인 없이 다음 Phase로 넘어갈 수 없다.** 각 Phase의 EXIT GATE가 이 필드를 확인한다.

---

## 2. 승인 요청 방법 — `AskUserQuestion`

HITL 지점에 도달하면 **먼저 검토 자료를 제시하고**, 그 다음 `AskUserQuestion` 으로 결정을 받는다.

### 2.1 검토 자료 제시

터미널에 요약을 출력한다. 사람이 스크롤 없이 판단할 수 있는 분량이어야 한다.

```
Phase 2a 완료 — TASK-001

시나리오 6건 (happy 3 / error 2 / boundary 1)
  SC-01  검색어가 매장명과 일치하면 해당 매장이 반환된다
  SC-02  ...

독립검증: PASS (6/6 시나리오가 Plan의 입출력과 대응)
  경고 1건: SC-04 의 Then 이 관찰 가능한 결과가 아님 ("내부적으로 캐시됨")

전문: workflow_design/05_scenario/SCENARIO_TASK-001.md
```

Phase 4·5처럼 자료가 길고 표·차트가 있으면 **Artifact로 발행**해 링크를 준다
(→ `wf-verify`, `wf-reflect` 스킬 참조).

### 2.2 결정 수집

```
AskUserQuestion({
  questions: [{
    header: "시나리오 승인",
    question: "Phase 2a 시나리오 6건을 승인하고 Red 코드 생성으로 넘어갈까요?",
    multiSelect: false,
    options: [
      { label: "승인",
        description: "시나리오를 확정하고 Phase 2b(Red 코드 생성)로 진행합니다." },
      { label: "시나리오 보완",
        description: "이 Phase에 머물며 시나리오를 수정합니다. 무엇을 고칠지 알려주세요." },
      { label: "설계로 롤백",
        description: "Phase 1 설계에 문제가 있습니다. Plan 단계로 되돌아갑니다." }
    ]
  }]
})
```

선택지는 **그 HITL에서 실제로 가능한 것만** 넣는다. 아래 표를 따른다.

---

## 3. decision 값과 허용 범위

| decision | 의미 | 허용 Phase | 다음 동작 |
|---|---|---|---|
| `APPROVE` | 승인 | 전부 | 다음 Phase로 |
| `REJECT` | 거절 → 재작업 | 2a, 2b, 4 | reject type 판정 (→ `reject-state-machine.md`) |
| `CLARIFY` | 질문 있음, 결정 보류 | **2a만** | 현 Phase 유지, 대화 계속 |
| `EXCEPTION_APPROVE` | 경고를 알고도 승인 | **4만, status=WARN일 때만** | 예외 항목 기록 후 다음 Phase로 |
| `REVISION_NEEDED` | 내용 보완 요청 | **5만** | 현 Phase 유지, 회고 보완 |

`EXCEPTION_APPROVE` 는 `VERIFY_<ID>.json` 의 `status` 가 `WARN` 일 때만 쓸 수 있다.
`FAIL` 상태에서는 예외 승인이 불가능하다 — 그건 Phase 3으로 되돌아가야 하는 상황이다.

---

## 4. 승인 기록

승인을 받으면 **두 곳을 갱신**한다.

1. **Phase 산출물 JSON** — 위 §1 표의 필드. 승인자의 코멘트가 있으면 같은 객체에 `note` 로
2. **그 Phase 의 체크포인트** — `next_steps` 를 다음 Phase 로 바꾸고, 승인 과정에서 정한 것이
   있으면 `decisions` 에 추가한다 (→ `checkpoint-template.md`)

```jsonc
// VERIFY_TASK-001.json
"human_review": {
  "decision": "APPROVE",
  "verified_commit": "a1b2c3d",
  "note": "SC-04 Then 을 관찰 가능한 형태로 고친 뒤 승인"
}
```

> **재승인을 요구하지 않는다.**
> 세션 복구 시 **단계 JSON 의 승인 필드**가 채워져 있으면 그 HITL 은 통과한 것이다.
> 사람을 같은 자료로 두 번 부르는 것은 워크플로우의 실패다.

---

## 5. 거절 처리

`REJECT` 를 받으면:

1. 사용자의 거절 사유를 그대로 받아 적는다 (요약·해석하지 않는다)
2. `reject-state-machine.md` 의 매핑표로 reject type 을 판정한다
3. Phase 산출물에 `reject` 객체를 기록한다

```jsonc
"reject": {
  "type": "RETRY_SCENARIO",
  "reason": "COVERAGE_INSUFFICIENT",
  "feedback": "권한이 없는 사용자가 접근했을 때 시나리오가 없습니다",
  "rejected_at": "2026-09-01T11:02:00Z",
  "attempt": 1
}
```

4. 재시도 횟수가 상한을 넘으면 상위 Phase로 롤백한다 (→ `reject-state-machine.md` §3)

---

## 6. 하지 말 것

- ❌ **자기 승인** — 에이전트가 `human_review.approved = true` 를 스스로 쓰는 것.
  이 필드는 `AskUserQuestion` 응답을 받은 뒤에만 쓴다.
- ❌ **승인 추정** — "사용자가 이전에 비슷한 걸 승인했으니 이번에도 승인일 것"
- ❌ **검토 자료 없는 승인 요청** — 무엇을 승인하는지 보여주지 않고 묻는 것
- ❌ **선택지 없는 자유 서술 요청** — "어떻게 할까요?" 대신 실행 가능한 선택지를 제시한다
