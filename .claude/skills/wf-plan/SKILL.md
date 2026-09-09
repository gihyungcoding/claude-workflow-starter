---
name: wf-plan
description: >-
  Phase 1 — 태스크를 TDD에 주입할 수 있는 구조 정보로 정규화한다. 코드베이스를 조사해 입력·출력·
  흐름·변경 대상 파일을 확정하고 PLAN_<ID>.json 을 만든다. Use when Phase 1을 시작할 때,
  "설계", "플랜", "계획 수립", "어떻게 구현할지" 요청을 받을 때, 또는 시나리오 작성 전에
  구조를 정해야 할 때.
---

# Phase 1 — Plan

**이 단계는 설계 문서를 쓰는 것이 아니다.** Phase 2a가 시나리오를 쓸 수 있도록
"무엇이 들어가고 무엇이 나오며 어디를 고치는가"를 확정하는 정규화 작업이다.

산출물이 장황하면 잘못하고 있는 것이다. `PLAN_<ID>.json` 은 사람이 읽는 문서가 아니라
다음 Phase의 입력이다.

## MUST

1. **아키텍처 문서와 관련 ADR을 먼저 읽는다** — 계층 배치는 내가 정하는 게 아니라 이미 정해져 있다
2. **코드베이스를 실제로 조사한 뒤** 파일 경로를 적는다 — 추측한 경로를 쓰지 않는다
3. `design.inputs` / `outputs` / `flows` 를 채운다 — 하나라도 비면 EXIT GATE 실패
4. `route` 를 `Backend` / `Frontend` / `Database` 중 하나로 결정하고 **근거를 적는다**
5. 태스크의 `acceptance_criteria` 를 전부 `flows` 로 커버한다
6. 완료 후 `CP-1.3_context-plan.md` 저장 + 커밋

## FORBIDDEN

1. ❌ 존재를 확인하지 않은 파일 경로를 `target_files` 에 쓰기
2. ❌ 구현 코드 작성 — 이 Phase는 코드를 만들지 않는다
3. ❌ 테스트 작성 — Phase 2b의 일이다
4. ❌ `acceptance_criteria` 중 일부를 "나중에" 로 미루기
5. ❌ **아키텍처에 없는 새 컴포넌트·계층을 말없이 도입하기** — ADR을 먼저 쓰자고 제안한다

## EXIT GATE

- `workflow_design/04_plan/PLAN_<ID>.json` 존재, JSON 파싱 성공
- `design.inputs`, `design.outputs`, `design.flows` 모두 비어 있지 않음
- `route ∈ {Backend, Frontend, Database}`
- `codebase_analysis.target_files` 의 모든 경로가 **실재**
- `architecture_refs` 가 채워져 있음 (아키텍처 문서가 있는 경우)
- `CP-1.3_context-plan.md` 저장 및 커밋

---

## 절차

### Step 1 — 태스크 로드

```bash
jq '.[] | select(.id == "TASK-001")' workflow_design/02_tasks/tasks.json
```

`acceptance_criteria` 를 그대로 옮겨 적는다. 이것이 이 태스크의 완료 정의다.

WRU 적격성을 다시 확인한다 (→ `docs/workflow/task-schema.md` §1). Green 단계에서 바뀌는
프로덕션 코드가 없다면 여기서 멈추고 사용자에게 알린다.

### Step 1.5 — 아키텍처·결정 참조

**설계를 시작하기 전에 이미 정해진 것을 확인한다.** 여기서 5분을 쓰면 Phase 4에서
제약 위반으로 되돌아오는 것을 막는다.

```bash
cat docs/architecture/architecture.md
cat docs/decisions/README.md
```

확인할 것:

| 무엇 | 어디서 | 설계에 미치는 영향 |
|---|---|---|
| 계층 구조 | `architecture.md` §2 | 새 코드를 어느 계층에 둘지 |
| 의존 방향 | `architecture.md` §3 | 무엇을 호출해도 되는지 |
| 검사되는 제약 | `constraints.yaml` | Phase 4가 실제로 확인할 것 |
| 관련 결정 | `decisions/README.md` | 이미 결론 난 논의를 반복하지 않는다 |

**route 가 Frontend 이면 디자인 정본도 읽는다.** 없으면 조용히 건너뛴다 (백엔드 전용
프로젝트에는 이 파일들이 없는 것이 정상이다).

```bash
cat docs/product/design.md docs/product/design-tokens.css 2>/dev/null
```

| 무엇 | 어디서 | 설계에 미치는 영향 |
|---|---|---|
| 의미 매핑 | `design.md` §5 | 같은 뜻에 같은 색·같은 말을 쓴다 |
| 토큰 | `design-tokens.css` | 새 색·치수를 만들지 않는다 |
| 하지 않는 것 | `design.md` §6 | 기본값으로 흘러가지 않게 |
| 와이어프레임 | feature 문서 §5 | 화면 구조와 상태 목록 |

`target_files` 에 스타일을 새로 만드는 파일이 있으면, **그 값이 토큰에서 오는지**를
PLAN 의 `unresolved` 에 적는다. Phase 4 의 `DESIGN-*` 가 그것을 검사한다.

제목만 보고 관련 있어 보이는 ADR은 본문을 읽는다. "왜 이 라이브러리를 쓰는가"가
설계 선택을 바꾼다.

```bash
python3 scripts/check_architecture.py    # 지금 걸리는 제약이 있는지 미리 본다
```

**아키텍처에 없는 새 컴포넌트나 계층이 필요하다고 판단되면 여기서 멈춘다.**
설계를 밀고 나가지 말고 사용자에게 알린다:

```
이 태스크는 아키텍처에 없는 캐시 계층을 필요로 합니다.

architecture.md 의 3계층(API/Service/Repository)에 캐시를 어디에 둘지가 정해져 있지
않습니다. 이건 이 태스크를 넘어 적용될 결정이라 ADR로 남기는 게 좋겠습니다.

/wf-adr "캐시 계층 배치" 를 먼저 하시겠어요? 아니면 이번엔 서비스 계층 안에
가둬 두고 나중에 정할까요?
```

Foundation 문서가 아직 없으면(빈 프로젝트) 이 단계를 건너뛰되, 사용자에게
`/wf-init` 을 한 번 안내하고 진행한다. 막지 않는다.

`CP-1.1_codebase-analysis.md` 에 참조한 ADR 번호를 남긴다.

### Step 2 — 코드베이스 조사

**추측하지 않고 찾는다.** 이 단계의 결과가 이후 모든 Phase의 전제가 된다.

- 관련 기능의 기존 구현을 찾는다 (Grep/Glob)
- **재사용할 수 있는 것**을 먼저 찾는다 — 기존 유틸리티·데코레이터·베이스 클래스
- 변경 대상 파일과, 변경이 파급되는 파일을 구분한다
- 기존 테스트가 있으면 그 위치와 패턴을 확인한다 (Phase 2b가 따라야 할 관례)

조사 결과를 `codebase_analysis` 에 기록한다. 찾지 못한 것은 `unresolved` 에 남긴다 —
못 찾았다는 사실이 다음 Phase에 필요한 정보다.

### Step 3 — 라우팅 결정

| route | 판단 기준 |
|---|---|
| `Backend` | 서버 로직·API·권한·비즈니스 규칙이 주 변경 대상 |
| `Frontend` | 화면·상태·렌더링·클라이언트 검증이 주 변경 대상 |
| `Database` | 스키마·마이그레이션·인덱스·쿼리 성능이 주 변경 대상 |

한 태스크는 route 하나만 갖는다. 양쪽에 걸치면 태스크를 나눠야 한다는 신호이므로
사용자에게 알린다 (→ `docs/workflow/task-schema.md` §1 묶음 규칙).

`CP-1.2_design-route.md` 저장 (권장).

### Step 4 — 구조 정규화

```jsonc
{
  "task_id": "TASK-001",
  "route": "Backend",
  "route_reason": "권한 판정과 쿼리 필터가 모두 서버 범위",

  "design": {
    "inputs": [
      { "name": "supervisor_id", "type": "int", "source": "인증 토큰",
        "constraints": ["필수", "활성 사용자여야 함"] },
      { "name": "keyword", "type": "str", "source": "쿼리 파라미터",
        "constraints": ["1자 이상 50자 이하"] }
    ],
    "outputs": [
      { "name": "stores", "type": "list[StoreSummary]",
        "description": "담당 매장 중 keyword 가 매장명에 포함된 것" },
      { "name": "403", "type": "error",
        "description": "담당하지 않는 매장을 직접 조회한 경우" }
    ],
    "flows": [
      { "id": "F1", "name": "담당 매장 검색",
        "steps": ["토큰에서 supervisor_id 추출", "담당 매장 ID 목록 조회",
                  "그 범위 안에서 keyword 로 필터", "결과 반환"],
        "covers": ["담당하지 않는 매장은 검색 결과에 나오지 않는다"] },
      { "id": "F2", "name": "권한 없는 직접 조회",
        "steps": ["store_id 가 담당 목록에 없음", "403 반환"],
        "covers": ["권한 없는 직접 조회는 403을 반환한다"] }
    ]
  },

  "architecture_refs": {
    "layer": "Service",
    "note": "권한 판정은 서비스 계층. API 는 검증만 (architecture.md §2)",
    "constraints_applied": ["ARCH-001"]
  },
  "adr_refs": ["ADR-0002"],

  "codebase_analysis": {
    "target_files": [
      { "path": "src/api/store_search.py", "change": "권한 필터 추가" },
      { "path": "src/repositories/store.py", "change": "담당 매장 조회 메서드 추가" }
    ],
    "reusable": [
      { "path": "src/auth/decorators.py", "symbol": "require_role",
        "note": "권한 체크 데코레이터 — 새로 만들지 말 것" }
    ],
    "existing_tests": ["tests/api/test_store_search.py"],
    "unresolved": []
  },

  "acceptance_criteria": [ /* 태스크에서 그대로 */ ],

  "test_hints": {
    "framework": "pytest",
    "command": "pytest tests/api/test_store_search.py",
    "mock_strategy": "리포지토리 계층을 스텁으로 대체, DB 접근 없음"
  }
}
```

**`flows[].covers` 가 `acceptance_criteria` 를 전부 덮는지 확인한다.** 덮이지 않은 기준이
있으면 flow를 추가하거나, 그 기준이 이 태스크 범위인지 사용자에게 확인한다.

### Step 5 — 저장

1. `workflow_design/04_plan/PLAN_<ID>.json` 저장 (atomic — `docs/workflow/data-antipatterns.md` §6)
2. `CP-1.3_context-plan.md` 저장 (→ `docs/workflow/checkpoint-template.md`)
3. `activeContext.md` 의 `phase`·`last_checkpoint`·`artifacts.plan` 갱신
4. 커밋

```bash
git add workflow_design/04_plan memory-bank/TASK-001
git commit -m "chore(workflow): TASK-001 Phase 1 설계 정규화

Refs: TASK-001"
```

### Step 6 — 보고

```
Phase 1 완료 — TASK-001

  route     Backend (권한 판정과 쿼리 필터가 서버 범위)
  계층      Service (architecture.md §2)
  참조 ADR  ADR-0002 계층형 아키텍처
  제약      ARCH-001 적용 — API 는 리포지토리를 직접 호출하지 않는다
  inputs    2 / outputs 2 / flows 2
  변경 대상  src/api/store_search.py, src/repositories/store.py
  재사용     require_role 데코레이터
  게이트     통과

다음: Phase 2a — 시나리오 설계
```

Phase 1에는 HITL이 없다. 게이트를 통과하면 바로 `wf-scenario` 로 넘어간다.
다만 **route 결정이나 태스크 범위에 의문이 있으면** 넘어가기 전에 사용자에게 확인한다 —
설계가 틀린 채로 진행하면 Phase 2a에서 롤백된다.
