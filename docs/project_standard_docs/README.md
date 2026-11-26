# 프로젝트 표준 문서 — 확장 지점 (현재 비활성)

이 디렉터리는 **코딩 표준 문서**(네이밍, 계층 구조, 에러 처리, 테스트 패턴 등)를 두는 자리다.
지금은 비어 있고, 워크플로우는 이것 없이 동작한다.

---

## 지금 비어 있는 이유

원본 저장소는 여기에 **323개 문서 / 59,747줄 / 규칙 6,101개**를 갖고 있었다. 그 규모에서는
규칙을 통째로 컨텍스트에 넣을 수 없어서, 별도 파이프라인이 필요했다:

```
.mdc 문서 323개
   ↓ generate_context_project.py
context.project.json (8.3MB)
   ↓ split_rules_by_scope.py
rules_by_scope/ (264 파일)
   ↓ build_scope_index.py
_scope_index.pkl (BM25 + 임베딩 하이브리드 인덱스)
   ↓ extract_scope_rules.py
태스크에 관련된 규칙만 추출
```

스크립트 5개, 중간 산출물 9.5MB, 재생성 트리거는 수동. 규칙 수천 개를 다루려면 필요한
장치지만, **규칙이 수십 개인 신규 프로젝트에는 과하다.** 그 규모에서는 Skills 의
progressive disclosure(필요할 때만 참조 문서를 읽는 방식)로 충분하다.

그래서 이식하지 않았고, 대신 활성화 조건과 방법만 남긴다.

**작은 규모의 시작점은 `docs/architecture/conventions.md`** 다(`conventions` 스킬이 `/wf-init` 에서
만든다). 배치·이름·에러 형식·입력 검증·테스트 규칙을 한 문서에 두고, 기계로 잡을 수 있는 것은
린트 설정·`constraints.yaml` 로 옮긴다. 규칙이 수백 개로 커져 한 문서에 담기지 않을 때 이 디렉터리의
방식을 검토한다 — 아래 「언제 파이프라인을 켤 것인가」가 그 기준이다.

---

## 지금은 규칙을 어디에 쓰나

| 규칙의 성격 | 어디에 |
|---|---|
| 항상 지켜야 하는 소수의 규칙 | `CLAUDE.md` (매 요청 주입됨 — 짧게 유지) |
| 특정 작업에서만 필요한 규칙 | `.claude/skills/<name>/SKILL.md` 또는 그 `references/` |
| 워크플로우 자체의 규격 | `docs/workflow/` |

규칙이 늘어나면 먼저 **스킬로 쪼갠다.** 예를 들어 API 설계 규칙이 많아지면
`.claude/skills/api-conventions/` 를 만들고, `description` 에 "API 엔드포인트를 만들거나
수정할 때" 같은 트리거를 넣는다. 그러면 관련 작업에서만 로드된다.

---

## 언제 파이프라인을 켤 것인가

아래 중 **두 개 이상**에 해당하면 도입을 검토한다.

- 표준 문서가 **50개를 넘는다**
- 규칙(MUST/SHOULD/FORBIDDEN 항목)이 **200개를 넘는다**
- 스택이 여러 개다 (백엔드 + 프론트엔드 2종 이상)
- "이 태스크에 어떤 규칙이 적용되는지" 판단하는 데 매번 시간이 걸린다
- 규칙 문서를 컨텍스트에 넣다가 잘리는 일이 생긴다

하나만 해당하면 스킬 분리로 해결되는 경우가 대부분이다.

---

## 켤 때의 구조

원본 저장소의 설계를 참고할 수 있다. 핵심은 `_spec.yaml` 을 **단일 스위치**로 삼아
스택이 바뀌면 디렉터리만 갈아끼우는 것이다.

```
docs/project_standard_docs/
├── backend/
│   ├── _spec.yaml              # implementation: spring-java / rule_priority 순서
│   ├── _abstract/              # 스택 무관 원칙 (API 응답 형식, HTTP 상태코드 등)
│   └── spring-java/            # 구현체별 규칙
├── database/
│   ├── _spec.yaml
│   └── mysql/
└── frontend/
    └── <app>/
        ├── _spec.yaml
        ├── _abstract/
        ├── react-typescript/
        └── ui_design_system/
```

`_spec.yaml` 예시:

```yaml
implementation: spring-java     # 어느 하위 디렉터리를 쓸지 결정하는 단일 키
stack:
  framework: Spring Boot
  language: Java
  version: "21"
rule_priority:                  # 로딩 순서 — 구체적인 것이 먼저
  - spring-java
  - _abstract
```

### 원본 설계에서 고쳐야 할 점

이식할 때 그대로 가져오지 말아야 할 것들이다. 원본에서 실제로 문제가 됐다.

1. **`globs` 를 실제로 쓰거나, 쓰지 않는다고 문서에 명시한다.** 원본은 323개 문서 전부
   `globs` 가 없는데 규칙 문서에는 "globs 로 자동 로드된다"고 적혀 있었다.
2. **`_spec.yaml` 이 존재하지 않는 폴백 디렉터리를 선언하지 않게 한다.** 원본의
   `database/_spec.yaml` 은 `_abstract` 를 폴백으로 걸어뒀는데 그 디렉터리가 없었다.
3. **`implementation` 값을 하나로 통일한다.** 원본은 `ui_design_system` 이
   `ui_design_system_admin`, `ui_design_system_anchor` 등 5가지로 갈라졌다.
4. **`scope` 같은 분류 필드에 자유 문자열을 허용하지 않는다.** 원본은 canonical 18개 값을
   정해뒀지만 실제로는 한글 자유 문자열 100종 이상이 들어갔고, scope 기반 분류가 무너졌다.
5. **규칙 ID 유일성을 CI 로 강제한다.** 원본은 규약만 있고 검사가 없어서 ID 충돌이 남았다.
6. **앱별로 문서를 포크하지 않는다.** 원본은 teacher/supervisor 규칙 126개가 경로와 ID
   토큰만 다른 사실상 같은 문서였다. 공통 원칙을 `_abstract` 로 올리고 차이만 남긴다.
