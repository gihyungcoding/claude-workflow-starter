---
name: wf-orchestrator
description: >-
  개발 워크플로우 전체를 관장한다 — 어느 Phase에 있는지 판정하고, EXIT GATE를 확인하고,
  다음 단계로 전이시킨다. Use when 새 개발 태스크를 시작할 때, 중단한 태스크를 이어갈 때,
  "다음 단계로", "워크플로우 진행", "어느 단계인지" 같은 요청을 받을 때, Phase 전이 판단이
  필요할 때, 또는 거절(reject)이 발생해 어느 Phase로 되돌아갈지 정해야 할 때.
---

# 워크플로우 오케스트레이션

개발 태스크를 6단계로 완주시킨다. **이 스킬은 직접 작업하지 않는다** — 지금 어디에 있고
다음이 무엇인지 판정해 해당 Phase 스킬로 넘긴다.

## MUST

1. 어떤 Phase를 시작하기 전에 **선행 Phase의 EXIT GATE를 실제로 확인**한다 (파일을 읽어서)
2. 태스크 상태는 항상 `memory-bank/<TASK-ID>/activeContext.md` 에서 읽는다 — 기억에 의존하지 않는다
3. Phase를 넘길 때마다 체크포인트를 저장하고 **커밋**한다
4. HITL 승인은 `AskUserQuestion` 으로만 받는다 (→ `docs/workflow/hitl-protocol.md`)

## FORBIDDEN

1. ❌ Phase 건너뛰기 — 2a 없이 2b로, 4 없이 5로 가지 않는다
2. ❌ EXIT GATE 미충족 상태에서 "대체로 됐으니 진행" 판단
3. ❌ 사람 대신 승인 필드를 채우기
4. ❌ 산출물이 없는데 있다고 보고하기 — 파일 존재를 확인하고 말한다

---

## 두 계층

```
Foundation (프로젝트 수준)   product.md · architecture.md · ADR · features/*.md
        │ 태스크 생성                                        ▲
        ▼                                                    │ ADR 제안 (Phase 5)
Workflow (태스크마다)                                         │
                        ┌─ EXIT GATE 통과 필요                │
                        ▼                                    │
  [1] Plan ──► [2a] Scenario ──► [2b] Red ──► [3] Green ──► [4] Verify ──► [5] Reflect ──► DONE
       │            │  HITL#1        │ HITL#2                  │ HITL#3        │ HITL#4
    아키텍처·ADR 참조                                    제약 검증        Foundation 되먹임
       │            │                │                         │               │
       └────────────┴─ 거절 시 되돌아감 ─────────────────────────┴───────────────┘
                     (docs/workflow/reject-state-machine.md)
```

Foundation 은 이 스킬이 관장하지 않는다. `/wf-init`, `/wf-feature`, `/wf-adr` 이 담당하고
`docs/README.md` 가 전체 흐름을 설명한다.

| Phase | 스킬 | 한 문장 |
|---|---|---|
| 1 | `wf-plan` | 태스크를 TDD에 주입할 수 있는 구조 정보로 정규화한다 |
| 2a | `wf-scenario` | Given/When/Then 시나리오를 설계하고 독립검증을 받는다 |
| 2b | `wf-red` | 시나리오를 **실패하는** 테스트 코드로 옮긴다 |
| 3 | `wf-develop` | 테스트를 통과시키는 최소 구현을 하고 리팩토링한다 |
| 4 | `wf-verify` | 증거 기반으로 완료를 판정한다 |
| 5 | `wf-reflect` | 회고하고 태스크를 닫는다 |
| Ship | `/wf-ship` | 최종 검사 후 PR 을 만든다 (머지는 사람이) |

---

## 현재 위치 판정

태스크에 대한 작업 요청을 받으면 **먼저 이것부터** 한다.

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cat "$REPO_ROOT/memory-bank/<TASK-ID>/activeContext.md"
ls "$REPO_ROOT/memory-bank/<TASK-ID>/checkpoints/"*/
```

판정 규칙:

- `activeContext.md` 가 없다 → **신규 태스크**. `/wf-start` 절차로 간다
- 있다 → `phase` 와 실제 체크포인트 파일을 **둘 다** 본다
- 둘이 어긋나면 **체크포인트 파일 쪽을 믿는다** (파일이 있다는 것이 증거)
- `status: BLOCKED` 이면 진행하지 않는다 — `unblock_condition` 을 사용자에게 보여주고 멈춘다

---

## EXIT GATE

각 Phase는 아래를 **모두** 만족해야 다음으로 넘어간다. 판정은 파일을 읽어서 한다.

| Phase | 통과 조건 |
|---|---|
| **1 → 2a** | `PLAN_<ID>.json` 존재 · 파싱 성공 · `design.inputs`/`outputs`/`flows` 비어 있지 않음 · `route ∈ {Backend, Frontend, Database}` · `codebase_analysis` 존재 · `architecture_refs` 채워짐(아키텍처 문서가 있는 경우) · `CP-1.3` 저장 |
| **2a → 2b** | `SCENARIO_<ID>.md` + `.json` 존재 · `scenarios.length ≥ 2` (happy ≥1, error ≥1) · `VALIDATION_<ID>.json` 의 `overall.pass == true` · `human_input.generate_red_trigger == true` · `CP-2.2` 저장 |
| **2b → 3** | `TEST_<ID>.json` 존재 · `red_scenarios.length > 0` · 테스트 실행 결과가 **실제로 실패** · 테스트 함수 개수 == 승인된 시나리오 개수 · `human_review.approved == true` · `CP-2.5` 저장 |
| **3 → 4** | `DEV_<ID>.json` 존재 · `test_status == "green"` · `failed == 0` · `passed ≥ red_scenarios.length` · 린트 error 0 · `CP-3.4` 저장 |
| **4 → 5** | `VERIFY_<ID>.json` 존재 · `status ∈ {PASS, WARN}` (FAIL 불가) · **아키텍처 제약 error 0건** · `human_review.decision ∈ {APPROVE, EXCEPTION_APPROVE}` · `CP-4.2` 저장 |
| **5 → DONE** | `REFLECT_<ID>.json` 존재 · `keep ≥ 1` · `insights ≥ 1` · `approved_by_human == true` · `CP-5.2` 저장 · **모든 산출물 커밋됨** |
| **DONE → Ship** | `ship_preflight.py` exit 0 — 산출물·**신선도**·제약·작업트리·브랜치·병합가능 |

자동 검증:

```bash
python3 scripts/verify_workflow_artifacts.py --task-id TASK-001   # 전체 산출물
python3 scripts/validate_phase2a_gate.py --task-id TASK-001       # 2a 게이트
python3 scripts/check_architecture.py                             # 아키텍처 제약 (Phase 4)
python3 scripts/check_freshness.py --task-id TASK-001             # 승인한 코드 그대로인가
python3 scripts/ship_preflight.py --task-id TASK-001              # 머지 전 종합 (Ship)
```

---

## Foundation 확인

태스크 작업을 시작하기 전에 프로젝트 문서가 있는지 본다.

```bash
ls docs/product/product.md docs/architecture/architecture.md 2>/dev/null
```

없으면 **막지 않되 한 번 안내한다**:

```
docs/architecture/architecture.md 가 아직 없습니다.

Phase 1이 설계할 때 계층 배치의 기준으로 삼을 문서가 없다는 뜻입니다.
지금 진행해도 되지만, /wf-init 으로 한 번 만들어두면 이후 태스크마다
같은 판단을 반복하지 않아도 됩니다.

이대로 진행할까요?
```

같은 세션에서 두 번 이상 안내하지 않는다.

## 신규 태스크 시작

1. `workflow_design/02_tasks/tasks.json` 에서 해당 ID를 찾는다 (없으면 사용자에게 확인)
2. WRU 적격성을 확인한다 (→ `docs/workflow/task-schema.md` §1). 부적격이면 **진행 전에 알린다**
2-1. `source_refs.source_file` 이 있으면 그 요구사항 문서를 읽어둔다 — 태스크 설명보다
     맥락이 풍부하고, Phase 1이 §5 구현 참고를 쓴다
3. `memory-bank/<TASK-ID>/` 구조 생성:
   ```bash
   REPO_ROOT="$(git rev-parse --show-toplevel)"
   mkdir -p "$REPO_ROOT/memory-bank/<TASK-ID>/checkpoints"/{phase1,phase2a,phase2b,phase3,phase4,phase5}
   ```
4. `activeContext.md` · `progress.md` 작성 (→ `docs/workflow/memory-bank-spec.md`).
   **`track` 을 정해 기록한다** — 아래 「경량 경로」
5. 작업 브랜치 생성 — `feature/task-<번호>-<짧은-slug>`
6. 커밋 후 `wf-plan` 스킬로 넘긴다

---

## 경량 경로

**`meta.estimate.value ≤ 8` 이면 `track: light`**, 아니면 `standard`. 시작할 때 한 번 정하고
`activeContext.md` 에 적는다. 사용자가 바꾸자고 하면 따른다.

### 줄이지 않는 것

**검증은 하나도 줄이지 않는다.** 실사용에서 5~6시간짜리 태스크 셋이 모두 Phase 4 에서
결함이 잡혔다 — 4건, 3회 재시도, 1건. 작다고 안전하지 않다.

| 그대로 | 이유 |
|---|---|
| 6 Phase · HITL 4회 | 절대 규칙 1 |
| Phase 1 의 `design.*` · `target_files` | 2a 검증자(V4·V8·V11)가 이것을 읽는다 |
| 경계값 시나리오(coverage-policy §2-1) | 작은 태스크도 입력은 받는다 |
| Phase 4 전체 — 테스트·제약·코드 리뷰·화면 확인 | 결함을 잡는 단계다 |

### 줄이는 것 — 아무도 읽지 않는 비용만

| Phase | standard | light |
|---|---|---|
| 1 | 완료 보고에 flows·target_files·AC 매핑 표 | **unresolved 와 AC 매핑만** |
| 3 | 완료 보고 상세 | **테스트 수·린트·범위 이탈만** |
| 5 | Phase 1~5 완료 리포트를 **Artifact 로 발행** | **생략** — REFLECT JSON 과 HITL#4 요약으로 |
| 5 | KPT 각 2~3건 | **각 1건 이상** — 실제로 일어난 것만 |

light 에서 아낀 만큼 Phase 4 에 쓴다.

---

## 거절 처리

HITL에서 거절이 나오면 `docs/workflow/reject-state-machine.md` 를 읽고:

1. 거절 사유를 사유 코드로 판정 → reject type 결정
2. `reject.attempt` 를 증가시켜 산출물에 기록
3. 재시도 상한을 넘었으면 **같은 Phase에서 다시 시도하지 않고** 상위 Phase로 롤백
4. 되돌아간 Phase에서는 지목된 부분만 고친다 (처음부터 다시 하지 않는다)

---

## 진행 상황 보고

Phase를 마칠 때마다 사용자에게 이 형식으로 보고한다.

```
Phase 2a 완료 — TASK-001

  산출물   workflow_design/05_scenario/SCENARIO_TASK-001.md (시나리오 6건)
  검증     PASS (경고 1건)
  체크포인트 CP-2.2
  게이트   통과 — 2b 진입 가능

다음: Red 테스트 코드 생성
```

Phase 5를 마치면 `/wf-ship` 을 안내한다 — 태스크가 DONE 이어도 머지되지 않으면
릴리스에 포함되지 않는다.

파일이 실제로 있는지 확인하고 쓴다. 만들었다고 생각하는 것과 만들어진 것은 다르다.
