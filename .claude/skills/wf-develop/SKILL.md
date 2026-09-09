---
name: wf-develop
description: >-
  Phase 3 — Red 테스트를 통과시키는 최소 구현을 하고 리팩토링한다(TDD Green). Use when Phase 3을
  시작할 때, "구현", "Green", "테스트 통과시키기", "기능 개발" 요청을 받을 때, 또는 HITL#2
  승인 직후.
---

# Phase 3 — Green

Red 테스트를 통과시킨다. **최소 구현 → 확인 → 리팩토링** 순서를 지킨다.

## MUST

1. **Red 테스트를 먼저 통과시킨다.** 그 다음에 리팩토링한다
2. Plan의 `codebase_analysis.reusable` 에 있는 것을 재사용한다 — 같은 것을 다시 만들지 않는다
3. 리팩토링 후 테스트를 **다시 실행**해 여전히 통과하는지 확인한다
4. 기존 테스트가 깨지지 않았는지 전체 스위트를 돌린다
5. 린트/포맷을 통과시킨다

## FORBIDDEN

1. ❌ **테스트를 고쳐서 통과시키기** — 단언 약화, skip 처리, 기대값 변경
2. ❌ 시나리오에 없는 기능 추가 (범위 확장)
3. ❌ 테스트를 실행하지 않고 "구현 완료" 보고
4. ❌ 전체 스위트를 돌리지 않고 넘어가기 — 회귀를 못 잡는다
5. ❌ Plan에 없는 파일을 대량 수정 — 필요하면 이유를 기록한다

## EXIT GATE

- `workflow_design/06_dev/DEV_<ID>.json` 존재
- `test_status == "green"`, `failed == 0`
- `passed >= red_scenarios.length`
- 전체 테스트 스위트 통과 (기존 테스트 포함)
- 린트 error 0 — **린트 도구가 없으면 `"errors": null` + `skipped_reason`.**
  `"command": "N/A", "errors": 0` 으로 적으면 이 게이트가 무력해진다
- `CP-3.2`, `CP-3.4` 저장 및 커밋

---

## 절차

### Step 1 — 입력 로드

```bash
cat workflow_design/05_scenario/TEST_TASK-001.json     # 무엇을 통과시켜야 하는가
cat workflow_design/04_plan/PLAN_TASK-001.json         # 어디를 고치는가, 무엇을 재사용하는가
```

`human_review.approved` 가 `true` 가 아니면 중단한다.

`CP-3.1_impl-strategy.md` 저장 (권장) — 어떤 순서로 구현할지, 재사용할 것이 무엇인지.

### Step 2 — 최소 구현

**테스트를 통과시키는 가장 단순한 코드**를 쓴다. 이 단계에서 아름다움을 추구하지 않는다.

- Plan의 `target_files` 를 먼저 본다
- `reusable` 에 있는 것을 실제로 쓴다. 쓰지 않기로 했다면 이유를 기록한다
- 한 번에 하나의 테스트를 통과시킨다 — 6개를 동시에 고치면 무엇이 무엇을 고쳤는지 모른다

주변 코드의 관례를 따른다: 네이밍, 에러 처리 방식, 로깅, 주석 밀도.
**이 저장소에서 자연스러워 보이는 코드**를 쓴다.

### Step 3 — Green 확인

```bash
pytest tests/api/test_store_search.py -v      # 대상 테스트
pytest                                        # 전체 스위트
```

전체를 돌리는 이유는 회귀 때문이다. 대상 테스트만 통과하고 기존 것이 깨지면 Green이 아니다.

실패가 남아 있으면 Step 2로 돌아간다. **테스트를 고치지 않는다.**
테스트가 정말 잘못됐다고 판단되면 Phase 2b로 롤백을 사용자에게 제안한다.

`CP-3.2_tests-green.md` 저장 (실행 출력 요약 포함).

### Step 4 — 리팩토링

테스트가 초록불인 상태에서만 한다. 테스트가 안전망 역할을 한다.

볼 것:

- 중복 — 같은 로직이 두 곳에 있는가
- 이름 — 무엇을 하는지 이름이 말하는가
- 크기 — 한 함수가 여러 일을 하는가
- 위치 — 이 코드가 이 계층에 있는 게 맞는가

리팩토링 **후 테스트를 다시 돌린다.** 이것을 건너뛰면 리팩토링이 아니라 그냥 수정이다.

```bash
pytest
```

`CP-3.3_refactor.md` 저장 (권장). 리팩토링을 하지 않기로 했다면 그 판단도 기록한다.

### Step 5 — 린트·포맷

**`CLAUDE.md` 「이 프로젝트에 대해」의 린트 명령을 쓴다.** 아래는 형식 예시다.

```bash
<CLAUDE.md 의 린트 명령>     # 예: ruff check . / ./gradlew spotlessCheck / npm run lint
```

**변경한 파일에서 error 0** 이어야 한다. 기존 파일의 경고는 이 태스크 범위가 아니다 —
고치고 싶으면 별도 태스크로 만든다.

### `CLAUDE.md` 의 린트 항목이 `TODO` 이면

**`errors: 0` 으로 적고 넘어가지 않는다.** EXIT GATE 의 "린트 error 0" 이 그 순간
무의미해지고, 이후 모든 태스크에서 같은 방식으로 우회된다.

| 상황 | 처리 |
|---|---|
| 도구를 지금 도입할 수 있다 | 사용자에게 알리고 도입한다. `CLAUDE.md` 의 린트 줄도 함께 채운다 |
| 이 프로젝트에 도입하지 않기로 했다 | `"errors": null, "skipped_reason": "<사유>"` 로 적는다 |

첫 태스크에서 도입하는 편이 거의 항상 낫다. 코드가 적을 때 포매터를 넣으면 변경이 작고,
나중에 넣으면 전체 파일이 한 번에 재포맷되어 리뷰가 불가능해진다.

### Step 6 — DEV JSON 저장

```jsonc
{
  "task_id": "TASK-001",
  "changed_files": [
    { "path": "src/api/store_search.py", "change": "권한 필터 추가", "lines_changed": 24 },
    { "path": "src/repositories/store.py", "change": "find_by_supervisor 추가", "lines_changed": 12 }
  ],
  "reused": [
    { "path": "src/auth/decorators.py", "symbol": "require_role" }
  ],
  "test_status": "green",
  "test_result": {
    "command": "pytest",
    "total": 18, "passed": 18, "failed": 0,
    "target_tests_passed": 6
  },
  "lint": { "command": "ruff check .", "errors": 0, "warnings": 0 },
  //  도구가 없으면 — 0 이 아니라 null 이다
  //  "lint": { "command": null, "errors": null,
  //            "skipped_reason": "CLAUDE.md 의 린트 항목이 TODO" },
  "refactoring": [
    { "what": "매장 ID 목록 조회를 리포지토리로 이동",
      "why": "API 계층에 쿼리 로직이 있었음" }
  ],
  "scope_deviations": []
}
```

`scope_deviations` — Plan에 없던 파일을 고쳤다면 여기에 이유와 함께 적는다.
비어 있는 것이 정상이고, 항목이 있으면 Phase 4가 그것을 검토한다.

`CP-3.4_context-dev.md` 저장, `activeContext.md` 갱신, 커밋.

```bash
git add src/ workflow_design/06_dev memory-bank/TASK-001
git commit -m "feat(store): 매장 검색에 슈퍼바이저 권한 필터 적용

Refs: TASK-001"
```

### Step 7 — 보고

```
Phase 3 완료 — TASK-001

  변경     src/api/store_search.py (+24), src/repositories/store.py (+12)
  재사용    require_role 데코레이터
  테스트    18/18 통과 (대상 6 + 기존 12)
  린트     error 0
  리팩토링  쿼리 로직을 리포지토리 계층으로 이동
  게이트    통과

다음: Phase 4 — 검증
```

Phase 3에는 HITL이 없다. 게이트 통과 후 `wf-verify` 로 넘어간다.
