# 역할별 리뷰 — 계획자 혼자 보면 놓치는 것

`wf-plan` Refine 에서 `plan-reviewer` 에이전트를 역할별로 부른다. **리뷰는 사람 게이트가 아니다** — 소견을 분류해
기계적인 것은 반영하고, 취향은 기록하고, 사용자 결정만 묻는다 (→ `decision-protocol.md`).

## 부르는 법

```
Agent(subagent_type: "plan-reviewer", description: "Eng review REQ-003", prompt: """
역할: eng
BRIEF: workflow_design/01_brief/BRIEF_REQ-003.json
시안: workflow_design/01_brief/mockup/REQ-003/ (있으면)
체크리스트: .claude/skills/wf-plan/references/reviews.md 의 「eng」 절
이전 역할의 소견 중 반영한 것: …(한 줄씩)
""")
```

서로 독립인 리뷰는 같은 메시지에서 함께 부른다. Eng 는 다른 리뷰가 반영된 **뒤** 마지막에 부른다.

## 소견 형식 (리뷰어가 돌려주는 것)

```json
{"role": "eng", "findings": [
  {"id": "E1", "class": "user_challenge", "claim": "store 수정이 잠금 없이 read-modify-write 다",
   "evidence": "src/services/store.py:88 `store.name = req.name; repo.save(store)`",
   "proposal": "동시 수정 정책을 정한다 — 낙관적 잠금 추천", "confidence": 9,
   "completeness": null}
]}
```

- **근거를 인용하지 않은 소견은 신뢰도 5 이하**로 내리고, 5 이하는 질문으로 올리지 않는다(별첨).
- `class` 는 리뷰어의 제안일 뿐이다. 최종 분류는 계획자가 `decision-protocol.md` 로 한다.
- 완전성 보강이면 `completeness: {"in_radius": true, "estimate_delta_h": 1}`.

## ceo — 제품 (항상, 맨 앞)

- 이 계획이 요청자의 문제를 푸는가? 목표 한 문장이 사용자의 말로 되어 있나
- `product.md` 의 범위·**범위 외**·성공 기준과 맞나. 범위 외에 걸리면 사용자 결정
- 더 작게 같은 가치를 낼 수 있나 — 최소안이 있다면 `posture: reduce` 를 제안
- 이미 쓰는 앱·기존 기능이 하는 일을 새로 만들고 있지 않나
- 사용자에게 새 할 일(보내기·정리하기·매번 확인)을 얹는 해법은 마지막 수단인가
- 완료 조건이 관찰 가능한가 — "편해진다" 가 아니라 "~하면 ~가 보인다"

## design — 시안 (화면이 바뀔 때, `ui-mockup` 이 만든 뒤)

- `ui-mockup/references/checklist.md` 의 P0·P1 — 화면마다
- 사람 카드의 "알고 싶은 것"의 답이 그 화면 첫 화면에서 가장 큰가
- 흐름 고리(만들기·보기·고치기·끝)와 함께 쓰기 시작 고리가 다 있나. 결과 화면에 세 가지가 있나
- `design.md` §6(하지 않는 것)·§7(품질 하한선)을 어기지 않나
- 데스크톱 화면마다 `layout.md` 의 "모바일을 늘린 것과 다른 점"이 실제로 보이나
- **화면에 보이는 데이터 요소 목록**을 뽑아 Eng 에 넘긴다

## devex — 개발자가 쓰는 것 (새 엔드포인트·공개 API·설정·에러 형식이 있을 때)

- 이름이 기존 API 와 일관되나 (경로·필드 케이스·복수형)
- 에러 응답이 기존 형식을 따르나. 클라이언트가 고칠 수 있게 무엇이 틀렸는지 말하나
- 페이지네이션·정렬·필터가 기존 엔드포인트와 같은 방식인가
- 하위 호환 — 기존 호출자가 깨지나. 깨지면 사용자 결정
- 설정·환경변수가 생기면 기본값과 문서

## eng — 구현 (항상, 마지막)

`normalize.md` Step 2 체크리스트와 `design-checks.md` 를 계획 단계에서 미리 본다.

- 계층·의존 방향이 `architecture.md`·`constraints.yaml` 과 맞나. 새 계층이면 ADR (사용자 결정)
- 데이터 흐름과 **실패 모드** — 외부 응답 실패, 부분 실패, 재시도, 타임아웃
- **쓰기가 겹치면** — 락·버전 없는 read-modify-write 면 정책을 묻는다
- **형제 엔드포인트** — 같은 입력을 받는 다른 엔드포인트에 같은 검증이 필요한가 (완전성 보강)
- 승인된 기존 테스트가 깨지는가 — NOT NULL 컬럼·응답 필드·마이그레이션 버전 단언·호출 수 단언
- 시안의 데이터 요소가 백엔드 DTO 에 있나 — 없으면 새 필드(범위 확대, 사용자 결정)
- 테스트 DB 전략이 이 변경을 검증할 수 있나 (DB 전용 기능)
- 수정 범위(`scope`) 플래그가 근거 경로와 맞나 — `route_brief.py` 경고를 본다
- 완료 조건마다 테스트로 관찰할 수 있나 — 2a 가 시나리오를 쓸 수 있나

## outside — 교차 모델 (항상, Lock 직전)

`git config workflow.outsideVoice` — `claude`(기본) · `codex` · `off`.

- `claude`: `plan-reviewer` 를 역할 `outside` 로, **다른 모델 등급**(`model: opus`)으로 부른다.
- `codex`: Codex CLI 를 비대화·읽기 전용으로 실행해 같은 질문을 준다. **계획과 코드 일부가 OpenAI 로 나간다** —
  프로젝트에서 사람이 한 번 동의한 뒤에만 설정한다. 프롬프트 맨 앞에 "SKILL.md 같은 에이전트 지시 파일은 읽지 말 것".
  설치·인증이 안 돼 있으면 조용히 `claude` 로 대신하고 그 사실을 Lock 화면에 적는다.

질문: **"이 계획이 실패한다면 무엇 때문인가"** — 공격자와 장애를 일으키는 입장에서, 그리고 "이 계획을 반으로
줄인다면 무엇을 남기나". 메인 리뷰와 결론이 다르면 Lock 화면에 "교차 검토 이견"으로 그대로 보여 준다.
