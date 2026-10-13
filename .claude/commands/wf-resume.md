---
description: 중단한 태스크를 마지막 체크포인트에서 이어간다
argument-hint: "[TASK-ID]"
---

중단된 태스크의 워크플로우를 재개한다.

## 1. 대상 결정

인자가 있으면 그 태스크. 없으면:

```bash
python scripts/wf_status.py --active
```

- 활성 태스크가 1건이면 그것으로 진행
- 여러 건이면 `AskUserQuestion` 으로 고르게 한다
- 없으면 그렇게 알리고 `/wf-start` 를 안내한다

## 2. 상태 복원

`docs/workflow/memory-bank-spec.md` §4.2 절차를 따른다.

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cat "$REPO_ROOT/memory-bank/<TASK-ID>/activeContext.md"
ls -1 "$REPO_ROOT/memory-bank/<TASK-ID>/checkpoints/"*/
```

1. `activeContext.md` 의 `phase` 와 `last_checkpoint` 를 읽는다
2. 체크포인트 디렉터리의 **실제 마지막 CP 파일**을 읽는다
3. 둘이 어긋나면 **CP 파일 쪽을 믿고**, 어긋났다는 사실을 사용자에게 보고한다
4. `status: BLOCKED` 이면 `unblock_condition` 을 보여주고 **진행하지 않는다**

## 3. 중복 작업 방지

마지막 CP에서 다음을 확인하고 그대로 따른다.

| 필드 | 어떻게 쓰나 |
|---|---|
| `summary` | 어디까지 왔는지. 그 이전 작업은 **다시 하지 않는다** |
| `decisions` | 여기 있는 결정은 **다시 논의하지 않는다** |
| 단계 JSON 의 승인 필드 | 채워져 있으면 그 HITL 은 **재승인하지 않는다** (→ `hitl-protocol.md` §4) |
| `next_steps` | `priority: 1` 부터 재개한다 |

## 4. 산출물 확인

`activeContext.md` 의 `artifacts` 에 적힌 파일이 실제로 있는지 본다.

```bash
python scripts/verify_workflow_artifacts.py --task-id <TASK-ID> --up-to-phase <현재 Phase>
```

없으면 **고치지 말고 보고한다.** 커밋되지 않은 채 세션이 끊겼을 가능성이 있고,
그 경우 어디까지가 유효한지는 사람이 판단한다.

## 5. 브랜치 확인

```bash
git branch --show-current
BASE="$(git config workflow.baseBranch || echo develop)"
git rev-list --count "HEAD..$BASE" 2>/dev/null    # 기준 브랜치가 얼마나 앞서갔나
```

`activeContext.md` 의 `branch` 와 다르면 사용자에게 확인한 뒤 체크아웃한다.
임의로 브랜치를 바꾸지 않는다.

**기준 브랜치가 많이 앞서갔으면 알린다.** 오래 중단됐던 태스크일수록 그렇다.

```
feature/task-001 은 develop 보다 23 커밋 뒤처져 있습니다.
지금 rebase 해두면 나중에 충돌을 한 번에 마주치지 않습니다.

  git rebase develop
```

rebase 를 임의로 실행하지 않는다 — 충돌이 나면 사용자가 판단해야 한다.
다만 **Phase 4를 이미 통과한 태스크라면 rebase 가 신선도를 깨뜨린다**는 점을
함께 알린다 (`/wf-ship` 이 재검증을 요구하게 된다).

## 6. 요약 보고 후 재개

```
TASK-001 재개

  Phase      2a (Scenario Design)
  마지막 CP   CP-2.2_canonical-scenarios
  브랜치      feature/task-001-store-search-permission

  완료된 것   시나리오 6건 작성 (happy 3 / error 2 / boundary 1)
  결정 사항   페이지네이션 경계는 SC-03 하나로 통합
  다음 단계   scenario-validator 호출

이어서 진행합니다.
```

그다음 해당 Phase 스킬(`wf-scenario` 등)로 넘어간다.
