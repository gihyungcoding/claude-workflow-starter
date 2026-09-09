# 프로젝트 가이드

<!--
  이 파일은 매 요청마다 컨텍스트에 주입된다. 짧게 유지한다.
  상세는 .claude/skills/ 와 docs/workflow/ 로 위임하고, 여기에는 "어디를 봐야 하는지"만 둔다.
  200줄을 넘으면 무언가를 스킬로 옮길 때다.
-->

## 이 프로젝트에 대해

<!-- TODO: 신규 프로젝트에 맞게 채운다 -->
- **무엇**: (프로젝트 한 줄 설명)
- **스택**: (예: Python 3.12 / FastAPI / PostgreSQL)
- **테스트**: (예: `pytest`)
- **린트**: (예: `ruff check`)
- **빌드**: (예: 없음)

Frontend 태스크의 `sub_categories` 에 쓸 수 있는 값: <!-- 예: admin, learner. 단일 앱이면 빈 배열 -->

<!-- 화면이 있는 프로젝트라면 채운다. 백엔드 전용이면 이 두 줄을 지운다. -->
- **UI 라이브러리**: (예: shadcn/ui — 근거 ADR-0002)
- **디자인 정본**: `docs/product/design.md` · `design-tokens.css` (`/wf-init` 2.5절에서 생성)
- **시안**: (Figma / Artifact 링크 / 없음 — 화면 명세는 feature 문서 §5)

---

## 문서 계층 (Foundation)

프로젝트 수준 문서. 태스크마다 바뀌지 않고 간헐적으로 갱신된다.

| 문서 | 답하는 것 | 누가 읽나 |
|---|---|---|
| `docs/product/product.md` | 무엇을 왜 만드는가 | 태스크 생성 |
| `docs/product/features/*.md` | 이번에 무엇을 만드는가. **§1-2 태스크 분리 표** | 태스크 추출 |
| `docs/architecture/architecture.md` | 시스템이 어떻게 구성되는가 | **Phase 1** |
| `docs/architecture/constraints.yaml` | 무엇을 어기면 안 되는가 (아키텍처 + 디자인) | **Phase 4** (`check_architecture.py`) |
| `docs/product/design.md` | 화면이 어떻게 보이는가·왜 그런가 | **Phase 1** (Frontend), **Phase 4** |
| `docs/product/design-tokens.css` | 색·타이포·간격의 정본 | 화면 코드 전부 |
| `docs/decisions/ADR-*.md` | 왜 이 기술·패턴을 골랐는가 | **Phase 1** |

전체 흐름은 `docs/README.md` 를 본다. 부트스트랩은 `/wf-init`.

**요구사항 문서의 `## 1-2. 태스크 분리` 표가 `tasks.json` 이 된다.** 문서를 해석해
태스크를 상상하지 않는다 — 표만 읽는다.

---

## 개발 워크플로우

모든 개발 태스크는 6단계를 순서대로 거친다. 각 단계는 전용 스킬이 담당한다.

| Phase | 스킬 | 산출물 | 사람 승인 |
|---|---|---|---|
| 1 Plan | `wf-plan` | `04_plan/PLAN_<ID>.json` | — |
| 2a Scenario | `wf-scenario` | `05_scenario/SCENARIO_<ID>.md` | **HITL #1** |
| 2b Red | `wf-red` | `05_scenario/TEST_<ID>.json` | **HITL #2** |
| 3 Green | `wf-develop` | `06_dev/DEV_<ID>.json` | — |
| 4 Verify | `wf-verify` | `07_verify/VERIFY_<ID>.json` | **HITL #3** |
| 5 Reflect | `wf-reflect` | `08_reflect/REFLECT_<ID>.json` | **HITL #4** |
| Ship | `/wf-ship` | PR | 머지는 사람이 |

전체 흐름·게이트·상태 전이는 `wf-orchestrator` 스킬이 관장한다.
단계를 건너뛰거나 순서를 바꾸지 않는다.

### 브랜치

| 브랜치 | 분기 | 머지 대상 |
|---|---|---|
| `feature/task-NNN-slug` | 기준 브랜치 | 기준 브랜치 |

기준 브랜치는 `git config workflow.baseBranch` 로 정한다 (미설정 시 `develop` → `main` 순으로 탐색).

<!-- TODO: git-flow 를 쓴다면 `git config workflow.baseBranch develop` 을 실행하고,
     release/hotfix 브랜치 규약이 정해지면 여기에 추가한다 -->

**feature 브랜치는 항상 기준 브랜치에서 갈라낸다.** 다른 태스크 브랜치 위에서 시작하면
그 태스크의 미완성 커밋이 딸려온다.

### 진입점

| 상황 | 명령 |
|---|---|
| 프로젝트를 막 시작했다 | `/wf-init` |
| 새 기능의 요구사항을 쓴다 | `/wf-feature <이름>` |
| 문서에서 태스크를 만든다 | `/wf-tasks-from-doc <경로>` |
| 태스크 하나만 급히 만든다 | `/wf-task-new "설명"` |
| 기술 결정을 기록한다 | `/wf-adr "<결정>"` |
| 새 태스크 시작 | `/wf-start <TASK-ID>` |
| 중단한 태스크 이어가기 | `/wf-resume <TASK-ID>` |
| 전체 현황 보기 | `/wf-status` |
| 머지 준비 (PR 생성) | `/wf-ship` |
| 지금 상태를 체크포인트로 저장 | `/wf-checkpoint` |

---

## 절대 규칙

1. **HITL 승인을 대신하지 않는다.** `human_review.approved` 같은 필드는 `AskUserQuestion`
   응답을 받은 뒤에만 쓴다. 스스로 승인 처리하는 것은 워크플로우 위반이다.
2. **EXIT GATE를 통과하지 않고 다음 Phase로 가지 않는다.** 각 스킬 상단에 조건이 있다.
3. **체크포인트는 저장 즉시 커밋한다.** untracked 파일은 세션이 끊기면 복구되지 않는다.
4. **산출물 경로를 지어내지 않는다.** `docs/workflow/artifact-paths.md` 의 화이트리스트만 쓴다.
5. **Memory Bank는 저장소 루트의 `memory-bank/`.** `workflow_design/` 아래에 만들지 않는다.
6. **테스트를 먼저 실패시킨다(Red).** 구현부터 쓰고 테스트를 맞추는 순서는 금지다.
7. **아키텍처 제약을 어기지 않는다.** `constraints.yaml` 의 `severity: error` 위반은
   Phase 4에서 FAIL이다. 어겨야 할 이유가 있으면 제약을 먼저 고친다(ADR과 함께).
8. **승인 이후 코드를 고치지 않는다.** Phase 4 승인은 특정 커밋에 대한 것이다.
   고쳐야 하면 Phase 4를 다시 거친다 — `/wf-ship` 이 대조해서 막는다.
9. **머지·푸시·배포를 대신 실행하지 않는다.** 준비하고 명령을 제시하되 사람이 실행한다.

---

## 참조 문서

세부 규격은 아래에 있다. 필요할 때 읽고, 미리 읽지 않는다.

| 문서 | 언제 읽나 |
|---|---|
| `docs/workflow/artifact-paths.md` | 파일을 저장하기 전 |
| `docs/workflow/checkpoint-template.md` | 체크포인트를 쓸 때 |
| `docs/workflow/hitl-protocol.md` | 사람의 승인을 받을 때 |
| `docs/workflow/memory-bank-spec.md` | 세션을 복구하거나 상태를 갱신할 때 |
| `docs/workflow/task-schema.md` | 태스크를 만들거나 읽을 때 |
| `docs/workflow/reject-state-machine.md` | **거절이 발생했을 때만** |
| `docs/workflow/data-antipatterns.md` | JSON 산출물을 다루다 막혔을 때 |
| `docs/README.md` | 기능을 어디서 시작할지 모를 때 |
| `docs/architecture/architecture.md` | **Phase 1에서 설계할 때** |
| `docs/product/design.md` | **Frontend 태스크의 Phase 1·4** |
| `docs/decisions/README.md` | 이미 내려진 결정을 확인할 때 |

---

## 태스크 ID

```
TASK-001, TASK-0042, TASK-1207      정규식: ^TASK-\d{3,}$
```

한 가지 형식만 쓴다. 자릿수를 보존한다 (`TASK-121` ≠ `TASK-0121`).
`TASK-task-001` 같은 이중접두는 훅이 차단한다.

---

## 커밋

```
<type>(<scope>): <subject>
```

- type: `feat` `fix` `docs` `style` `refactor` `test` `chore`
- subject: 50자 이내, 명령형, 마침표 없음, **한국어**
- 태스크 참조는 footer에: `Refs: TASK-001`
- 워크플로우 산출물 커밋은 `chore(memory-bank):` 또는 `chore(workflow):` 를 쓴다

한 커밋은 한 목적만 담는다.
