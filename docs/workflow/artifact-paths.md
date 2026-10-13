# 산출물 경로 규약

모든 Phase 산출물과 체크포인트의 저장 위치를 정의한다. **이 문서가 경로의 유일한 정본**이며,
`scripts/hooks/check_artifact_paths.py` 가 화이트리스트 방식으로 이 규약을 강제한다.

> **왜 화이트리스트인가**
> 원본 저장소는 블랙리스트(금지 패턴 목록) 방식이었다. 그 결과 `05_chain_data_plan/`,
> `06_chain_data_context_dev/`, `06_chain_data_dev/` 처럼 **아무도 금지한 적 없는 오타 디렉터리**가
> 각각 파일 1개씩 품은 채 살아남았고, 정본 디렉터리와 동시에 존재해 산출물 게이트가
> "후보 2개 이상"으로 오판하는 원인이 되었다. 허용 목록에 없으면 거부한다.

---

## 1. 태스크 ID 형식 — 단일 형식만 허용

```
TASK-<숫자 3자리 이상>        예: TASK-001, TASK-0042, TASK-1207
```

- 정규식: `^TASK-\d{3,}$`
- **대소문자 혼용 금지.** 원본 저장소는 `TASK-NNN`(169건)과 `task-NNNN`(164건)이 공존해
  게이트가 "ID 표기 흡수" 로직을 따로 들고 있어야 했다. 여기서는 한 형식만 쓴다.
- **이중접두 금지.** `TASK-TASK-001`, `TASK-task-001` 모두 거부. 원본에서 이 패턴이 167건 생겼다.
- **자릿수를 보존한다.** `TASK-121` 과 `TASK-0121` 은 서로 다른 태스크다. 정규화하지 않는다.

---

## 2. 워크플로우 산출물 — `workflow_design/`

```
workflow_design/
├── 02_tasks/
│   └── tasks.json                          # 태스크 배열 (단일 파일)
├── 04_plan/
│   └── PLAN_<TASK-ID>.json                 # Phase 1
├── 05_scenario/
│   ├── SCENARIO_<TASK-ID>.md               # Phase 2a — SoT (사람이 편집)
│   ├── SCENARIO_<TASK-ID>.json             # Phase 2a — 파생물 (직접 편집 금지)
│   ├── TEST_<TASK-ID>.json                 # Phase 2b — 파생물, scenario.json 을 supersede
│   └── validator/
│       └── VALIDATION_<TASK-ID>.json       # 독립검증자 응답 원본 (가공 금지)
├── 06_dev/
│   └── DEV_<TASK-ID>.json                  # Phase 3
├── 07_verify/
│   └── VERIFY_<TASK-ID>.json               # Phase 4
└── 08_reflect/
    └── REFLECT_<TASK-ID>.json              # Phase 5
```

**파일명에 슬러그를 붙이지 않는다.** 원본은 `CONTEXT_PLAN_TASK-019_store-ranking.json` 처럼
제목 슬러그를 붙였는데, 같은 태스크의 슬러그가 Phase마다 달라지면서 게이트가 glob으로
찾아야 했고 매칭 실패가 잦았다. `<TASK-ID>` 하나로 결정된다.

### 허용 디렉터리 목록 (이 외 `workflow_design/NN_*` 은 전부 거부)

`02_tasks` · `04_plan` · `05_scenario` · `06_dev` · `07_verify` · `08_reflect`

> 번호가 03, 그리고 01이 비어 있는 것은 원본의 PRD/매칭 단계(01_prd, 03_prd_to_tdd_case,
> 04_matching_output)를 이식하지 않았기 때문이다. 번호를 다시 매기지 않은 이유는 원본 저장소와
> 대조할 때 단계 대응이 바로 보이게 하기 위해서다. 새 단계가 필요하면 빈 번호를 쓴다.

---

## 3. 세션 복구 상태 — `memory-bank/`

```
<repo-root>/memory-bank/
├── index.md                                # 활성/완료 태스크 목록 (스크립트가 생성)
└── <TASK-ID>/
    ├── activeContext.md                    # 현재 상태 (YAML frontmatter + 본문)
    ├── progress.md                         # Phase 진행 표
    └── checkpoints/
        ├── phase1/  phase2a/  phase2b/  phase3/  phase4/  phase5/
        └── CP-<n.m>_<고정슬러그>.md
```

### ⚠️ 위치 원칙

**memory-bank 는 항상 저장소 루트에 있다. `workflow_design/` 아래가 아니다.**

```
<repo-root>/memory-bank/          ✅
workflow_design/memory-bank/      ❌ 훅이 차단
workflow_design/memory_bank/      ❌ 훅이 차단 (언더스코어도)
```

> 산출물 경로가 `workflow_design/` 기준 상대경로로 기술되다 보니, CWD가 `workflow_design/`인
> 세션에서 `mkdir -p memory-bank/...` 를 그대로 실행하면 잘못된 위치에 생긴다. 원본 저장소에
> 이렇게 새어 들어간 파일이 7개 있다. 쉘에서는 반드시 루트를 동적으로 구한다:

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
MEMORY_BANK_ROOT="$REPO_ROOT/memory-bank"
# 이후 모든 경로는 "$MEMORY_BANK_ROOT/..." — bare "memory-bank/..." 금지
```

### 체크포인트 파일명 — Phase 당 하나

자유 작명 금지. 아래 6개만 쓴다 (→ `checkpoint-template.md`).

| Phase | 파일 |
|---|---|
| 1 | `phase1/CP-1.3_context-plan.md` |
| 2a | `phase2a/CP-2.2_canonical-scenarios.md` |
| 2b | `phase2b/CP-2.5_red-code.md` |
| 3 | `phase3/CP-3.4_context-dev.md` |
| 4 | `phase4/CP-4.2_verification.md` |
| 5 | `phase5/CP-5.2_context-reflect.md` |

v1 의 나머지 13종(`CP-1.1`·`2.3`·`2.4`·`2.6`·`3.2`·`4.3`·`5.3` 등)과 `_retry<N>` 접미사는
**새로 쓰지 않는다.** 이미 만들어진 프로젝트의 파일이 걸리지 않도록 경로 검사가 허용만 한다.

> **원본 대비 변경 — CP-2.4 ID 충돌 해소**
> 원본은 `1003a`가 "CP-2.4 = 독립검증", `1003b`/마스터가 "CP-2.4 = Red 코드"로 같은 ID를 서로
> 다른 산출물에 쓰고 있었다. 여기서는 2a를 CP-2.1~2.4, 2b를 CP-2.5~2.6으로 나눠 충돌을 없앴다.
> 디렉터리도 `phase2a/`·`phase2b/`로 분리했다 (원본은 `phase2/`와 `phase2a/`가 태스크마다 달랐다).
>
> 슬러그 고정의 이유도 같다. 원본에는 `CP-4.2_verification-complete`(208건)과
> `CP-4.2_verification`(93건), `CP-3.2_tests-green`(226건)과 `CP-3.2_test-green`(31건)이 공존했다.

---

## 4. 커밋 규칙 — 저장 즉시 커밋

체크포인트와 Phase 산출물은 **저장 직후 같은 브랜치에 커밋한다.** 작업 트리에만 둔 채
다음 Phase로 넘어갈 수 없다.

- 체크포인트를 커밋하지 않으면 세션이 끊겼을 때 **복구 대상 자체가 사라진다.**
  Memory Bank의 존재 이유가 세션 복구인데 untracked 파일은 복구되지 않는다.
- `scripts/verify_workflow_artifacts.py` 는 작업 트리가 아니라 **git이 추적하는 파일**을 검사한다.

```bash
git add "$MEMORY_BANK_ROOT/$TASK_ID" workflow_design/
git commit -m "chore(memory-bank): $TASK_ID CP-<n.m> 체크포인트"
```

---

## 5. 이 규약이 잡지 못하는 것

훅은 **경로 문자열만** 본다. 판단하지 않는다.

- 파일 **내용**이 규약에 맞는지는 검사하지 않는다 (`PLAN_TASK-001.json` 안이 비어 있어도 통과)
- 태스크 ID가 `tasks.json` 에 실제로 존재하는지 확인하지 않는다
- 체크포인트가 해당 Phase에서 실제로 저장됐는지(순서)는 보지 않는다

내용 검증은 `scripts/verify_workflow_artifacts.py` 와 각 Phase의 EXIT GATE가 담당한다.
