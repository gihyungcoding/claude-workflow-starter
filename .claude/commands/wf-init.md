---
description: 신규 프로젝트 부트스트랩 — 프로덕트 정의 → 아키텍처 → 첫 ADR
---

Foundation 문서를 순서대로 만든다. 이미 있는 것은 건너뛴다.

## 0. 현재 상태 확인

```bash
ls docs/product/product.md docs/architecture/architecture.md docs/architecture/conventions.md docs/decisions/ADR-*.md 2>/dev/null
grep -c "TODO" docs/product/product.md docs/architecture/architecture.md 2>/dev/null
```

TODO 가 남아 있으면 미완성으로 본다. 어디까지 되어 있는지 사용자에게 먼저 알린다.

```
Foundation 상태

  product.md        미작성 (TODO 12개)
  architecture.md   미작성 (TODO 8개)
  conventions.md    없음 (코딩 규칙 — 2.7)
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

### 그다음 — 방향까지만 정한다

라이브러리가 대신 내려주지 못하는 것이 색·타이포·의미 매핑이다. **여기서 정하지 않으면
라이브러리 기본값이 그대로 제품의 얼굴이 된다** — 주제와 무관하게 어느 프로젝트에서나
같은 화면이 나오는 이유가 이것이고, 흔히 "AI 티가 난다"고 하는 것의 정체다.

`frontend-design` 스킬을 로드하고 `product.md` §1~3 을 입력으로 삼아
`docs/product/design.md` 를 만든다.

**단, 지금 채울 수 있는 것만 채운다.**

| 절 | 지금 | 왜 |
|---|---|---|
| §1 주제·청중·주된 일 | ✅ | `product.md` 에서 나온다 |
| §2 방향 (대담함을 어디에) | ✅ | 주된 일에서 도출된다 |
| §3 UI 라이브러리 | ✅ | 스택 결정이다 |
| §6 하지 않을 것 | ✅ | 기본값 회피 목록. 화면과 무관하다 |
| §7 품질 하한선 | ✅ | 보편 기준이다 |
| **§4 토큰 값** | ⬜ TODO | **무엇이 담기는지 알아야 한다** |
| **§5 의미 매핑** | ⬜ TODO | **상태 목록이 있어야 한다 — 기능에서 나온다** |

**§4·§5 와 `design-tokens.css` 는 첫 기능 문서(§2 화면 설계) 이후에 채운다.**
첫 화면 요청을 `/wf-plan` 으로 진행하면 `ui-mockup` 시안이 토큰과 배지(의미→색) 표의 초안을 만들고,
확정 뒤 Dispatch 의 `design` 작업이 그것을 §4·§5 로 옮긴다.
지금은 화면을 하나도 안 봤다. 색을 먼저 정하고 화면을 맞추면 순서가 거꾸로다 —
무엇을 담을지 → 어떻게 배치할지 → 그다음 색이다.

`constraints.yaml` 의 `DESIGN-*` 도 그때 켠다. 토큰이 없으면 옮길 것도 없다.
기존 화면이 이미 위반해서 `warn` 으로 켜야 한다면 **`promote_after` 에 그 위반을 해소할
태스크를 적는다** — 적지 않은 임시 `warn` 은 영원히 `warn` 으로 남는다.

**서체 방향은 지금 정해도 된다** (언어·도메인에서 나온다). 다만 **한국어 UI 라면
한글 글리프가 있는 서체인지 반드시 확인한다** — Inter·Playfair Display·Space Grotesk
처럼 흔히 추천되는 서체는 한글이 없어 시스템 폰트로 폴백되고, 그러면 정한 것이
화면에 나타나지 않는다.

## 2.7. 코딩 규칙 — 코드 없이 정할 수 있는 것은 지금

**`conventions` 스킬**로 `docs/architecture/conventions.md` 를 만든다. 코드가 없으니 "주변 코드를 따른다"는 아무것도 정하지 않는다 —
그대로 두면 첫 태스크가 쓴 코드가 곧 컨벤션이 된다. 시험 실행에서 10건 중 7건(테스트 DB·포매터·DTO 위치·입력 검증·
에러 형식·테스트 이름·제약 경로)이 코드 없이 정할 수 있었는데 나중에 정해 이전 태스크·재정렬·두 번째 PR 이 생겼다.

- 항목은 스킬의 `references/items.md`, 추천값은 `stacks/<스택>.md`(Spring Boot·React(Vite)·FastAPI). 스택 관례는 묻지 않고 정하고, 갈리는 것만 묻는다
- **테스트 DB 는 위 「테스트는 무엇으로 도는가」의 결정을 `C-TESTDB` 로 옮긴다** — 운영과 다르면 ADR 과 전환할 태스크까지
- 제약은 `constraints.yaml` 에 **`error` 로** 넣는다(빈 저장소에는 어길 코드가 없다). 경로 확인은 4.5 기준 구현 뒤
- 되돌리기 어려운 결정(테스트 DB·검증 방식)은 3단계 ADR 후보로 넘긴다

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
| FastAPI | `uv init` + `uv add fastapi` (uv 가 없으면 `python -m venv` + `requirements*.txt`, Docker 만 있으면 compose 의 `app` 서비스 — 명령은 `docker compose run --rm -T app …`, 비대화형이라 `-T`) |

### 부트스트랩은 워크플로우 태스크가 아니다

**태스크로 만들지 않는다.** 두 선택지 모두 부적절하다:

- 첫 태스크에 포함 → 그 태스크의 완료 조건과 무관한 변경이 PR 에 섞인다
- 별도 태스크 → Red 테스트를 쓸 수 없어 WRU 조건을 만족하지 못한다
  (`docs/workflow/task-schema.md` §1)

환경 준비이므로 **기준 브랜치에서 직접 하고 커밋한다.** feature 브랜치를 만든 뒤에
알게 되면 되돌아와야 한다.

골격을 만든 뒤 **테스트·린트·빌드 명령을 다시 돌려 `CLAUDE.md` 를 확정한다.**
린터·포매터는 **지금 넣는다**(권고가 아니라 게이트가 본다) — 코드가 적을 때 넣으면 변경이 작고, 나중에 넣으면 전체 파일이
한 번에 재포맷되어 리뷰가 불가능해진다(시험 실행: 첫 Red 뒤에 넣어 15개 파일 재정렬).

### 기준 구현 — 규칙을 첫 코드로 증명한다

골격만으로는 2.7 의 규칙이 코드에서 어떤 모양인지 아무도 모른다. **규칙을 모두 지키는 작은 수직 조각 하나**를 지금
의도적으로 만든다 — 이후 태스크는 "주변 코드"보다 이것을 먼저 본뜬다. 담을 것은 `conventions` 스킬 `stacks/<스택>.md`
「기준 구현」(입력이 있는 엔드포인트 하나 + 검증 실패가 정한 에러 형식으로 + 층별 테스트, 프론트엔드가 있으면 토큰만 쓰는 화면 하나). 숫자·식별자 입력이 있으면 경계 테스트에 비 ASCII 숫자 하나를 넣는다 — 기준 구현은 이후 모든 태스크가 본뜨므로 여기서의 실수가 퍼진다.

1. 결정한 테스트 DB 로 테스트가 실제로 돈다
2. 린트·테스트·빌드 통과 — 린트 명령은 여기서 `CLAUDE.md` 에 적는다(실행 파일이 골격과 함께 생긴다)
3. `python3 scripts/check_architecture.py --json` — 위반 0, 검사 대상 없음(`no_target`) 0(금지 경로 제약은 파일이 없는 것이 통과). 제약마다 일부러 어겨 걸리는지 확인하고 되돌린다 — 줄 정규식은 어긴 줄, 금지 경로는 금지된 이름의 파일을 잠깐
4. `AskUserQuestion` 으로 기준 파일과 규칙 표를 보여 주고 확인받는다 → `conventions.md` 상태를 `기준 구현 확인`, 「기준 파일」에 경로
5. `python3 scripts/check_conventions.py` 통과 — `/wf-start` 가 첫 태스크 전에 같은 게이트를 돈다

기준 구현도 부트스트랩이다 — 태스크로 만들지 않고 기준 브랜치에서 커밋한다(위 「부트스트랩은 워크플로우 태스크가 아니다」).

## 5. 마무리

```bash
python3 scripts/rebuild_doc_index.py
python3 scripts/hooks/check_artifact_paths.py --all
python3 scripts/check_conventions.py          # 첫 태스크 전 게이트 — /wf-start 도 돈다
git add docs/ CLAUDE.md && git commit -m "docs: Foundation 문서 초기 작성"
```

```
Foundation 준비 완료

  product.md       ✓  사용자 3역할, 범위 외 4항목
  architecture.md  ✓  3계층, 제약 2건
  constraints.yaml ✓  ARCH-001(error), TEST-001(error) — 검증 통과, 검사 대상 없음 0
  conventions.md   ✓  10항목 정함 · 기준 구현 확인 (기준 파일 6개) — check_conventions 통과
  ADR              2건
  CLAUDE.md        ✓  pytest / ruff check  (실행 확인함)
  프로젝트 골격     ✓  기준 구현 포함 — pytest 4 passed, ruff 0
  design.md        ✓  방향까지 (§4 토큰·§5 의미 매핑은 첫 기능 이후)

다음: /wf-plan "<만들 것>" 으로 첫 기능을 계획하세요 (문서부터 쓰려면 /wf-feature <기능이름>).
```

**첫 기능을 제안할 때는 가장 복잡한 것을 고르지 않는다.** 선행 의존이 없고 판정
로직 중심인 것 — 조회·목록·검증 같은 것 — 을 권한다. 첫 태스크는 워크플로우에
익숙해지는 자리이기도 하다.

## 이미 다 되어 있으면

무엇이 있는지 보여주고, 갱신할 것이 있는지 묻는다. 덮어쓰지 않는다.
