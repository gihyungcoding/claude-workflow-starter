# BRIEF — 요청 하나의 계획

사용자 프롬프트 하나에서 시작해 대화로 다듬고 사람이 확정(Lock, HITL#0)하는 계획이다.
Phase 1 의 앞부분(Intake → Draft → Refine → Lock → Dispatch)이 이 파일 하나를 채운다.
태스크별 `PLAN_<ID>.json` 은 그 뒤(Normalize)에 만든다.

| 무엇 | 경로 |
|---|---|
| 계획 | `workflow_design/01_brief/BRIEF_<REQ-ID>.json` |
| 시안 증거 | `workflow_design/01_brief/mockup/<REQ-ID>/` |
| 로컬 이벤트 | `workflow_design/09_telemetry/<REQ-ID>.jsonl` |

검사: `scripts/check_brief.py` (게이트) · `scripts/route_brief.py` (수정 범위 → 후속 작업) ·
`scripts/plan_impact.py` (계획이 바뀌면 어디부터 다시 하나) · `scripts/wf_event.py` (이벤트).

---

## 1. 요청 ID — `REQ-NNN`

```
REQ-001, REQ-0042        정규식: ^REQ-\d{3,}$
```

요청 하나는 태스크 0~n 개가 된다(비코드 요청은 0개, 기능은 여러 개). 태스크가 생기기 전에
계획이 있어야 하므로 태스크 ID 를 빌리지 않는다. 요청에서 나온 태스크는
`source_refs.request_id` 로 요청을 가리킨다.

## 2. 상태

```
drafting → refining → locked → dispatched → done
                 └─────────────→ abandoned
```

| status | 뜻 | 다음으로 가는 조건 |
|---|---|---|
| `drafting` | 1차 계획을 쓰는 중 | 초안 커밋 → `draft_commit` 기록 |
| `refining` | 결정 대화 중 | `check_brief.py --gate lock` 통과 + HITL#0 승인 |
| `locked` | 사람이 확정함 | Dispatch 작업 전부 끝 (`--gate dispatch`) |
| `dispatched` | 후속 작업을 다 만들었다 — 태스크가 돈다 | 요청의 태스크가 모두 DONE |
| `done` · `abandoned` | 끝 | — |

## 3. 형식

```jsonc
{
  "id": "REQ-001",
  "status": "refining",
  "prompt": "사용자가 쓴 원문 그대로",
  "posture": "hold",                    // hold | selective | expand | reduce — 범위를 대하는 자세
  "goal": "한 문장",

  "acceptance_criteria": [
    { "id": "AC-1", "text": "…", "kind": "happy", "ui": true },   // ui: 화면에서 보여야 하는가
    { "id": "AC-2", "text": "…", "kind": "error", "ui": true }
  ],
  "out_of_scope": ["…"],

  "approach": {                         // 실제로 갈림길이 있을 때만
    "chosen": "A",
    "options": [{ "id": "A", "summary": "최소안", "effort": "S", "risk": "…", "reuses": ["…"] }]
  },
  "assumptions": [{ "text": "…", "verified_by": "src/api/x.py:42" }],   // 확인 못 했으면 null

  "decisions": [                        // 결정 기록부 — §4
    { "id": "D1", "class": "user_challenge", "source": "eng",
      "question": "…", "options": ["…"], "recommended": "…",
      "status": "approved", "answer": "…", "scope": "이 승인이 덮는 범위" }
  ],
  "completeness": [                     // 영향 범위 안의 완전성 보강 — §5
    { "id": "C1", "text": "형제 엔드포인트 검증 대칭", "in_radius": true, "estimate_delta_h": 1, "status": "included" }
  ],

  "scope": {                            // 수정 범위 — route_brief.py 가 후속 작업으로 바꾼다
    "wru": true,                        // 프로덕션 코드가 바뀌는가. false 면 파이프라인 밖에서 처리
    "routes": ["Backend", "Frontend"],
    "product_change": false,            // product.md 범위를 바꾸는가
    "architecture": { "change": false, "adr": [] },   // 새 계층·의존 방향 / 새로 쓸 ADR 제목
    "design_tokens": false,             // design.md §4·§5 를 채우거나 바꾸는가
    "ui": "mockup",                     // none | annotate(기존 화면 표시) | mockup(새 화면 시안)
    "migration": false,
    "paths": ["src/api/x.py"]           // 근거 경로 — 경로 기준 교차 확인에 쓴다
  },
  "split": [                            // 태스크 분할안 — WRU 4~16h
    { "key": "A", "title": "…", "route": "Backend", "estimate_h": 8, "ac": ["AC-1", "AC-2"], "depends_on": [] }
  ],

  "mockup": {                           // scope.ui 가 mockup 일 때
    "status": "approved",               // none | draft | approved
    "rev": 3,
    "coverage": { "AC-1": ["home", "d-home"] },   // 완료 조건 → 시안 화면 id
    "feedback": [{ "rev": 2, "text": "…", "impact": "visual" }],  // visual | state | screen | data
    "artifact_url": null
  },
  "reviews": [{ "role": "eng", "model": "claude", "findings": 4, "accepted": 3 }],

  "dispatch": [{ "job": "adr", "status": "done", "ref": "ADR-0007" }],
  "tasks": ["TASK-012", "TASK-013"],

  "draft_commit": "a1b2c3d",            // 1차 계획을 커밋한 지점 — 대화로 무엇이 바뀌었는지 회고에서 본다
  "human_review": { "approved": true, "locked_commit": "e4f5a6b", "note": "" }
}
```

## 4. 결정 기록부

| class | 무엇 | 어떻게 정하나 |
|---|---|---|
| `mechanical` | 코드·문서가 이미 정한 것(경로, 재사용 대상, 계층 배치) | 묻지 않고 기록만 |
| `taste` | 취향(이름, 문구, 순서) | 추천안으로 정하고 Lock 화면에 목록으로 보여 준다 |
| `user_challenge` | 범위 추가·삭제, 완료 조건, product.md 충돌, 새 계층·ADR, 분할, 위험 정책 | **자동으로 정하지 않는다.** `AskUserQuestion` 으로 묻는다 |

`status`: `unresolved` · `approved` · `declined` · `deferred` · `reopened`.
**Lock 하려면 `unresolved`·`reopened` 가 없어야 한다.** `user_challenge` 는 `answer` 가 있어야 한다.
확정 뒤 다시 열리면 `reopened` 로 바꾸고 `reopened_in` 에 그 Phase 를 적는다 — 회고가 이것을 센다.

## 5. 완전성 보강 (영향 범위 안에서만)

변경 영향 범위 = 변경 대상 파일 · 그 파일을 직접 쓰는 쪽 · 그 파일들을 건드리는 테스트 ·
같은 입력을 받는 형제 엔드포인트 · (화면이면) 범위 안 화면의 상태 화면.

`status: included` 로 자동 포함하려면 `in_radius: true` 이고 `estimate_delta_h ≤ 2` 여야 한다.
넘으면 `user_challenge` 결정으로 올린다. 자동 포함한 것도 Lock 화면에 보여 주고 하나씩 뺄 수 있다
(`status: dropped`) — 조용히 넓히지 않는다.

## 6. 하지 않는 것

- 확정(`locked`) 전에 Dispatch 작업을 시작하지 않는다.
- `human_review.approved` 를 에이전트가 스스로 쓰지 않는다 — `AskUserQuestion` 응답을 받은 뒤에만.
- 확정 뒤 BRIEF 를 고칠 때는 결정을 `reopened` 로 남기고 `plan_impact.py` 로 다시 할 곳을 정한다.
