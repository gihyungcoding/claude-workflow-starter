---
description: 대화형으로 태스크 1건을 만든다
argument-hint: "[무엇을 할지 한 줄 설명]"
---

`task-authoring` 스킬의 기준으로 태스크 1건을 만든다.

> **새로 만들거나 고칠 것을 말로 요청받았다면 기본 진입점은 `/wf-plan "<요청>"` 이다** — 계획을 다듬고 확정한 뒤
> 태스크를 자동으로 만든다. 이 명령은 계획 대화 없이 태스크만 급히 넣을 때 쓴다. 이렇게 만든 태스크도
> `/wf-start` 할 때 `wf-plan` 「요청 없는 태스크」 절차로 짧은 확정을 거친다.

요구사항 문서 없이 급한 작업을 넣을 때 쓴다. 기능이 여러 태스크로 쪼개진다면
`/wf-feature` 로 문서를 먼저 쓰는 편이 낫다 — 그래야 나중에 왜 이렇게 쪼갰는지 남는다.

## 1. 맥락 확인

```bash
cat docs/product/product.md 2>/dev/null | head -60
jq -r '[.[].id] | max' workflow_design/02_tasks/tasks.json
```

- `product.md` 의 **범위 외**에 해당하면 진행 전에 알린다:
  "이건 product.md 에서 '하지 않는 것'으로 적힌 항목입니다. 범위를 넓히는 거라면
  product.md 를 먼저 고쳐야 합니다. 그래도 진행할까요?"
- 비슷한 태스크가 이미 있는지 확인한다 (중복 생성 방지)

## 2. 필요한 것 묻기

인자로 받은 설명에서 채울 수 있는 것은 채우고, **빠진 것만** 묻는다.
다 아는 것을 되묻지 않는다.

필요한 정보:

| 항목 | 없으면 |
|---|---|
| 무엇을 하는가 | 인자 또는 질문 |
| 어디를 고치는가 | 코드베이스를 먼저 찾아본다 (Grep) — 사용자에게 떠넘기지 않는다 |
| 완료 조건 | **정상 1건 + 오류 1건 이상**. "오류일 때는 어떻게 되나요?"를 반드시 묻는다 |
| 추정 | 4~16시간. 벗어나면 합치거나 나눈다 |
| Backend / Frontend | `architecture.md` 로 판정. 애매하면 묻는다 |

`AskUserQuestion` 으로 선택지를 주는 편이 자유 서술보다 빠르다. 예를 들어 route 판정,
우선순위, 규모 추정은 선택지로 제시한다.

## 3. WRU 판정

`task-authoring` 스킬 §1 의 다섯 조건을 확인한다.

특히 **조건 4 (프로덕션 코드가 바뀌는가)**. "원인을 분석해보자", "스펙을 정하자"는
단독 태스크로 만들지 않고, 사용자에게 이렇게 알린다:

```
이건 워크플로우 1회를 완주할 단위가 아닙니다 —
Green 단계에서 바뀌는 프로덕션 코드가 없어서 Red 테스트를 쓸 수 없습니다.

두 가지 방법이 있습니다:
  1. 후속 구현까지 포함해 하나의 태스크로 (분석은 description 에 흡수)
  2. 워크플로우 밖에서 조사만 하고, 결과로 태스크를 만들기
```

## 4. 생성

`task-authoring` §2 스키마로 만들고, §3 규칙으로 채번한다.

```bash
jq --slurpfile new /tmp/new-task.json '. + $new[0]' \
   workflow_design/02_tasks/tasks.json > /tmp/merged.json && \
   mv /tmp/merged.json workflow_design/02_tasks/tasks.json

python3 scripts/validate_tasks.py
```

## 5. 확인 후 커밋

만든 태스크를 보여주고 확인을 받은 뒤 커밋한다.

```
TASK-005  Backend  매장 검색 결과 캐싱                6h

  완료 조건
    - 같은 검색어 재요청 시 DB 조회가 발생하지 않는다
    - 캐시 만료 후에는 다시 조회한다
    - 캐시 서버가 죽어도 검색은 동작한다

  변경 예상  src/services/store.py
  검증       validate_tasks.py 통과

다음: /wf-start TASK-005
```

```bash
git add workflow_design/02_tasks && git commit -m "chore(tasks): TASK-005 매장 검색 캐싱"
```
