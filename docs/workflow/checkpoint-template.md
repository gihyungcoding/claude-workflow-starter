# 체크포인트 (v2)

세션이 끊겨도 작업을 이어갈 수 있게 하는 **커서**다. 기록물이 아니다.

> **v1 에서 바뀐 점**
> v1 은 19종(필수 12)을 두고, 프론트매터 12개 필드와 본문 3절을 쓰게 했으며, 재시도마다
> `_retry` 파일을 새로 만들었다. 실사용 8개 태스크에서 체크포인트가 **전체 산출물의 54%**
> (171개 · 10,368줄)였다. 그런데 체크포인트를 실제로 읽는 곳은 셋뿐이었고, 그 셋이 읽는
> 내용은 약 20%였다. 나머지는 단계 JSON 을 산문으로 다시 쓰거나, 파일 경로에서 유도되는
> 메타였다. HITL 승인 CP 4종(40개 · 2,417줄)은 단계 JSON 의 `human_review` 와 같은 사실을
> 두 번 적고 있었다.

---

## 1. 누가 읽는가 — 이 셋에 필요한 것만 쓴다

| 읽는 곳 | 무엇을 | 왜 |
|---|---|---|
| `/wf-resume` · SessionStart 훅 | **마지막** CP 의 `summary` · `next_steps` | 어디서 다시 시작하나 |
| `wf-reflect` Step 1 | **모든** CP 의 `decisions` · `attempts` | 무엇을 왜 정했나, 어디서 되돌아갔나 |
| EXIT GATE 스크립트 | 파일 존재 여부 | Phase 를 거쳤나 |

여기 없는 것은 쓰지 않는다. 특히:

| 쓰지 않는 것 | 이미 있는 곳 |
|---|---|
| 완료한 작업 목록 | git log · 단계 JSON |
| 작업 내용 산문 요약 | 단계 JSON (`status_reason` 등) |
| checkpoint_id · task_id · phase | **파일 경로** — `memory-bank/TASK-001/checkpoints/phase4/CP-4.2_…` |
| 테스트·빌드 명령, 환경 변수 | `CLAUDE.md` |
| HITL 승인 사실 | 단계 JSON 의 `human_review` (→ `hitl-protocol.md`) |

---

## 2. Phase 당 하나

| Phase | 파일 |
|---|---|
| 1 | `phase1/CP-1.3_context-plan.md` |
| 2a | `phase2a/CP-2.2_canonical-scenarios.md` |
| 2b | `phase2b/CP-2.5_red-code.md` |
| 3 | `phase3/CP-3.4_context-dev.md` |
| 4 | `phase4/CP-4.2_verification.md` |
| 5 | `phase5/CP-5.2_context-reflect.md` |

**Phase 를 진행하면서 같은 파일을 덮어쓴다.** 저장할 때마다 커밋하므로 이전 내용은 git 에
남는다. 시나리오를 쓴 뒤, 독립검증을 받은 뒤, HITL#1 승인을 받은 뒤 — 모두 같은
`CP-2.2` 를 갱신한다.

> 파일명에 번호(1.3, 2.2 …)가 남아 있는 것은 v1 과의 호환 때문이다. 이미 만들어진
> 프로젝트의 체크포인트가 그대로 유효하도록 이름을 바꾸지 않았다.

---

## 3. 형식

```yaml
---
status: ACTIVE                       # ACTIVE | ARCHIVED
saved_at: 2026-10-13T10:30:00Z
summary: "시나리오 6건 작성, 독립검증 통과(경고 2 반영). HITL#1 대기"

next_steps:
  - "HITL#1 — 시나리오 6건 승인 받기"
  - "승인되면 SCENARIO_TASK-001.json 의 generate_red_trigger 를 true 로"

decisions:                           # 없으면 [] 를 명시한다
  - decision: "페이지 경계 시나리오를 1건으로 통합"
    rationale: "첫/마지막 페이지가 같은 코드 경로를 탄다"

attempts:                            # 되돌아온 적이 있을 때만
  - n: 1
    outcome: "Phase 4 FAIL — 좌석 상한 우회, 대량 생성 DoS"
    back_to: "2a"
---
```

**본문은 쓰지 않는다.** 위 다섯 필드가 전부다.

| 필드 | 쓰는 곳 | 한 줄 규칙 |
|---|---|---|
| `summary` | 재개 | 한 문장. 지금 어디까지 왔나 |
| `next_steps` | 재개 | 우선순위 순. 재개하면 첫 줄부터 한다 |
| `decisions` | 회고 | **무엇을 정했고 왜**. 대안을 버린 이유가 있으면 한 줄 덧붙인다 |
| `attempts` | 회고 | 거절·FAIL 로 되돌아온 이력. 원인 한 줄과 어디로 갔는지 |

**30줄을 넘으면** 커서가 아니라 사본을 만들고 있는 것이다. 단계 JSON 을 다시 서술하고
있지 않은지 본다.

---

## 4. 저장 절차

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
CP="$REPO_ROOT/memory-bank/$TASK_ID/checkpoints/phase2a/CP-2.2_canonical-scenarios.md"
mkdir -p "$(dirname "$CP")"
# Write 도구로 CP 를 쓴다 (있으면 덮어쓴다)
git add "$REPO_ROOT/memory-bank/$TASK_ID"
git commit -m "chore(memory-bank): $TASK_ID Phase 2a 체크포인트"
```

저장하면 `activeContext.md` 의 `phase` · `last_checkpoint` 도 함께 갱신한다
(→ `memory-bank-spec.md`). 둘이 어긋나면 복구 시 어느 쪽을 믿을지 알 수 없다.

---

## 5. 되돌아왔을 때

거절이나 FAIL 로 이전 Phase 에 돌아오면, **돌아온 Phase 의 CP 를 덮어쓰고 `attempts` 에
한 줄을 추가한다.** 새 파일을 만들지 않는다.

```yaml
attempts:
  - n: 1
    outcome: "Phase 4 FAIL — title 200자 초과 시 500, sections 의 null 원소"
    back_to: "2a"
  - n: 2
    outcome: "HITL#1 거절 — 동시 위반 시 우선순위 시나리오 누락"
    back_to: "2a"
```

`decisions` 에는 이번 시도에서 **무엇을 바꿨는지**를 추가한다. 이전 시도의 CP 원문이
필요하면 git 이력에 있다:

```bash
git log -p -- memory-bank/TASK-001/checkpoints/phase2a/CP-2.2_canonical-scenarios.md
```

회고(Phase 5)는 모든 CP 의 `attempts` 를 모아 **어디서 몇 번, 왜 되돌아갔는지**를 본다.
거절이 반복된 지점은 대개 규칙이나 태스크 정의에 문제가 있다는 신호다.

---

## 6. status

| 값 | 언제 |
|---|---|
| `ACTIVE` | 진행 중인 태스크의 CP |
| `ARCHIVED` | 태스크 종료 후 (Phase 5 Step 7) |

v1 의 `SUPERSEDED` 는 쓰지 않는다 — 덮어쓰기 이전 상태는 git 이력이 대신한다.

---

## 7. v1 체크포인트가 있는 프로젝트

이미 만들어진 v1 파일(`CP-2.3_validator-passed.md`, `…_retry1.md` 등)은 **그대로 둔다.**
경로 검사가 계속 허용하고, 게이트는 Phase 당 1개만 요구하므로 기존 태스크도 통과한다.
새 태스크부터 v2 로 쓴다. 옮겨 적거나 지울 필요는 없다.
