---
name: wf-red
description: >-
  Phase 2b — 승인된 시나리오를 실패하는 테스트 코드로 옮기고 사람 승인(HITL#2)을 받는다.
  Use when Phase 2b를 시작할 때, "Red 코드", "실패 테스트 작성", "테스트 코드 생성" 요청을
  받을 때, 또는 HITL#1 승인 직후.
---

# Phase 2b — Red

승인된 시나리오를 **실패하는** 테스트로 옮긴다. 이 단계가 끝나면 테스트는 반드시 빨간불이다.

## MUST

1. 승인된 시나리오 **하나당 테스트 함수 하나** — 개수가 정확히 일치해야 한다
2. 테스트를 실행해 **실제로 실패하는 것을 확인**한다 (실행 출력을 남긴다)
3. 실패 사유가 **"구현이 없어서"** 인지 확인한다 — 테스트 코드 자체의 결함은 Red 가 아니다
   (정적 컴파일 언어는 Step 3의 「컴파일 언어」 절을 먼저 읽는다)
4. 기존 테스트 파일의 관례를 따른다 (Phase 1의 `codebase_analysis.existing_tests`)
5. HITL#2 승인을 `AskUserQuestion` 으로 받는다

## FORBIDDEN

1. ❌ **구현 코드 작성** — 이 Phase는 로직을 한 줄도 만들지 않는다.
   컴파일 언어의 스켈레톤은 예외이나 허용 범위가 정해져 있다 (Step 3)
2. ❌ 테스트를 통과시키기 위해 단언을 약화시키기
3. ❌ 시나리오에 없는 테스트 추가 / 시나리오에 있는데 테스트 누락
4. ❌ 실행하지 않고 "실패할 것"이라고 보고하기
5. ❌ `SCENARIO_<ID>.md` 수정 — 시나리오는 HITL#1에서 확정됐다

## EXIT GATE

- `workflow_design/05_scenario/TEST_<ID>.json` 존재
- `red_scenarios.length > 0`
- 테스트 실행 결과가 **실제 실패** (출력을 `red_result` 에 기록)
- 테스트 함수 개수 == 승인된 시나리오 개수 (grep으로 센 수치를 기록)
- `human_review.approved == true`
- `CP-2.5`, `CP-2.6` 저장 및 커밋

---

## 절차

### Step 1 — 입력 로드

```bash
cat workflow_design/05_scenario/SCENARIO_TASK-001.md      # SoT
jq '.human_input.generate_red_trigger' workflow_design/05_scenario/SCENARIO_TASK-001.json
```

`generate_red_trigger` 가 `true` 가 아니면 **중단한다.** HITL#1이 끝나지 않았다는 뜻이다.

Plan의 `test_hints` 로 프레임워크·명령·목 전략을 확인한다.

> Phase 2b는 새 세션에서 시작되는 경우가 많다. 그때는 `PLAN_<ID>.json` 도 함께 읽는다.

### Step 2 — 테스트 작성

시나리오 순서대로 1:1로 옮긴다.

```python
def test_sc01_담당_매장이_검색된다():
    """SC-01 (happy)

    Given 슈퍼바이저 S가 매장 A, B를 담당한다
    When  S가 "강남"으로 검색한다
    Then  결과에 매장 A가 포함된다
    """
    # Given
    supervisor = make_supervisor(stores=["A", "B"])
    set_store_name("A", "강남점")

    # When
    result = search_stores(supervisor.id, keyword="강남")

    # Then
    assert "A" in [s.id for s in result]
    assert len(result) == 1
```

규칙:

- 함수명에 **시나리오 ID를 넣는다** (`test_sc01_...`) — 매핑을 기계적으로 셀 수 있게
- docstring에 GWT를 그대로 옮긴다 — 테스트만 봐도 의도를 알 수 있게
- 본문을 `# Given` / `# When` / `# Then` 으로 나눈다
- Then의 단언은 시나리오 문장과 **1:1로 대응**시킨다. 문장 3개면 단언도 3개

### Step 3 — 실행해서 실패 확인

**`CLAUDE.md` 「이 프로젝트에 대해」의 테스트 명령을 쓴다.**

```bash
<CLAUDE.md 의 테스트 명령>    # 예: pytest -v / ./gradlew test / npm test
```

출력을 그대로 기록한다. 판정 기준은 **실패 유형이 아니라 원인**이다.

| | |
|---|---|
| **Red 다** | 단언이 실패한다 — 로직이 없거나 틀렸다 |
| **Red 가 아니다** | 테스트 코드 자체가 잘못됐다 (오타, 잘못된 임포트, 잘못된 단언) |

확인할 것:

| 확인 | 왜 |
|---|---|
| 모든 새 테스트가 실패 | 하나라도 통과하면 이미 구현됐거나 단언이 약하다 |
| 기존 테스트는 계속 통과 | 새 테스트가 기존 것을 깨뜨리지 않았는지 |

통과한 테스트가 있으면 단언을 강화하거나, 그 기능이 이미 있는지 확인한다.

#### 컴파일 언어 (Java · Kotlin · Go · Rust · C# · TypeScript)

동적 언어에서는 `NameError` 가 Red 다 — 호출 대상이 없어도 테스트가 **실행은 된다.**
컴파일 언어에서는 그렇지 않다. 클래스나 메서드가 없으면 **테스트가 컴파일조차 되지
않으므로**, 실행 결과 자체가 존재하지 않는다. "구현이 없어서 실패" 를 관찰할 수 없다.

따라서 **컴파일용 스켈레톤이 선행돼야 한다.** 허용 범위는 좁다.

| | |
|---|---|
| **허용** | 클래스·인터페이스 선언, 메서드 시그니처, 필드, enum 상수, 구조적 애노테이션 |
| **허용** | 메서드 본문은 `throw new UnsupportedOperationException()` **한 줄만** |
| **금지** | 조건 분기, 계산, 쿼리, 실제 값 반환 — **빈 리스트·null 반환도 금지** |

빈 리스트 반환이 금지인 이유: "결과가 비어 있다" 를 검증하는 시나리오가 **우연히
통과**한다. 그것은 구현이 아니라 사고다.

**스켈레톤이 순수한지 검증하는 방법** — 모든 실패가 `UnsupportedOperationException`
이면 로직이 한 줄도 없다는 뜻이다.

```bash
./gradlew test 2>&1 | grep -c "UnsupportedOperationException"   # == 실패 개수여야 한다
```

숫자가 실패 개수보다 적으면 어딘가에 로직이 들어갔다. 그 테스트를 찾아 스켈레톤으로
되돌린다.

**애노테이션이 곧 구현인 경우는 아예 넣지 않는다.** 스키마 제약(`@NotNull`,
`@Column(length=200)`, `@Check`)은 선언이 아니라 동작이다 — 넣는 순간 그 제약을
검증하는 시나리오가 통과해버린다. Phase 3 에서 추가한다.

컴파일 스켈레톤은 Red 커밋에 함께 담는다. `TEST_<ID>.json` 의
`compile_skeleton` 에 어느 파일에 무엇을 넣었는지 적는다.

### Step 4 — 인벤토리 검증

시나리오와 테스트 개수가 맞는지 **센다.**

```bash
grep -c "^def test_" tests/api/test_store_search.py
jq '.scenarios | length' workflow_design/05_scenario/SCENARIO_TASK-001.json
```

두 수가 다르면 어느 시나리오가 빠졌는지 찾는다. 시나리오 ID로 대조:

```bash
grep -o "test_sc[0-9]*" tests/api/test_store_search.py | sort
jq -r '.scenarios[].id' workflow_design/05_scenario/SCENARIO_TASK-001.json
```

### Step 5 — TEST JSON 저장

```jsonc
{
  "task_id": "TASK-001",
  "supersedes": "SCENARIO_TASK-001.json",
  "test_file": "tests/api/test_store_search.py",
  "red_scenarios": [
    { "scenario_id": "SC-01", "test_function": "test_sc01_담당_매장이_검색된다",
      "status": "red", "failure": "NameError: name 'search_stores' is not defined" }
  ],
  "red_result": {
    "command": "pytest tests/api/test_store_search.py -v",
    "total": 6, "failed": 6, "passed": 0,
    "existing_tests_still_passing": true
  },
  "inventory_check": {
    "scenarios": 6, "test_functions": 6, "match": true
  },
  "testing_preferences": {
    "framework": "pytest",
    "mock_strategy": "리포지토리 계층 스텁, DB 접근 없음"
  },
  //  컴파일 언어만 — 무엇을 컴파일 통과용으로 넣었는지
  //  "compile_skeleton": {
  //    "files": ["src/main/java/.../PerformanceService.java"],
  //    "contents": "시그니처 4개, 본문은 전부 UnsupportedOperationException",
  //    "purity_check": "실패 11건 == UnsupportedOperationException 11건"
  //  },
  "human_review": { "approved": false }
}
```

`CP-2.5_red-code.md` 저장.

### Step 6 — HITL #2

```
Phase 2b — TASK-001

테스트 6개 작성 → 6개 전부 실패 (기대한 상태)
  tests/api/test_store_search.py

  test_sc01_담당_매장이_검색된다     NameError: search_stores
  test_sc02_담당하지_않는_매장은_403  NameError: search_stores
  ...

인벤토리  시나리오 6 == 테스트 함수 6 ✓
기존 테스트 12개 계속 통과 ✓
```

`AskUserQuestion`:

- **승인** → Phase 3 (구현)
- **테스트 수정** → Step 2로 (단언이 틀렸다 등)
- **시나리오로 롤백** → Phase 2a로

승인 후:
1. `TEST_<ID>.json` 의 `human_review.approved = true`
2. `CP-2.6_hitl2-approved.md` 저장
3. `activeContext.md` 갱신
4. 커밋 — **테스트 코드도 함께 커밋한다** (빨간 상태로 커밋하는 것이 정상이다)

```bash
git add tests/ workflow_design/05_scenario memory-bank/TASK-001
git commit -m "test(TASK-001): 매장 검색 권한 필터 Red 테스트 6건

Refs: TASK-001"
```
