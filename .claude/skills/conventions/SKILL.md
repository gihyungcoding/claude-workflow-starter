---
name: conventions
description: >-
  프로젝트 코딩 규칙(conventions.md)을 정하고 기준 구현으로 증명한다 — 테스트 DB·포매터·배치·에러 형식·입력 검증·
  테스트 이름처럼 코드 없이 정할 수 있는 것을 스택 추천값으로 묻고, 린트 설정·제약으로 옮긴다. Use when /wf-init 2.7·4.5,
  새 프로젝트에서 "코딩 컨벤션", "코드 규칙", "린트 설정", "테스트 DB" 를 정할 때, 회고가 conventions.md 변경을 제안했을 때.
---

# 코딩 규칙 — 정하고, 첫 코드로 증명한다

**코드가 없으면 관례를 배울 곳이 없다.** 그대로 두면 첫 태스크가 우연히 쓴 코드가 컨벤션이 되고 아무도 검토하지 않는다
(시험 실행: 10건 중 7건이 코드 없이 정할 수 있었는데 나중에 정해 이전 태스크·재정렬·두 번째 PR 이 생겼다 — `references/items.md`).
그래서 순서를 뒤집는다:

1. **정한다 (코드 없이)** — `/wf-init` 2.7. 항목마다 스택 추천값으로 묻는다 → `docs/architecture/conventions.md` · 제약 · 린트 설정
2. **증명한다 (코드 한 조각)** — `/wf-init` 4.5. 규칙을 모두 지키는 기준 구현을 의도적으로 만들고 사람이 한 번 확인
3. **붙잡는다 (코드가 있어야 아는 것)** — 태스크가 새 관례를 처음 만들면 `new_conventions` → HITL#3 → 회고 → 여기

| 파일 | 성격 |
|---|---|
| `docs/architecture/conventions.md` | 정본 — 표(게이트가 읽는다) + 기준 파일 + 결정 메모. 템플릿 `templates/conventions.md` |
| `docs/architecture/constraints.yaml` | 기계로 잡을 수 있는 규칙만 — `architecture-doc` 스킬 규칙대로 |
| 린트·포맷 설정 | 스택 파일의 조각 |

## MUST

1. **항목을 하나도 비우지 않는다** — 정할 수 없으면 `해당 없음 — <이유>`. TODO 가 남으면 게이트(`scripts/check_conventions.py`)가 첫 태스크를 막는다
2. **스택 추천값으로 묻는다** — `stacks/<스택>.md`. 묻는 방식은 `wf-plan/references/decision-protocol.md`:
   `mechanical`(스택 관례·이미 정한 것)은 묻지 않고 근거와 함께 기록, `taste` 는 추천안으로 정하고 목록으로 보여 줌, `user_challenge` 만 `AskUserQuestion`
3. **테스트 DB 는 운영과 같게** — 다르게 하려면 ADR 과 전환할 태스크(`promote_after`)를 적는다. "나중에 전환"만 적으면 전환하지 않는다.
   ADR 은 **스택 추천값에서 벗어날 때만** 쓴다(운영과 다른 테스트 DB, 추천과 다른 검증 방식 등). 추천값을 그대로 쓰면 결정 메모 한 줄이면 된다
4. **제약은 `error` 로 시작한다** — 빈 저장소에는 어길 코드가 없다. `warn` 으로 시작하면 `promote_after` 를 반드시 적는다
5. **기준 구현을 만든 뒤 제약 경로를 확인한다** — `check_architecture.py --json` 에 `no_target` 이 0(금지 경로 `forbidden_path` 는 파일이 없는 것이 통과라 예외). 빈 저장소에서 쓴 glob 은 실제 패키지와 어긋나기 쉽다
6. **태스크 번호를 파일 이름에 넣지 않는다** — 태스크는 끝나도 코드는 남는다

7. **제약 YAML 은 파서가 읽는 부분집합으로** — 매핑은 블록(`detect:` 아래 들여쓰기), 리스트는 인라인 `["a/**", "b/**"]`, 정규식은 큰따옴표 안에서 역슬래시를 두 번(`"^\\s*print\\("`). `constraints.yaml` 머리말에 규칙이 있다
8. **제약 id 접두사** — 배치·의존 `ARCH-`, 테스트 `TEST-`, 로깅 `LOG-`, 화면 `DESIGN-`. 새 종류가 필요하면 `architecture-doc` 스킬에
## FORBIDDEN

1. ❌ "주변 코드를 따른다"로 미루기 — 첫 태스크에는 주변 코드가 없다
2. ❌ 린터·포매터를 첫 태스크 뒤로 미루기 — 전체 파일이 한 번에 재정렬된다
3. ❌ 검사 칸을 비워 두기 — 무엇이 이 규칙을 지키는지(린트 규칙·제약 id·`리뷰`) 모르면 지켜지지 않는다
4. ❌ 코드가 있어야 아는 것을 미리 지어내기 — `references/items.md` 「코드가 있어야 아는 것」은 태스크가 만나면 기록한다

## 정하기 — `/wf-init` 2.7

1. `CLAUDE.md` 스택 줄과 `architecture.md` 를 읽고 스택 파일을 고른다(Spring Boot·React(Vite)·FastAPI). 없는 스택은 `references/items.md` 의 질문만
2. `templates/conventions.md` 를 `docs/architecture/conventions.md` 로 복사
3. 항목마다 분류 → 묻거나 추천값으로 정함 → 표의 결정·검사·상태(`정함`) + 결정 메모. 되돌리기 어려운 것(테스트 DB·검증 방식)은 `/wf-adr`
4. 검사 칸의 제약을 `constraints.yaml` 에 — `architecture-doc` 스킬의 "갱신할 때" 절차(일부러 어겨 걸리는지 확인)는 기준 구현 뒤에
5. 린트 명령은 **4.5 골격에서** `CLAUDE.md` 에 적는다(`uv`·`gradlew` 같은 실행 파일은 골격 뒤에 생긴다). 2.7 에서는 무엇을 쓸지만 정한다

## 증명하기 — `/wf-init` 4.5

1. 골격과 함께 린트 설정을 넣고 **통과**시킨다
2. 스택 파일 「기준 구현」을 만든다 — 규칙의 결정마다 그것을 보이는 코드가 적어도 한 군데
3. 결정한 테스트 DB 로 테스트가 실제로 돈다
4. `check_architecture.py --json` — 위반 0, `no_target` 0. 제약마다 일부러 어겨 걸리는지 확인하고 되돌린다 —
   줄 정규식은 어긴 줄을, 금지 경로(`forbidden_path`)는 금지된 이름의 파일을 잠깐 만들어 본다
5. `AskUserQuestion` — 기준 파일 목록과 규칙 표를 보여 주고 "이대로 첫 태스크부터 따르게 할까요?" → 상태를 `기준 구현 확인` 으로, `## 기준 파일` 에 경로
6. `python3 scripts/check_conventions.py` 통과 → 기준 브랜치에 커밋(부트스트랩은 태스크가 아니다 — `/wf-init` 4.5)

## 갱신하기 — 회고가 제안했을 때

`/wf-retro` 에서 승인된 `rule_proposals`(target `docs/architecture/conventions.md`)를 표에 행으로 더한다. 기계로 잡을 수 있으면 제약도.
기존 코드가 새 규칙을 어기면 제약은 `warn` + `promote_after`(고칠 태스크)로 시작한다.
