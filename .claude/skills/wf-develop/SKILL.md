---
name: wf-develop
description: >-
  Phase 3 — Red 테스트를 통과시키는 최소 구현을 하고 리팩토링한다(TDD Green). Use when Phase 3을
  시작할 때, "구현", "Green", "테스트 통과시키기", "기능 개발" 요청을 받을 때, 또는 시나리오·Red
  통합 승인(HITL#1·2) 직후.
---

# Phase 3 — Green

Red 테스트를 통과시킨다. **최소 구현 → 확인 → 리팩토링** 순서를 지킨다.

## MUST

1. **Red 테스트를 먼저 통과시킨다.** 그 다음에 리팩토링한다
2. Plan의 `codebase_analysis.reusable` 에 있는 것을 재사용한다 — 같은 것을 다시 만들지 않는다
3. 리팩토링 후 테스트를 **다시 실행**해 여전히 통과하는지 확인한다
4. 기존 테스트가 깨지지 않았는지 전체 스위트를 돌린다
5. 린트/포맷을 통과시킨다
6. **Phase 4 로 넘기기 전에 `code-reviewer` 로 자체 리뷰를 한다** (Step 5.5). 결함은 여기서
   고친다 — Phase 4 에서 잡히면 거절 기록·롤백·재승인까지 한 바퀴를 더 돈다

## FORBIDDEN

1. ❌ **테스트를 고쳐서 통과시키기** — 단언 약화, skip 처리, 기대값 변경
2. ❌ 시나리오에 없는 기능 추가 (범위 확장)
3. ❌ 테스트를 실행하지 않고 "구현 완료" 보고
4. ❌ 전체 스위트를 돌리지 않고 넘어가기 — 회귀를 못 잡는다
5. ❌ Plan에 없는 파일을 대량 수정 — 필요하면 이유를 기록한다
6. ❌ **자체 리뷰의 `[correctness]` 소견을 고치지 않거나 기록하지 않고 Phase 4 로 넘기기** —
   Phase 4 리뷰어가 같은 결함을 다시 찾아 FAIL 이 된다

## EXIT GATE

- `workflow_design/06_dev/DEV_<ID>.json` 존재
- `test_status == "green"`, `failed == 0`
- `passed >= red_scenarios.length`
- 전체 테스트 스위트 통과 (기존 테스트 포함)
- 린트 error 0 — **린트 도구가 없으면 `"errors": null` + `skipped_reason`.**
  `"command": "N/A", "errors": 0` 으로 적으면 이 게이트가 무력해진다
- `pre_review.rounds` 가 1개 이상이고, 마지막 라운드 이후 남은 `[correctness]` 가
  `pre_review.unresolved` 에 모두 적혀 있음
- `CP-3.4` 저장 및 커밋

---

## 절차

### Step 1 — 입력 로드

```bash
cat workflow_design/05_scenario/TEST_TASK-001.json     # 무엇을 통과시켜야 하는가
cat workflow_design/04_plan/PLAN_TASK-001.json         # 어디를 고치는가, 무엇을 재사용하는가
```

`human_review.approved` 가 `true` 가 아니면 중단한다.

**Phase 4 FAIL 로 돌아왔다면** `VERIFY_<ID>.json` 의 `root_causes` 를 먼저 읽는다
(→ `wf-verify/references/root-cause-sweep.md`).

- 증상 하나가 아니라 **뿌리**를 고친다. 증상만 고치면 같은 뿌리의 다음 변종 때문에 다시 돌아온다
- 같은 뿌리의 변종이 둘 이상이면 **공통 지점**(검증기 · 필터 · 역직렬화 · 공용 메서드)에서
  고친다. 필드마다 따로 붙이면 빠뜨린 한 곳이 다음 FAIL 이 된다. 공통 지점이 없으면 걸리는
  모든 위치를 Grep 으로 열거해 `rollback_fixes[].sites` 에 남긴다
- `probe: reproduced` 변종마다 **테스트를 먼저 실패시킨 뒤** 고친다 (Red → Green)
- `probe: not_probed` 변종도 **테스트를 쓴다** — 테스트가 프로브다. 실패하면 고치고, 통과하면
  그 테스트가 다음 VERIFY 의 `not_reproduced` 근거(`evidence`)가 된다
- 변종이 시나리오에 없는 동작이라 테스트를 쓸 수 없다면 여기서 만들지 않는다. Phase 2a 로
  돌아가되 **변종 전부를 한 번에** 가져간다 (시나리오에 없는 기능 추가는 금지다)
- 고친 내용은 `DEV_<ID>.json` 의 `rollback_fixes` 에
  `{root_cause, variants, tests, fix_locus: "common" | "per_site", sites}` 로 남긴다

구현 순서나 재사용 대상을 정했으면 `CP-3.4` 의 `decisions` 에 남긴다.

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

`CP-3.4` 를 갱신한다 — `summary` 에 통과 수 한 줄. 실행 출력은 `DEV_<ID>.json` 에 있다.

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

리팩토링 여부와 이유를 `CP-3.4` 의 `decisions` 에 남긴다 — 하지 않기로 했어도.

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

### Step 5.5 — 자체 리뷰

Phase 4 1차 검증이 FAIL 난 태스크가 최근 5건 중 4건이었다(TASK-010·011·012·014). 거의
전부 `code-reviewer` 의 `[correctness]` 소견이었고, 한 번 FAIL 날 때마다 거절 기록 →
롤백 → 수정 → 재검증 → 재승인에 20~40분이 들었다. **같은 리뷰어를 여기서 먼저 부른다.**

이 리뷰가 Phase 4 리뷰를 대신하지는 않는다. Phase 4 는 리뷰어를 다시 부르고, 이 단계에서
나온 `root_causes` 를 이전 라운드로 넘겨받는다.

**1. 구현을 먼저 커밋한다.** 리뷰어는 `git diff <기준>...HEAD` 를 읽는다. 커밋하지 않은
파일, 특히 새로 만든 파일은 리뷰 범위에 들어가지 않는다.

```bash
git add <변경한 소스 경로>
git commit -m "feat(<scope>): <subject>

Refs: TASK-001"
```

**2. 리뷰어를 부른다.** 프롬프트는 Phase 4 Step 5 와 같은 형식이다. **`CLAUDE.md`
「이 프로젝트에 대해」에 `code-reviewer` 리뷰 지시가 있으면 여기에도 그대로 넣는다**
(예: 이 저장소의 JPA 지시).

```
Agent({
  subagent_type: "code-reviewer",
  description: "TASK-001 Phase 3 자체 리뷰",
  run_in_background: false,
  prompt: `
TASK-001 의 변경 코드를 리뷰해주세요. Phase 3 자체 리뷰입니다.

변경 파일: <DEV 에 적을 changed_files>
비교 기준: git diff <기준 브랜치>...HEAD
설계: workflow_design/04_plan/PLAN_TASK-001.json
시나리오: workflow_design/05_scenario/SCENARIO_TASK-001.md
<CLAUDE.md 의 프로젝트별 리뷰 지시>
`
})
```

**3. 소견에 따라 처리한다.**

| 소견 | 처리 |
|---|---|
| `[correctness]`, 변종이 시나리오 안의 동작 | Step 1 「Phase 4 FAIL 로 돌아왔다면」 규칙대로 고친다 — 뿌리를 공통 지점에서 고치고, 변종마다 **테스트를 먼저 실패시킨 뒤** 고친다. 고친 것은 `fix` 커밋으로 남긴다 |
| `[correctness]`, 변종이 시나리오에 없는 동작 | 여기서 만들지 않는다. **Phase 4 를 거치지 말고 지금** 사용자에게 2a 롤백을 제안한다. 변종은 전부 한 번에 가져간다 |
| `[security]` | `[correctness]` 와 같이 처리한다 |
| `[design]` `[reuse]` `[test]` | 범위 안에서 싸게 고칠 수 있으면 고친다. 아니면 `pre_review.deferred` 에 적어 Phase 4 로 넘긴다 |

새로 쓴 테스트는 통합 HITL 에서 승인받은 테스트가 아니다. `pre_review.rounds[].tests_added` 에
적어 Phase 4 가 리뷰하게 한다. **승인된 테스트는 고치지 않는다** — 고쳐야 하면 Step 3 의
3요건을 따른다.

**4. 고쳤으면 한 번 더 리뷰한다.** `wf-verify/references/code-review-rounds.md` §1·§2 대로
이전 `root_causes` 를 넘기고, 수정 커밋 범위(`<1라운드 HEAD>...HEAD`)를 지정한다.
「같은 카테고리 전수」 지시에 **「이번에 추가한 방어 코드가 공유 함수의 모든 호출부를 덮는가」**를
명시해 넣는다. 공유 검증 함수의 호출부 하나에만 방어를 넣고 나머지가 남으면 리뷰어가 수정 범위만
보고 통과시킨다 (→ TASK-016 RC-2 — 자체 리뷰가 놓치고 Phase 4 에서 FAIL).
**자체 리뷰는 최대 2라운드다.** 2라운드 뒤에도 `[correctness]` 가 남으면 고치려고 더 돌지
않는다. `pre_review.unresolved` 에 적고 사용자에게 알린 뒤 Phase 4 로 넘긴다. 판정은
Phase 4 가 한다.

소견이 없으면 1라운드로 끝난다. **결함이 없다는 리뷰 결과도 `rounds` 에 남긴다.**

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
  "scope_deviations": [],
  "pre_review": {                      // Step 5.5 — 자체 리뷰
    "rounds": [
      { "n": 1, "scope": "전체 develop...HEAD", "findings": 1,
        "tests_added": ["StoreSearchTest#blankKeywordIsRejected"],
        "fix_commit": "b4c5d6e" },
      { "n": 2, "scope": "수정 커밋 a1b2c3d...HEAD · 같은 카테고리 전수", "findings": 0,
        "tests_added": [], "fix_commit": null }
    ],
    "root_causes": [ /* 리뷰어가 낸 그대로 — Phase 4 가 이전 라운드로 넘겨받는다 */ ],
    "unresolved": [],                  // 2라운드 뒤에도 남은 [correctness]
    "deferred": []                     // 고치지 않고 Phase 4 로 넘긴 비결함 소견
  }
}
```

`scope_deviations` — Plan에 없던 파일을 고쳤다면 여기에 이유와 함께 적는다.
비어 있는 것이 정상이고, 항목이 있으면 Phase 4가 그것을 검토한다.

`CP-3.4_context-dev.md` 를 마무리 갱신하고(`next_steps` 를 Phase 4 로), `activeContext.md` 갱신, 커밋.
소스는 Step 5.5 에서 이미 커밋했으므로 여기서는 산출물만 커밋한다.

```bash
git add workflow_design/06_dev memory-bank/TASK-001
git commit -m "chore(workflow): TASK-001 Phase 3 Green 완료

Refs: TASK-001"
```

### Step 7 — 보고

`track: light` 면 테스트 수·린트·범위 이탈·자체 리뷰만 보고한다 (→ `wf-orchestrator` 「경량 경로」).

```
Phase 3 완료 — TASK-001

  변경     src/api/store_search.py (+24), src/repositories/store.py (+12)
  재사용    require_role 데코레이터
  테스트    18/18 통과 (대상 6 + 기존 12)
  린트     error 0
  리팩토링  쿼리 로직을 리포지토리 계층으로 이동
  자체 리뷰 2라운드 — 결함 1건(빈 keyword) 수정, 테스트 1건 추가, 미해결 0
  게이트    통과

다음: Phase 4 — 검증
```

Phase 3에는 HITL이 없다. 게이트 통과 후 `wf-verify` 로 넘어간다.
