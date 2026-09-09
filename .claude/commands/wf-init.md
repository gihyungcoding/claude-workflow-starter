---
description: 신규 프로젝트 부트스트랩 — 프로덕트 정의 → 아키텍처 → 첫 ADR
---

Foundation 문서를 순서대로 만든다. 이미 있는 것은 건너뛴다.

## 0. 현재 상태 확인

```bash
ls docs/product/product.md docs/architecture/architecture.md docs/decisions/ADR-*.md 2>/dev/null
grep -c "TODO" docs/product/product.md docs/architecture/architecture.md 2>/dev/null
```

TODO 가 남아 있으면 미완성으로 본다. 어디까지 되어 있는지 사용자에게 먼저 알린다.

```
Foundation 상태

  product.md        미작성 (TODO 12개)
  architecture.md   미작성 (TODO 8개)
  ADR               1건 (ADR-0001, 형식 예시)
  CLAUDE.md         TODO 3곳
```

## 1. 프로덕트 정의

`product-definition` 스킬로 `docs/product/product.md` 를 채운다.

**한 번에 다 묻지 않는다.** 섹션 단위로 물어보고 확인을 받으며 진행한다:
한 문장 → 문제 → 사용자 → 범위(특히 하지 않는 것) → 성공 기준 → 제약 → 열린 질문.

사용자가 "나중에"라고 하면 그 섹션에 TODO 를 남기고 넘어간다. 막지 않는다.

완료 후 `CLAUDE.md` 의 `sub_categories` 목록을 여기서 정한 역할로 채운다.

## 2. 아키텍처

`architecture-doc` 스킬로 `docs/architecture/architecture.md` 를 채운다.

기존 코드가 있으면 **먼저 읽고 현재 구조를 파악한 뒤** 쓴다 — 이상을 쓰고 현실과
다른 채로 두면 Phase 1이 잘못된 기준으로 설계한다.

```bash
ls -d src/*/ app/*/ lib/*/ 2>/dev/null
```

빈 저장소라면 사용자와 구조를 정하면서 쓴다.

`## 3. 의존 방향` 에서 "금지"로 적은 것 중 검사 가능한 것을 `constraints.yaml` 로 옮기고,
**실제로 걸리는지 확인한다**:

```bash
python3 scripts/check_architecture.py
```

**빈 저장소에서는 `?` 와 「검사 대상 없음」이 정상이다** — 아직 코드가 없으니 glob 이
매칭할 파일도 없다. 여기서 "통과"라고 읽지 않는다. 제약이 실제로 동작하는지는
**첫 구현 태스크의 Phase 1 에서 다시 확인**한다. 문서에 `**/controller/**` 라고 썼는데
코드가 `**/api/**` 로 만들어지는 일이 흔하다.

### 데이터 저장소를 정했으면 — 테스트는 무엇으로 도는가

프로덕션 DB 를 정하는 자리에서 **테스트 DB 전략도 함께 정한다.** 나중으로 미루면
프로젝트 골격을 만든 직후 첫 테스트가 연결 실패로 죽는다.

특히 **DB 전용 기능을 쓰기로 한 ADR 이 있으면 그 검증 가능성이 걸린다** —
PostgreSQL 의 `ON CONFLICT ... WHERE` 같은 것은 H2 로 검증되지 않는다.

| 선택지 | 언제 |
|---|---|
| 실제 DB (Docker/Testcontainers) | DB 전용 기능에 의존하는 ADR 이 있다 |
| 인메모리 (H2 등) 호환 모드 | Docker 를 쓸 수 없다 — **전환 조건을 ADR 에 적는다** |
| 둘 다 (단위=인메모리, 통합=실제) | 테스트가 느려지기 시작하면 |

두 번째를 고르면 **무엇이 검증되지 않는지**와 **언제 첫 번째로 옮길지**를 ADR 에
명시한다. 적지 않으면 영원히 인메모리로 남는다.

## 2.5. 프론트엔드가 있나

**화면이 있는 프로젝트인지 먼저 확인한다.** 백엔드 전용이면 이 단계를 건너뛴다.

```
이 프로젝트에 사용자가 보는 화면이 있나요?
```

있다면 이어서 묻는다:

```
UI 라이브러리를 정하셨나요?

  정했다        → 무엇인지 알려주세요 (CLAUDE.md 에 기록합니다)
  아직이다      → 지금 정하는 걸 권합니다. ADR 로 남기죠
  직접 만든다   → 디자인 시스템을 코드로 관리한다는 뜻입니다. 이것도 ADR 감입니다
```

### 왜 먼저 정하나

시안이 없는 프로젝트에서 UI 라이브러리는 **디자인 결정의 대부분을 대신 내려준다.**
버튼·입력·모달·테이블이 이미 있고 간격·색·타이포도 정해져 있어서, 남는 결정은
"무엇을 보여줄지"와 "어떤 상태가 있는지"뿐이다 — 그건 기획이지 디자인이 아니다.

이걸 정하지 않고 화면 작업을 시작하면 화면마다 간격과 색이 달라진다. 되돌리는 비용이
크므로 첫 프론트엔드 태스크 **전에** 정한다.

정했으면 `CLAUDE.md` 의 스택에 함께 적고, 3단계에서 ADR 로 남긴다.

## 3. 첫 ADR

`adr` 스킬로 이 프로젝트의 첫 실질적 결정을 기록한다.

2단계에서 구조를 정하며 내린 결정이 있으면 그것부터 쓴다 (계층 구조, 상태 관리 선택,
데이터베이스 선택 등). 사용자에게 "지금까지 정한 것 중 나중에 '왜 그랬지?'라고 물을 만한
게 있나요?"라고 묻는다.

**2.5단계에서 UI 라이브러리를 정했다면 그것을 첫 ADR 로 쓴다.** 되돌리기 비싼 결정이고
이후 모든 화면 작업이 이 결정을 따르므로, 왜 골랐는지가 남아야 한다.
검토한 선택지에 실제로 비교한 것을 쓴다 — 이름만 나열하지 않는다.

`ADR-0001` 은 ADR 형식 자체에 대한 결정이므로 그대로 두고 `ADR-0002` 부터 쓴다.

## 4. CLAUDE.md 채우기

**사용자가 미리 채워두기를 기대하지 않는다.** 여기서 채운다.

```bash
grep -n "TODO" CLAUDE.md
```

### 먼저 탐지한다

물어보기 전에 저장소에서 찾을 수 있는 것은 찾는다.

```bash
ls package.json pyproject.toml setup.py Cargo.toml go.mod pom.xml build.gradle 2>/dev/null
cat package.json 2>/dev/null | jq -r '.scripts | to_entries[] | "\(.key): \(.value)"' 2>/dev/null
grep -A5 '\[tool.pytest' pyproject.toml 2>/dev/null
ls Makefile 2>/dev/null && grep -E '^[a-z-]+:' Makefile
```

찾은 것을 제시하고 확인만 받는다:

```
package.json 에서 찾았습니다.

  테스트   npm test        (vitest run)
  린트     npm run lint    (eslint .)
  빌드     npm run build   (vite build)

이대로 CLAUDE.md 에 넣을까요?
```

### 채울 항목

| 항목 | 어디서 |
|---|---|
| 프로젝트 한 줄 설명 | 1단계 `product.md` §1 |
| 스택 | 탐지 결과 |
| **테스트·린트·빌드 명령** | 탐지 후 확인 — Phase 3/4 가 실제로 실행하므로 틀리면 그때 막힌다 |
| `sub_categories` | 1단계에서 정한 사용자 역할 |

빈 저장소라 탐지할 것이 없으면 **다음 절로 간다.** TODO 로 남기고 넘어가지 않는다 —
그 TODO 는 Phase 3 의 "린트 error 0" 게이트를 무력화하고, 첫 태스크 한복판에서
발견된다.

## 4.5. 프로젝트 골격

**여기서 확인하지 않으면 첫 태스크의 Phase 1 에서 막힌다.**
`CLAUDE.md` 에 적은 명령이 실제로 도는지 지금 돌려본다.

```bash
<CLAUDE.md 의 테스트 명령>     # 실제로 실행한다
```

돌지 않으면 골격이 없는 것이다. **스캐폴딩을 안내하고 사용자가 실행하게 한다.**

| 스택 | 예 |
|---|---|
| Spring Boot | https://start.spring.io 또는 `spring init` |
| React (Vite) | `npm create vite@latest frontend -- --template react-ts` |
| FastAPI | `uv init` + `uv add fastapi` |

### 부트스트랩은 워크플로우 태스크가 아니다

**태스크로 만들지 않는다.** 두 선택지 모두 부적절하다:

- 첫 태스크에 포함 → 그 태스크의 완료 조건과 무관한 변경이 PR 에 섞인다
- 별도 태스크 → Red 테스트를 쓸 수 없어 WRU 조건을 만족하지 못한다
  (`docs/workflow/task-schema.md` §1)

환경 준비이므로 **기준 브랜치에서 직접 하고 커밋한다.** feature 브랜치를 만든 뒤에
알게 되면 되돌아와야 한다.

골격을 만든 뒤 **테스트·린트·빌드 명령을 다시 돌려 `CLAUDE.md` 를 확정한다.**
이 시점에 린터도 함께 넣는 편이 거의 항상 낫다 — 코드가 적을 때 포매터를 도입하면
변경이 작고, 나중에 넣으면 전체 파일이 한 번에 재포맷되어 리뷰가 불가능해진다.

## 5. 마무리

```bash
python3 scripts/rebuild_doc_index.py
python3 scripts/hooks/check_artifact_paths.py --all
git add docs/ CLAUDE.md && git commit -m "docs: Foundation 문서 초기 작성"
```

```
Foundation 준비 완료

  product.md       ✓  사용자 3역할, 범위 외 4항목
  architecture.md  ✓  3계층, 제약 2건
  constraints.yaml ✓  ARCH-001(error), ARCH-002(warn) — 검증 통과
  ADR              2건
  CLAUDE.md        ✓  pytest / ruff check  (실행 확인함)
  프로젝트 골격     ✓  pytest → 0 tests, exit 0

다음: /wf-feature <기능이름> 으로 첫 기능 요구사항을 작성하세요.
```

**첫 기능을 제안할 때는 가장 복잡한 것을 고르지 않는다.** 선행 의존이 없고 판정
로직 중심인 것 — 조회·목록·검증 같은 것 — 을 권한다. 첫 태스크는 워크플로우에
익숙해지는 자리이기도 하다.

## 이미 다 되어 있으면

무엇이 있는지 보여주고, 갱신할 것이 있는지 묻는다. 덮어쓰지 않는다.
