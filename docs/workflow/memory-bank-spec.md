# Memory Bank 규격

세션이 끊겨도 작업을 이어가기 위한 상태 저장소다. 경로 규약은 `artifact-paths.md` §3에 있고,
이 문서는 **파일 내용의 형식**과 **복구 절차**를 정의한다.

> **원본에서 바뀐 점**
> `activeContext.md` 업데이트 템플릿이 원본에서는 6개 규칙 파일에 중복되어 있었다.
> 또 세션 복구는 사람이 매번 "task-0310 복구해줘"라고 지시해야 시작됐다. 여기서는
> **SessionStart 훅**(`scripts/hooks/session_start.py`)이 세션 시작 시 활성 태스크를 자동으로
> 주입하므로, 복구는 지시가 아니라 기본 동작이다.

---

## 1. `activeContext.md`

태스크의 **현재 상태 레코드**다. 한 태스크에 하나만 있다.

```markdown
---
task_id: TASK-001
title: "매장 검색 API에 권한 필터 추가"
phase: "2a"
phase_name: "Phase 2a - Scenario Design"
status: ACTIVE                  # ACTIVE | BLOCKED | DONE
created_at: 2026-09-01
last_updated: 2026-09-01

primary_category: Backend       # Backend | Frontend | Database
sub_categories: []
target_repo: "."
branch: "feature/task-001-store-search-permission"

last_checkpoint: CP-2.2
artifacts:
  plan: "workflow_design/04_plan/PLAN_TASK-001.json"
  scenario: "workflow_design/05_scenario/SCENARIO_TASK-001.md"
---

## 지금 무엇을 하고 있나

시나리오 6건을 작성했고 독립검증자 호출을 준비 중이다.

## 다음 한 걸음

`scenario-validator` 서브에이전트에 SCENARIO_TASK-001.md 와 PLAN_TASK-001.json 을 넘겨
검증 결과를 받는다.

## 알아둬야 할 것

- 권한 체크는 기존 `require_role` 데코레이터를 재사용한다 (CP-1.3 결정)
- 페이지네이션 경계 시나리오는 1건으로 통합했다 (CP-2.2 결정)
```

### 갱신 시점

`activeContext.md` 는 **체크포인트를 저장할 때마다 함께 갱신**한다. 최소한 다음 3개는 반드시:

- `phase` / `phase_name`
- `last_checkpoint`
- `last_updated`

> 체크포인트만 저장하고 `activeContext.md` 를 그대로 두면, 복구 시 "어느 쪽이 최신인가"를
> 판단할 수 없다. 두 파일이 어긋나면 **체크포인트 디렉터리의 가장 마지막 CP를 정답으로 본다**
> (파일이 실제로 있는 쪽이 증거이므로).

### `status: BLOCKED` 일 때

`reject-state-machine.md` §4의 3개 필드를 추가한다: `blocked_reason`, `blocked_since`,
`unblock_condition`.

---

## 2. `progress.md`

Phase 진행 상황을 한눈에 보는 표다. 태스크당 하나.

```markdown
# TASK-001 진행

| Phase | 상태 | 체크포인트 | 비고 |
|---|---|---|---|
| 1 Plan | ✅ 완료 | CP-1.3 | 설계 라우팅: Backend |
| 2a Scenario | 🔄 진행 중 | CP-2.2 | 시나리오 6건, 검증 대기 |
| 2b Red | ⬜ 대기 | — | |
| 3 Green | ⬜ 대기 | — | |
| 4 Verify | ⬜ 대기 | — | |
| 5 Reflect | ⬜ 대기 | — | |

## 완료 조건

- [ ] 권한 없는 사용자가 타 매장을 조회하면 403
- [ ] 기존 매장 조회 동작이 깨지지 않음 (회귀 테스트 통과)
- [ ] 검색 응답 시간이 기존 대비 20% 이내 증가
```

상태 기호: `⬜ 대기` / `🔄 진행 중` / `✅ 완료` / `⛔ 차단` / `↩️ 재시도`

---

## 3. `index.md` — 손으로 쓰지 않는다

`memory-bank/index.md` 는 `scripts/rebuild_memory_bank_index.py` 가 **각 태스크 폴더의
`activeContext.md` 를 읽어 결정론적으로 생성**한다.

```bash
python scripts/rebuild_memory_bank_index.py
```

> **왜 스크립트만 쓰게 하나**
> 원본 저장소는 정규 생성 경로가 없어 에이전트가 매번 `index.md` 에 수작업으로 행을 덧붙였다.
> 그 결과 누락·중복·고아 행(폴더는 지웠는데 행은 남은 것)이 쌓였고, 활성 태스크 19건 중
> 제목이 비어 있는 것이 다수였다. 생성 경로가 하나면 이런 drift가 생기지 않는다.

`index.md` 를 직접 편집하면 다음 재생성 때 사라진다.

---

## 4. 세션 복구

### 4.1 자동 (기본)

세션이 시작되면 SessionStart 훅이 다음을 컨텍스트에 주입한다:

- 활성 태스크 목록 (`status: ACTIVE` 또는 `BLOCKED`)
- 각 태스크의 현재 Phase와 마지막 체크포인트
- 활성 태스크가 1건이면 그 태스크의 `activeContext.md` 전문

사용자가 아무 말도 하지 않아도 이 정보는 이미 있다. **"어떤 태스크를 하고 계셨나요?"라고
묻지 않는다.**

### 4.2 복구 절차

이어서 작업하라는 지시를 받으면:

```
1. activeContext.md 의 phase / last_checkpoint 확인
2. checkpoints/phase<N>/ 에서 실제 마지막 CP 파일을 읽는다
   └─ activeContext.md 와 어긋나면 CP 파일 쪽을 믿는다
3. CP 의 summary 를 확인 — 그 이전 작업은 다시 하지 않는다
4. CP 의 decisions 를 확인 — 여기 있는 결정은 다시 논의하지 않는다
5. 단계 JSON 의 승인 필드를 확인 — 채워져 있으면 그 HITL 은 재승인하지 않는다
6. CP 의 next_steps[0] 부터 재개한다
```

### 4.3 복구 시 검증

- 폴더명 == `activeContext.md` 의 `task_id` == 모든 CP의 `task_id`
- 폴더가 `<repo-root>/memory-bank/` 아래에 있음 (`workflow_design/` 아래가 아님)
- `artifacts` 에 적힌 파일이 실제로 존재함

불일치가 있으면 **고치지 말고 사용자에게 보고한다.** 어느 쪽이 맞는지는 사람이 안다.

---

## 5. 태스크 종료

Phase 5 승인(HITL#4) 후:

1. `activeContext.md` 의 `status` 를 `DONE` 으로
2. 체크포인트들의 `status` 를 `ARCHIVED` 로
3. `python scripts/rebuild_memory_bank_index.py` 실행 → 완료 목록으로 이동
4. 커밋

태스크 폴더는 **지우지 않는다.** 과거 태스크의 결정 기록은 비슷한 작업을 할 때
같은 논의를 반복하지 않게 해주는 자산이다.
