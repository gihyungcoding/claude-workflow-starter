# 코딩 규칙 (conventions)

> 코드를 **어떻게** 쓰는가 — 배치·이름·에러·검증·테스트. 구조(무엇이 무엇을 호출하나)는 `architecture.md`,
> 기계 검사는 `constraints.yaml`, 화면은 `design.md`. 여기 있는 규칙이 "주변 코드"보다 먼저다.
>
> `/wf-init` 2.7 에서 정하고 4.5 의 기준 구현으로 증명한다. 태스크가 새 관례를 처음 만들면 회고(`rule_proposals`)를 거쳐 여기에 더한다.
> 게이트: `python3 scripts/check_conventions.py` — 첫 태스크를 시작하기 전에 통과해야 한다.

## 규칙

표의 형식을 지킨다(게이트가 읽는다). 칸은 4개 — **칸 안에 `|` 를 쓰려면 `\|`**(정규식 `a\|b`). 아니면 열이 밀린다.
**결정**이 `TODO` 면 미결정. **검사**는 이 규칙을 무엇이 지키는지: 린트 규칙(`ruff T20`) · 제약 id(`ARCH-001`) · `리뷰`.
여럿이면 모두 적는다 — 정규식 제약은 우회되기 쉬워(별칭 import 등) 린트 규칙이 있으면 그것이 먼저다.
**상태**: `TODO` → `정함`(2.7) → `기준 구현 확인`(4.5 — 기준 파일로 보이고 사람이 확인). 첫 태스크 전 게이트는 `기준 구현 확인` 을 요구한다.
해당 없는 항목은 결정 `해당 없음 — <이유>`, 검사 `—`, 상태 `해당 없음`. `C-COMMIT` 은 `정함` 그대로.

`C-TESTDB` 의 결정은 **`같음 — …` 또는 `다름 — …` 으로 시작한다**. 다르면 같은 칸에 실재하는 ADR 번호와 전환할 태스크(`promote_after: TASK-…`)를 적는다.

| id | 결정 | 검사 | 상태 |
|---|---|---|---|
| C-TESTDB | TODO | TODO | TODO |
| C-LINT | TODO | TODO | TODO |
| C-LAYOUT | TODO | TODO | TODO |
| C-ERROR | TODO | TODO | TODO |
| C-VALID | TODO | TODO | TODO |
| C-DATA | TODO | TODO | TODO |
| C-TEST | TODO | TODO | TODO |
| C-LOG | TODO | TODO | TODO |
| C-FE | TODO | TODO | TODO |
| C-COMMIT | `CLAUDE.md` 「커밋」 절 | 리뷰 | 정함 |

## 기준 파일

규칙을 모두 지키는 기준 구현(`/wf-init` 4.5). 새 코드는 이 파일들을 본뜬다 — "주변 코드"보다 먼저.
`- 경로 — 무엇의 기준인가` 형식으로 적는다.

## 결정 메모

항목마다 고른 이유·버린 대안을 한두 줄. 되돌리기 어려운 것(테스트 DB·검증 방식처럼 나중에 바꾸면 이전 태스크가 생기는 것)은 ADR 로.
