# Reject 처리와 상태 전이

HITL에서 거절이 나왔을 때 어느 Phase로 되돌아가고, 몇 번까지 재시도하는지를 정의한다.

> **원본에서 바뀐 점**
> 이 내용은 원본에서 마스터 문서와 `1003a`, `1003b` 3곳에 중복되어 있었다. 여기서는 이 파일이
> 정본이고, Phase 스킬은 거절이 발생했을 때만 이 문서를 읽는다 (정상 경로에서는 읽지 않는다).

---

## 1. 상태 전이

```
START
  │
  ▼
Phase 1 (Plan) ◄─────────────────────── ROLLBACK_PLAN
  │
  ▼
Phase 2a (Scenario) ◄──── RETRY_SCENARIO
  │
  ├─ HITL #1 ─ REJECT ─┘
  ▼
Phase 2b (Red) ◄──── RETRY_RED_CODE
  │
  ├─ HITL #2 ─ REJECT ─┘   (또는 RETRY_SCENARIO → 2a로)
  ▼
Phase 3 (Green)
  │
  ▼
Phase 4 (Verify)
  │
  ├─ HITL #3 ─ REJECT ─► Phase 3 (구현 결함) 또는 Phase 2a (시나리오 결함)
  ▼
Phase 5 (Reflect)
  │
  ├─ HITL #4 ─ REVISION_NEEDED ─┘  (현 Phase 유지)
  ▼
DONE
```

`BLOCKED` 는 어느 Phase에서도 발생할 수 있으며 상태 전이가 아니라 **정지**다.

---

## 2. Reject Type

| Type | 무엇이 잘못됐나 | 되돌아갈 곳 |
|---|---|---|
| `RETRY_SCENARIO` | 시나리오가 불완전·부정확 | Phase 2a |
| `RETRY_RED_CODE` | 시나리오는 맞는데 테스트 코드가 틀림 | Phase 2b 내부 루프 |
| `ROLLBACK_PLAN` | 설계 자체가 문제 | Phase 1 |
| `ROLLBACK_TASK` | 태스크 정의·요구사항이 불명확 | 워크플로우 밖 (사람이 태스크를 다시 씀) |
| `BLOCKED` | 외부 의존성 때문에 진행 불가 | 정지 (HOLD) |

### 거절 사유 → Type 매핑

사용자의 거절 사유를 아래 사유 코드 중 하나로 판정한 뒤 Type을 결정한다.
**어디에도 맞지 않으면 추측하지 말고 사용자에게 되묻는다.**

```
SCENARIO_INCOMPLETE      시나리오가 빠졌다              → RETRY_SCENARIO
COVERAGE_INSUFFICIENT    커버리지가 부족하다             → RETRY_SCENARIO
SCENARIO_WRONG_TYPE      happy/error 분류가 틀렸다       → RETRY_SCENARIO
RULE_CONFLICT            프로젝트 규칙과 충돌한다         → RETRY_SCENARIO

CODE_SCENARIO_MISMATCH   코드가 시나리오와 다르다         → RETRY_RED_CODE
WRONG_ASSERTION          단언이 틀렸다                  → RETRY_RED_CODE

TECH_INFEASIBLE          기술적으로 불가능한 설계다       → ROLLBACK_PLAN
DESIGN_MISMATCH          설계가 요구사항과 다르다         → ROLLBACK_PLAN

TASK_UNCLEAR             태스크 정의가 모호하다           → ROLLBACK_TASK
TASK_GAP_FOUND           요구사항에 빠진 부분이 있다       → ROLLBACK_TASK

DEPENDENCY_NOT_READY     선행 태스크·외부 API 미준비      → BLOCKED
```

---

## 3. 재시도 상한

```jsonc
{
  "RETRY_SCENARIO":  { "max_attempts": 3, "on_exceed": "ROLLBACK_PLAN" },
  "RETRY_RED_CODE":  { "max_attempts": 2, "on_exceed": "RETRY_SCENARIO" },
  "ROLLBACK_PLAN":   { "max_attempts": 2, "on_exceed": "ESCALATE" },
  "ESCALATE":        { "action": "사용자에게 사람의 개입이 필요하다고 알리고 정지" }
}
```

재시도 횟수는 Phase 산출물의 `reject.attempt` 에 누적 기록한다.
**상한을 넘으면 같은 Phase에서 다시 시도하지 않는다** — 3번 실패한 시나리오를 4번째로
고쳐 쓰는 것보다 설계를 다시 보는 편이 빠르다는 판단이다.

상한 초과로 상위 Phase에 진입할 때는 `reject.escalated_from` 에 원래 Type을 남긴다.

---

## 4. BLOCKED 처리

`BLOCKED` 는 워크플로우가 해결할 수 없는 사유다. 재시도하지 않는다.

1. `activeContext.md` 의 `status` 를 `BLOCKED` 로 바꾼다
2. `blocked_reason` 과 `blocked_since` (날짜)를 기록한다
3. **무엇이 풀려야 재개할 수 있는지**를 한 문장으로 적는다
4. 체크포인트를 저장하고 정지한다

```yaml
status: BLOCKED
blocked_reason: "검색 API의 응답 스키마가 확정되지 않음 (백엔드 TASK-014 선행)"
blocked_since: 2026-09-01
unblock_condition: "TASK-014 완료 후 DEV_TASK-014.json 의 응답 스키마 확인"
```

해제는 **사람이 명시적으로 지시할 때만** 한다. 에이전트가 "이제 됐을 것 같다"고 스스로
재개하지 않는다.

> `memory-bank/index.md` 는 BLOCKED 태스크를 활성 목록에 계속 표시한다. 원본 저장소에서
> 2~3개월 정체된 태스크가 6건 있었는데, 정체 자체보다 **정체가 보이지 않는 것**이 문제였다.

---

## 5. 거절 후 재시도할 때

되돌아간 Phase에서 **처음부터 다시 하지 않는다.** 거절 사유가 지목한 부분만 고친다.

- 되돌아간 Phase 의 체크포인트를 **덮어쓰고** `attempts` 에 한 줄을 추가한다 —
  무엇 때문에 왔고(`outcome`) 어디로 왔는지(`back_to`)
- `decisions` 에 **이번 시도에서 무엇을 바꿨는지** 추가한다
- 새 파일을 만들지 않는다. 이전 시도의 원문은 git 이력에 있다
  (→ `checkpoint-template.md` §5)

이 이력이 Phase 5 회고의 입력이 된다. 거절이 반복된 지점은 대개 규칙이나 태스크 정의에
문제가 있다는 신호다.

### Phase 4 FAIL 로 돌아올 때는 뿌리 단위로

증상 하나를 고치려고 돌아가지 않는다. 되돌아갈 때마다 독립검증 · HITL · Red · Green · 리뷰를
다시 도는데, 증상 하나만 고치면 같은 뿌리의 다음 변종 때문에 또 돌아온다.

`VERIFY_<ID>.json` 의 `root_causes` 에서 **`probe: reproduced` 변종 전부를 이번 왕복에서
처리한다.** Phase 3 은 뿌리를 고치고 변종마다 테스트를 먼저 실패시키며, 시나리오가 필요하면
Phase 2a 에서 변종 전부를 한 번에 가져간다. 재검증에서 같은 뿌리의 변종이 또 나오면 새 뿌리를
만들지 않고 `origin: "later"` 로 덧붙인다 — 회고가 스윕이 놓친 것을 세는 근거다.
`not_probed` 로 넘긴 변종은 다음 라운드에 반드시 프로브하고, 같은 뿌리의 변종이 둘 이상이면
위치마다가 아니라 공통 지점에서 고친다.
(→ `.claude/skills/wf-verify/references/root-cause-sweep.md`)
