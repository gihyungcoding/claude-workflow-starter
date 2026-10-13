---
description: 현재 작업 상태를 체크포인트로 저장하고 커밋한다
---

지금까지의 진행을 체크포인트에 남긴다. 세션을 끝내기 전이나 긴 작업 중간에 쓴다.

**체크포인트는 Phase 당 하나다.** 새 파일을 만들지 않고, 현재 Phase 의 CP 를 덮어쓴다
(→ `docs/workflow/checkpoint-template.md`).

## 1. 대상

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cat "$REPO_ROOT/memory-bank/<활성 TASK-ID>/activeContext.md"
```

`activeContext.md` 의 `phase` 로 파일이 정해진다.

| phase | 파일 |
|---|---|
| 1 | `phase1/CP-1.3_context-plan.md` |
| 2a | `phase2a/CP-2.2_canonical-scenarios.md` |
| 2b | `phase2b/CP-2.5_red-code.md` |
| 3 | `phase3/CP-3.4_context-dev.md` |
| 4 | `phase4/CP-4.2_verification.md` |
| 5 | `phase5/CP-5.2_context-reflect.md` |

## 2. 작성

다섯 필드만 쓴다. 본문은 쓰지 않는다.

- `summary` — 지금 어디까지 왔나, 한 문장
- `next_steps` — 다음 세션이 무엇부터 할지, 우선순위 순
- `decisions` — 이번에 내린 결정과 **이유**. 기존 항목은 지우지 않고 덧붙인다. 없으면 `[]`
- `attempts` — 되돌아온 적이 있으면 그대로 유지한다
- `status` · `saved_at`

이번 세션에서 실제로 일어난 것만 적는다. 하려던 것을 한 것처럼 쓰지 않는다.

**쓰지 않는 것** — 완료 목록, 산문 요약, 테스트 명령, 산출물 내용. 각각 git log ·
단계 JSON · `CLAUDE.md` 에 이미 있다.

## 3. activeContext 갱신

- `last_checkpoint` · `last_updated`
- `artifacts` (새 산출물이 생겼으면)
- 본문의 "지금 무엇을 하고 있나" / "다음 한 걸음"

체크포인트만 갱신하고 `activeContext.md` 를 두면 복구 시 어느 쪽이 최신인지 알 수 없다.

## 4. 커밋

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
git add "$REPO_ROOT/memory-bank/<TASK-ID>" workflow_design/
git commit -m "chore(memory-bank): <TASK-ID> Phase <N> 체크포인트"
```

**커밋까지가 이 명령의 범위다.** 커밋하지 않은 체크포인트는 세션이 끊기면 복구되지 않는다.

## 5. 보고

```
Phase 3 체크포인트 갱신 (CP-3.4)

  지금   대상 테스트 6/6 통과, 리팩토링 검토 중
  다음   쿼리 조립을 리포지토리로 이동
  커밋   a3f21c9
```
