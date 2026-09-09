---
description: 전체 태스크의 워크플로우 진행 현황을 보여준다
argument-hint: "[TASK-ID]"
---

## 인자가 없으면 — 전체 현황

```bash
python scripts/wf_status.py
```

출력에 더해 다음을 확인하고 **주의가 필요한 것을 짚어준다**:

- `status: BLOCKED` 인 태스크 → `unblock_condition` 과 며칠째인지
- `last_updated` 가 **14일 이상 지난** 활성 태스크 → 정체 경고
- 같은 Phase에서 재시도가 2회 이상인 태스크

```
활성 3 / 차단 1 / 완료 12

  TASK-004  Phase 3 (Green)      2일 전    매장 검색 권한 필터
  TASK-007  Phase 2a (Scenario)  1일 전    과정 목록 정렬
  TASK-002  Phase 4 (Verify)     23일 전   ⚠ 정체 — 마지막 활동 8/9

  ⛔ TASK-005  차단 11일째
     검색 API 응답 스키마 미확정 (TASK-014 선행)
```

정체된 태스크가 있으면 그냥 표시만 하지 말고, **무엇을 하면 풀리는지** 한 줄 덧붙인다.

## 인자가 있으면 — 태스크 상세

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cat "$REPO_ROOT/memory-bank/<TASK-ID>/progress.md"
ls -1 "$REPO_ROOT/memory-bank/<TASK-ID>/checkpoints/"*/
python scripts/verify_workflow_artifacts.py --task-id <TASK-ID>
```

Phase별 진행 표, 저장된 체크포인트, 산출물 존재 여부, 미충족 EXIT GATE를 보여준다.

```
TASK-004  매장 검색 권한 필터

  Phase 1 Plan      ✅  CP-1.3
  Phase 2a Scenario ✅  CP-2.2 CP-2.3 CP-2.4   (재시도 1회)
  Phase 2b Red      ✅  CP-2.5 CP-2.6
  Phase 3 Green     🔄  CP-3.1                  ← 현재
  Phase 4 Verify    ⬜
  Phase 5 Reflect   ⬜

  산출물   PLAN ✓  SCENARIO ✓  TEST ✓  DEV ✗
  다음     최소 구현 후 pytest 실행

  미충족 게이트 (3→4)
    - DEV_TASK-004.json 없음
    - CP-3.2, CP-3.4 미저장
```

## 파생 상태가 어긋났을 때

`wf_status.py` 는 `activeContext.md` 파일들을 직접 읽으므로 항상 최신이다.
`memory-bank/index.md` 와 `tasks.json` 의 `status` 는 파생물이라 어긋날 수 있다.

```bash
python scripts/rebuild_memory_bank_index.py --check   # 어긋난 곳만 보고
python scripts/rebuild_memory_bank_index.py           # 둘 다 맞춘다
```

**`tasks.json` 불일치는 그냥 넘기지 않는다.** `/wf-start`(인자 없음)와 `depends_on`
판정이 `tasks.json` 을 읽으므로, 완료된 태스크가 다시 후보로 뜨거나 후속 태스크가
영원히 차단된 것처럼 보인다. 현황 보고에 이렇게 덧붙인다:

```
⚠ tasks.json 이 memory-bank 와 다릅니다 (TASK-001: todo ≠ done)
  python scripts/rebuild_memory_bank_index.py 로 맞추고 커밋하세요.
```
