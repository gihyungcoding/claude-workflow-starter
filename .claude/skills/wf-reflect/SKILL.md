---
name: wf-reflect
description: >-
  Phase 5 — KPT 회고와 규칙 개선안을 쓰고 승인을 기다리지 않고 태스크를 닫는다. 사람 승인
  (HITL#4)은 /wf-retro 에서 여러 태스크의 회고를 모아 받는다. Use when Phase 5를 시작할 때,
  "회고", "KPT", "reflect", "태스크 마무리" 요청을 받을 때, Phase 4 검증이 승인됐을 때, 또는
  "회고 승인", "회고 검토", "/wf-retro" 요청을 받을 때.
---

# Phase 5 — Reflection

태스크를 닫는다. **다음 태스크가 더 나아지게 만드는 것**이 목적이지 기록을 남기는 것이 아니다.

## MUST

1. Keep 최소 1건, 개선 인사이트 최소 1건
2. 각 항목에 **이 태스크에서 실제로 일어난 일**을 근거로 붙인다
3. 거절·재시도가 있었으면 그 원인을 분석한다
4. **이번 태스크의 결정 중 ADR 승격 대상이 있는지 판정한다**
5. **아키텍처 문서와 실제 코드의 괴리(drift)를 확인한다**
6. **HITL#4 를 기다리지 않고** 태스크를 `DONE` 으로 닫는다. 회고 승인은 비동기다 —
   「일괄 검토」에서 여러 태스크를 모아 받는다

## FORBIDDEN

1. ❌ 일반론 쓰기 — "테스트를 잘 쓰자" 같은 항목은 아무것도 바꾸지 않는다
2. ❌ 이 태스크에서 일어나지 않은 일을 회고하기
3. ❌ **`approved_by_human` 을 스스로 `true` 로 쓰기** — 「일괄 검토」에서 `AskUserQuestion`
   응답을 받은 뒤에만 쓴다. 태스크를 닫는 것과 회고를 승인받는 것은 다른 일이다
4. ❌ Problem 항목을 빼고 좋은 것만 쓰기

## EXIT GATE

- `workflow_design/08_reflect/REFLECT_<ID>.json` 존재
- `keep.length >= 1`, `insights.length >= 1`
- `completion_report.approved_by_human == false` — 승인은 「일괄 검토」에서 채운다
- `CP-5.2` 저장
- **Phase 1~5의 모든 산출물과 체크포인트가 커밋됨**
- **`tasks.json` 의 `status` 가 `done`** — memory-bank 만 DONE 이면 태스크가 닫힌 게 아니다

```bash
python scripts/verify_workflow_artifacts.py --task-id TASK-001    # exit 0
python scripts/rebuild_memory_bank_index.py --check               # exit 0
```

---

## 절차

### Step 1 — 이력 수집

이 태스크에서 실제로 무슨 일이 있었는지 모은다. **스크립트로 모으고, 원문은 필요할 때만 연다.**

```bash
python3 scripts/collect_task_history.py --task-id TASK-001
```

체크포인트 · VERIFY · DEV · PLAN · VALIDATION 과 그 git 이력을 한 번에 모은다. 파일을 읽어서는
알 수 없는 것도 나온다 — VERIFY 는 라운드마다 덮어써지므로 **Phase 4 가 몇 번 FAIL 했는지**는
git 이력을 라운드로 묶어야 보인다. 체크포인트의 되돌아간 기록과 VERIFY 라운드가 어긋나면
(FAIL 은 있는데 attempts 가 없으면) 기록 누락으로 알린다.

출력의 자유 텍스트는 한 줄로 접히고 잘린다. 원문이 필요한 항목만 해당 파일을 연다.

볼 것:

- 각 CP 의 `attempts` → 어디서 몇 번, 왜 되돌아갔는가
  (v1 체크포인트를 쓰던 태스크면 `_retry` 파일과 `SUPERSEDED` 가 같은 정보다)
- 각 CP의 `decisions` → 무엇을 왜 결정했는가
- `VERIFY_<ID>.json` 의 WARN·예외 승인 → 무엇을 남겨뒀는가
- `VERIFY_<ID>.json` 의 `root_causes` → `origin: later` 는 첫 라운드의 뿌리 스윕이 놓친
  변종이다. 어떤 질문이 빠졌는지가 개선 재료다 (`not_probed` 가 많았다면 프로브 환경도)
- `DEV_<ID>.json` 의 `scope_deviations` → 계획을 벗어난 곳
- Phase 4 라운드 수와 각 라운드의 판정 사유 → 되돌아간 횟수의 실제 값
- PLAN 의 `exploration` → Phase 1 조사 시험의 판정 재료 (`wf-plan/references/explore-trial.md`)

### Step 2 — KPT 분석

**Keep** — 잘 작동해서 다음에도 할 것

```
require_role 데코레이터를 재사용했다. Phase 1의 codebase_analysis.reusable 에
미리 적어둔 덕분에 Phase 3에서 권한 로직을 새로 짜지 않았다.
```

**Problem** — 마찰이 있었던 곳

```
성능 기준("응답 시간 20% 이내")이 acceptance_criteria 에 있었는데 측정 수단이 없어
Phase 4에서 WARN으로 남았다. 태스크를 만들 때 자동 검증 가능성을 확인하지 않았다.
```

**Try** — 다음에 시도할 구체적 변경

```
태스크 생성 시 acceptance_criteria 각 항목에 "어떤 명령으로 확인하는가"를 적게 한다.
docs/workflow/task-schema.md 의 WRU 필수 조건 5번(Verify 자동화 가능)을
"측정 명령을 명시할 수 있다"로 구체화한다.
```

Try는 **어느 파일의 무엇을 바꿀지**까지 적는다. 그렇지 않으면 실행되지 않는다.

KPT 는 `REFLECT_<ID>.json` 에 들어가므로 따로 저장하지 않는다.

### Step 3 — Foundation 되먹임

회고가 Foundation을 갱신하지 않으면 아키텍처 문서는 반년 뒤 아무도 믿지 않게 된다.
이 단계가 그 고리다. 세 종류를 **구분해서** 낸다.

#### 3-1. ADR 승격 후보

이번 태스크에서 내린 결정 중 **이 태스크·이 기능을 넘어 적용되는 것**을 찾는다.
체크포인트의 `decisions` 와 Plan의 설계 판단이 재료다.

```jsonc
"adr_candidates": [
  { "decision": "캐시 무효화를 이벤트 기반으로 처리",
    "why_broader": "다른 조회 API 에도 같은 방식이 필요하다",
    "evidence": "CP-3.4 의 decisions",
    "suggested_title": "캐시 무효화 전략" }
]
```

기준은 `adr` 스킬 §1을 쓴다. 애매하면 후보로 올리고 사용자가 판단하게 한다.

#### 3-2. 아키텍처 drift

문서와 실제 코드가 어긋난 지점.

```jsonc
"architecture_drift": [
  { "what": "architecture.md 는 3계층인데 실제로는 API 가 리포지토리를 직접 호출하는 곳이 있다",
    "where": "src/api/legacy_export.py",
    "found_how": "check_architecture.py 경고",
    "suggestion": "제약을 error 로 올리거나, 예외를 문서화" }
]
```

이번 태스크가 만든 것이 아니어도 눈에 띄었으면 적는다.

**승격 기한이 지난 warn 제약도 drift 다.** `check_architecture.py` 가 `overdue_promotions` 로
알려준다. 이번 태스크가 그 `promote_after` 였다면 특히 — 승격 약속을 회고에서 다시 꺼내지
않으면 아무도 기억하지 않는다. drift 는 발견될 때 적어두지
않으면 다음에 또 발견된다.

#### 3-3. 워크플로우 규칙 개선

`docs/workflow/`, `.claude/skills/` 를 고쳐야 하는 것.

```jsonc
"rule_proposals": [
  { "target": "docs/workflow/task-schema.md",
    "section": "§1 WRU 필수 조건",
    "change": "5번 항목에 '측정 명령을 명시할 수 있다'를 추가",
    "evidence": "TASK-001 에서 성능 기준이 WARN으로 남음",
    "status": "pending",             // pending | applied | rejected
    "recurring": 2 }                 // 같은 대상의 미반영 제안이 이미 있으면 그 수
]
```

`target` 은 **파일 경로로 쓴다** (`.claude/skills/wf-plan/SKILL.md`). 같은 파일을 여러 표기로
적으면 같은 문제가 반복돼도 반복으로 집계되지 않는다.

**제안하기 전에 이미 쌓인 것을 본다.**

```bash
python3 scripts/wf_status.py --proposals
```

같은 대상에 미반영 제안이 이미 있으면 `recurring` 에 그 수를 적고, **일괄 검토에서 "지금
반영"을 선택지로 올린다** (「일괄 검토」). 같은 파일에 대한 제안이 쌓인다는 건 같은 원인의 재작업이
계속되고 있다는 뜻이다 — 실사용에서 `coverage-policy.md` 개선이 세 태스크에 걸쳐 제안되는
동안 같은 원인의 롤백이 반복됐다.

**이 Phase 안에서 문서를 직접 고치지 않는다.** 회고 중에 규칙을 바꾸면 그 변경이 검토를
거치지 않는다. 반영은 일괄 검토에서 승인을 받은 뒤 별도 커밋으로 한다.

**대상이 워크플로우 자산이면** (`.claude/`, `docs/workflow/`, `scripts/`) 이 프로젝트를 만든
**스타터에도 같은 변경이 필요하다.** 프로젝트에서만 고치면 다음 프로젝트가 같은 문제를 다시
겪는다. 반영할 때 사용자에게 이것을 알린다.

### Step 4 — REFLECT JSON 저장

```jsonc
{
  "task_id": "TASK-001",
  "keep": [
    { "what": "재사용 자산을 Phase 1에서 미리 식별",
      "evidence": "PLAN 의 reusable 에 require_role 기록 → Phase 3에서 즉시 사용" }
  ],
  "problem": [
    { "what": "성능 기준에 측정 수단이 없었음",
      "evidence": "VERIFY_TASK-001.json 의 WARN 1건",
      "phase": 4 }
  ],
  "try": [
    { "what": "acceptance_criteria 에 검증 명령을 함께 적기",
      "target": "docs/workflow/task-schema.md" }
  ],
  "insights": [
    "자동 검증이 불가능한 완료 기준은 태스크 생성 시점에 걸러야 한다"
  ],
  "phase_analysis": {
    "1": { "retries": 0, "note": "—" },
    "2a": { "retries": 1, "note": "검증자가 SC-04 의 Then 을 관찰 불가로 지적" },
    "2b": { "retries": 0, "note": "—" },
    "3": { "retries": 0, "note": "—" },
    "4": { "retries": 0, "note": "WARN 1건 (성능 미측정)" },
    "5": { "retries": 0, "note": "—" }
  },
  "adr_candidates": [ /* Step 3-1 */ ],
  "architecture_drift": [ /* Step 3-2 */ ],
  "rule_proposals": [ /* Step 3-3 */ ],
  "completion_report": { "approved_by_human": false }
}
```

`CP-5.2_context-reflect.md` 저장.

### Step 5 — 완료 리포트

Phase 1~5를 한 장으로 정리해 **Artifact로 발행**한다. 터미널 스크롤백에만 남기지 않는다 —
회고는 나중에 다시 볼 자료다.

**`track: light` 면 이 Step 을 건너뛴다.** REFLECT JSON 과 일괄 검토 요약으로 충분하다
(→ `wf-orchestrator` 「경량 경로」).

담을 것: 태스크 개요 / Phase별 진행과 재시도 / 변경 파일 / 테스트·검증 결과 /
KPT / 규칙 개선안.

`artifact-design` 스킬을 먼저 로드한 뒤 HTML을 작성한다.

> 원본 저장소는 이 리포트를 605줄짜리 렌더러 스크립트 + HTML 템플릿으로 만들고, 바이트 단위
> 대조까지 EXIT GATE에 넣고 있었다. Artifact가 그 일을 대신하므로 스크립트를 두지 않는다.

### Step 6 — 태스크 종료

**HITL#4 를 기다리지 않는다.** 회고 승인은 다음 태스크를 막을 이유가 없다. 실사용에서 회고
초안이 끝난 뒤 승인까지 몇 시간씩 걸렸는데(TASK-012 는 3시간 20분), 그동안 태스크가 열려
있어 Ship 도 다음 태스크도 밀렸다. 규칙 개선 제안은 이미 `pending` 으로 쌓였다가 모아서
반영되고 있었다.

1. `completion_report.approved_by_human` 은 `false` 그대로 둔다
2. `CP-5.2` 갱신 — `next_steps` 에 "회고 승인 대기 — /wf-retro"
3. `activeContext.md` 의 `status` 를 `DONE` 으로
4. 체크포인트들의 `status` 를 `ARCHIVED` 로
5. `python scripts/rebuild_memory_bank_index.py`
6. `python scripts/verify_workflow_artifacts.py --task-id TASK-001` → exit 0 확인
7. 커밋

**5번이 `tasks.json` 의 `status` 도 함께 고친다.** 상태가 두 곳에 있기 때문이다 —
`activeContext.md`(시작된 뒤에만 존재)와 `tasks.json`(시작 전부터 존재). 예전에는
`activeContext.md` 만 DONE 이 되고 `tasks.json` 은 `todo` 로 남았는데,
`/wf-start`(인자 없음)와 `depends_on` 판정은 `tasks.json` 을 읽는다. 그 결과
**완료된 태스크가 다시 후보로 제시되고 후속 태스크의 선행 의존이 풀리지 않았다.**

출력에 `tasks.json status 갱신 — TASK-001: todo → done` 이 보이는지 확인한다.
안 보이면 이미 맞거나, `tasks.json` 의 `id` 와 memory-bank 폴더명이 다른 것이다.

```bash
git add workflow_design/ memory-bank/
git commit -m "chore(workflow): TASK-001 회고 작성 및 태스크 종료

Refs: TASK-001"
```

`git add` 에 `workflow_design/08_reflect` 가 아니라 `workflow_design/` 을 쓰는 이유는
`02_tasks/tasks.json` 도 이 커밋에 들어가야 하기 때문이다.

**태스크 폴더를 지우지 않는다.** 과거 결정 기록은 비슷한 작업에서 같은 논의를 반복하지 않게
해주는 자산이다.

### Step 7 — Ship 안내

태스크가 `DONE` 이어도 **머지되지 않으면 릴리스에 포함되지 않는다.** 회고를 마치면
다음 단계를 안내한다. 회고 요약도 여기서 한 번 보여준다. 승인 요청은 아니고, 사람이 나중에
일괄 검토할 때 무엇이 기다리는지 미리 알게 하려는 것이다.

```
TASK-001 완료 — 회고 승인 대기

  Keep 2 / Problem 1 / Try 1
  ADR 승격 후보 1건 · 규칙 개선안 1건 (⚠ wf-plan 반복 3건째)
  리포트: <Artifact 링크>

다음: /wf-ship 으로 머지를 준비하세요.
      회고 승인은 /wf-retro 로 나중에 모아서 받습니다.
```

회고 산출물 커밋은 신선도 판정에 영향을 주지 않는다 — `check_freshness.py` 는 워크플로우
산출물이 아닌 소스 변경만 본다.

---

## 일괄 검토 (HITL #4) — `/wf-retro`

닫힌 태스크 중 회고 승인을 받지 않은 것을 모아 한 번에 승인받는다. 사용자가 `/wf-retro` 나
"회고 승인"을 요청할 때 한다. 태스크 Phase 안의 단계가 아니다.

**1. 대상을 모은다.**

```bash
python3 scripts/wf_status.py --retros            # 승인 대기 회고
python3 scripts/wf_status.py --proposals         # 미반영 규칙 제안 · 반복
```

대기 회고가 없으면 그렇게 말하고 끝낸다.

**2. 작업 브랜치를 만든다.** 대상 태스크의 feature 브랜치는 이미 머지됐을 수 있다. 기준
브랜치에서 `chore/retro-<YYYYMMDD>` 를 갈라낸다.

**3. 태스크마다 요약을 보여준다.** 요약은 오래된 태스크부터 보여준다.

```
회고 일괄 검토 — 3건

TASK-001  매장 검색 권한 필터
  Keep 2 / Problem 1 / Try 1
  재시도       Phase 2a 1회 (독립검증 지적)
  ADR 승격     1건 — "캐시 무효화 전략"
  아키텍처 drift 0건
  규칙 개선안   1건 — docs/workflow/task-schema.md
  리포트: <Artifact 링크>

TASK-002  …
```

반복 제안(`recurring`)은 태스크별이 아니라 **대상 파일별로 묶어** 마지막에 보여준다.

**4. `AskUserQuestion` 으로 받는다.** 한 번에 질문 4개까지 보낼 수 있으므로 태스크 하나당
질문 하나로 나눈다. 4건을 넘으면 나눠서 묻는다. 반복 제안이 있으면 마지막 질문으로 붙인다.

태스크마다 선택지:

- **승인** → `approved_by_human = true`
- **승인 + ADR 작성** → 승인 후 `/wf-adr` 로 승격 후보를 기록한다
- **회고 보완** (`REVISION_NEEDED`) → 무엇을 보완할지 받아 REFLECT 를 고친 뒤 그 태스크만 다시 묻는다
- **제안만 반려** → 회고는 승인하되 ADR·규칙 제안은 폐기한다 (`status: rejected`)

반복 제안이 있을 때 붙이는 질문은 **지금 반영 / 다음에**다. "지금 반영"이면 대상 파일의 미반영
제안을 **모든 태스크 것을 한꺼번에** 한 커밋으로 반영한다. 대상이 워크플로우 자산이면
스타터에도 같은 변경이 필요하다는 것을 알린다 (Step 3-3).

**5. 기록하고 커밋한다.**

```jsonc
"completion_report": {
  "approved_by_human": true,
  "reviewed_at": "2026-11-05T10:30:00Z",
  "reviewed_in": "batch",            // 일괄 검토에서 승인했다는 표시
  "note": "사람의 코멘트가 있으면"
}
```

반영한 제안에는 `"status": "applied", "applied_in": "<커밋 해시>"` 를 적는다. 적지 않으면
`/wf-status` 가 계속 미반영으로 센다. 제안 반영 커밋과 승인 기록 커밋은 나눈다.

```bash
git add workflow_design/08_reflect
git commit -m "chore(workflow): 회고 3건 일괄 승인

Refs: TASK-001, TASK-002, TASK-003"
```

푸시와 PR 생성은 사람이 한다 — 명령만 제시한다 (절대 규칙 9). 태스크 Ship 이 아니므로
`/wf-ship`·`ship_preflight.py` 의 대상이 아니다.
