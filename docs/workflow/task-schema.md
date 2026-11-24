# 태스크 스키마와 WRU 기준

`workflow_design/02_tasks/tasks.json` 에 담기는 태스크의 형식과, **무엇이 하나의 태스크인가**를
정의한다. 원본 저장소의 `docs/plan_prompt.md`(WRU 룰)를 계승했다.

> **우선순위**: 이 문서의 WRU 기준은 태스크를 만드는 모든 경로(사람이 직접 쓰든, 문서에서
> 추출하든)에 적용된다.

---

## 1. WRU — Workflow-Runnable Unit

각 태스크는 7단계 워크플로우(Plan → Scenario → Red → Green → Verify → Reflect)를
**1회 완주할 수 있는 단위**여야 한다.

### 필수 조건 (모두 만족)

1. **Plan 가능** — 입력·출력이 명확해 설계를 쓸 수 있다
2. **Scenario 작성 가능** — Given/When/Then 동작이 **2개 이상** (happy 1 + error 1 최소)
3. **Red 작성 가능** — 실패하는 자동 테스트를 쓸 수 있다 (unit/integration/E2E 무관)
4. **Green 구현 변경 있음** — 실제 프로덕션 코드가 **1개 파일 이상** 바뀐다
5. **Verify 자동화 가능** — 빌드/테스트/린트로 완료를 판정할 수 있다

### 금지 패턴 — 단독 태스크로 만들지 않는다

| 패턴 | 어떻게 처리하나 |
|---|---|
| "재현·원인 분석"만 | 후속 구현 태스크의 `description` 으로 흡수 |
| "수동 QA"만 | 후속 구현 태스크의 `acceptance_criteria` 로 흡수 |
| "스펙·DTO 정의"만 | 후속 구현 태스크의 Plan 단계로 흡수 |
| "키/항목 수집"만 | 적용 태스크와 합침 |
| 단일 라인 CSS/문자열 수정만 | 같은 화면의 인접 수정과 묶음 |

이유는 단순하다. 이런 작업은 7단계를 돌릴 만한 실체가 없어서, 워크플로우 오버헤드가
작업 자체보다 커진다.

### 묶음 규칙

같은 이슈에서 "분석 → 백엔드 → 프론트 → QA"로 갈라지는 작업은 1~2개로 통합한다.

- 같은 `primary_category`: **단일 태스크**
- `primary_category` 가 갈리는 경우(Backend ↔ Frontend): 카테고리별 1개씩 (**최대 2개**)
  - Frontend 태스크는 반드시 `depends_on: ["<Backend 태스크 ID>"]`
- 분리하려면 **양쪽 모두에 구체적 증거**가 있어야 한다. 한쪽이 추측이면 분리하지 않는다

### 크기 기준

| 추정치 | 판정 |
|---|---|
| < 4h | 인접 태스크와 묶을 후보 (오버헤드가 더 큼) |
| **4~16h** | **정상 WRU** |
| > 16h | 두 개로 분할 |

---

## 2. 태스크 스키마

```jsonc
{
  "id": "TASK-001",                      // ^TASK-\d{3,}$ — artifact-paths.md §1
  "title": "매장 검색 API에 권한 필터 추가",
  "description": "슈퍼바이저가 담당하지 않는 매장을 검색 결과에서 제외합니다. 재현·원인 분석과 수동 QA를 흡수합니다.",

  "primary_category": "Backend",         // Backend | Frontend | Database
  "sub_categories": [],                  // Frontend 일 때만 채운다 (아래 §3)
  "reason_primary": "권한 판정과 쿼리 필터가 모두 서버 범위",

  "priority": "High",                    // High | Medium | Low
  "depends_on": [],                      // 선행 태스크 ID 배열
  "status": "todo",                      // todo | in_progress | done | blocked

  "meta": {
    "estimate": { "unit": "hour", "value": 8 },
    "risk": "medium",                    // low | medium | high

    "acceptance_criteria": [
      "담당하지 않는 매장은 검색 결과에 나오지 않는다",
      "기존 매장 조회 동작이 깨지지 않는다 (회귀 테스트 통과)",
      "권한 없는 직접 조회는 403을 반환한다"
    ],

    "absorbed_steps": [                  // 흡수한 단계를 명시 (금지 패턴 처리 흔적)
      "재현·원인 분석",
      "수동 QA"
    ],

    "implementation_spec": {
      "paths": []                        // §4 규칙 — 추측 금지
    },

    "complexity": {
      "size_score": 3,
      "risk_score": 2,
      "total_score": 42.0,
      "level": "보통"                     // 단순 | 보통 | 복잡
    }
  },

  "source_refs": {                       // 이 태스크의 출처
    "request_id": "REQ-001",             // 요청(BRIEF)에서 나온 태스크 — brief-schema.md
    "source_file": "docs/product/features/store-search-permission.md",
    "sections": ["1-2"],                 // 어느 섹션에서 왔나
    "sections_with_ranges": [            // 더 정확한 위치
      { "section": "1-2", "range": "Task A" }
    ]
  }
}
```

### `source_refs` — 문서에서 만들어진 태스크

`/wf-tasks-from-doc` 이 채운다. 손으로 만든 태스크는 없어도 된다.

이 필드가 있으면 `/wf-start` 가 그 문서를 함께 읽는다. 태스크의 `description` 보다
문서에 맥락이 훨씬 많기 때문이다 — 배경, 구현 참고 경로, 범위 외.

반대 방향 추적(문서 → 태스크)은 요구사항 문서의 `## 1-2` 표 "태스크 ID" 열이 담당한다.
**양쪽이 다 있어야 추적이 끊기지 않는다.**

### `meta.source_evidence` — 코드 근거 (선택)

요구사항 문서의 `## 5. 구현 참고` 에 적힌 참조를 실제 코드에서 확인한 결과.

```jsonc
"meta": {
  "source_evidence": [
    { "ref": "StoreService.search()",
      "resolved": "src/services/store.py:42",
      "basis": "explicit_ref" },        // explicit_ref | domain_inferred
    { "ref": "GET /api/stores/search",
      "resolved": null,
      "basis": "explicit_ref",
      "note": "아직 없는 엔드포인트 (신규)" }
  ]
}
```

`basis`

- `explicit_ref` — 문서에 **직접 적힌** 참조를 코드에서 찾은 것. 사실로 취급한다
- `domain_inferred` — 도메인 어휘로 추론해 찾은 것. **후보일 뿐이고 문서를 뒤집지 않는다**

이 필드가 없어도 워크플로우는 동작한다. 있으면 Phase 1의 코드베이스 조사가 빨라진다.

### 적격 임계

- `complexity.total_score < 30` 또는 `size_score < 2` → WRU 부적격. 통합하거나 제외한다
- `complexity.level == "단순"` 이고 `estimate < 4h` → 단독 태스크 금지

---

## 3. 카테고리 · 문서 연결

`primary_category` 는 `Backend` / `Frontend` / `Database` 중 하나다.

`Frontend` 인 경우에만 `sub_categories` 에 대상 앱을 넣는다. **이 목록은 프로젝트마다 다르므로
신규 프로젝트에서는 `CLAUDE.md` 에 정의하고 여기서는 형식만 규정한다.**

```jsonc
// 예: 앱이 여러 개인 프로젝트
"primary_category": "Frontend",
"sub_categories": ["admin"]        // CLAUDE.md 에 정의된 값 중 하나

// 예: 단일 앱 프로젝트
"primary_category": "Frontend",
"sub_categories": []
```

---

## 4. `implementation_spec.paths` — 추측 금지

- **입력 자료에 명시적으로 적힌 파일 경로만** 넣는다
- 적힌 경로가 없으면 `"paths": []` 로 둔다
- 프로젝트 구조나 네이밍 관행을 근거로 경로를 **만들어내지 않는다**

> 태스크 추출 단계에서 지어낸 경로는 Phase 1이 그것을 사실로 받아들이게 만든다.
> 존재하지 않는 파일을 전제로 설계가 진행되면 Phase 3에서야 발견된다.
> 경로 탐색은 Phase 1의 코드베이스 분석이 할 일이지 태스크 정의가 할 일이 아니다.

---

## 5. `tasks.json` 파일 형식

태스크 객체의 **배열**이다. 최상위에 래퍼 객체를 두지 않는다.

```json
[
  { "id": "TASK-001", ... },
  { "id": "TASK-002", ... }
]
```

- `id` 는 파일 내에서 유일해야 한다
- 새 태스크의 번호는 기존 최대값 + 1 (자릿수는 3자리 이상 유지)
- 이 파일은 여러 사람·세션이 함께 쓰므로, 편집 전에 항상 최신 상태를 읽는다
  (→ `data-antipatterns.md` §1: `head`/`sed` 로 자르지 말고 `jq` 를 쓴다)

### 검증

```bash
python3 scripts/validate_tasks.py
```

스키마·WRU 임계·ID 유일성·순환 의존을 확인한다. 태스크를 만드는 두 경로
(`/wf-task-new`, `/wf-tasks-from-doc`)가 모두 이것을 통과해야 커밋한다.

## 6. 태스크는 어떻게 만들어지나

| 방법 | 언제 |
|---|---|
| `/wf-tasks-from-doc <문서>` | 요구사항 문서의 `## 1-2. 태스크 분리` 표에서 일괄 생성 |
| `/wf-task-new "설명"` | 문서 없이 한 건만 급히 |

둘 다 `task-authoring` 스킬의 같은 WRU 기준을 쓴다. 기능이 여러 태스크로 쪼개진다면
`/wf-feature` 로 문서를 먼저 쓰는 편이 낫다 — 왜 그렇게 쪼갰는지가 남는다.
