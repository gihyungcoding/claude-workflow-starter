# 실패 유형 카탈로그

태스크가 **여는 노출면**마다 미리 확인할 칸. Phase 1 이 PLAN `design.surfaces` 에 이 태스크가 여는 노출면을 고르면
`coverage_matrix.py` 가 아래 표의 칸을 펼치고, Phase 2a 가 칸마다 시나리오(`covered`) 또는 이유(`n/a`)를 적는다.
입력 필드의 경계(길이·NUL·정수 표기…)는 여기가 아니라 `coverage-policy.md` §2-1 이 맡는다.

**왜 있나** — Phase 4 가 FAIL 을 내고 되돌아가면 같은 노출면의 다른 칸이 다음 라운드에 나왔다(`later` 변종).
ssirleague TASK-004 는 정적 서빙을 열고 405 → 415·400 → Range 416·컨테이너 수준 400 → 커밋된 응답 순으로 4라운드를 돌았다.
리뷰어가 구현 뒤에 찾던 것을 구현 전에 시나리오로 정하게 하는 것이 목적이다.

**어떻게 자라나** — 회고(Phase 5)가 `later` 변종과 후속 태스크로 넘긴 변종을 이 표의 행 제안으로 올리고(`rule_proposals`,
target 이 이 파일), `/wf-retro` 에서 사람이 승인하면 더한다. `python3 scripts/verify_convergence.py --candidates` 가 아직 표에 없는
후보를 모아 준다. 효과는 같은 스크립트의 태스크별 Phase 4 라운드 수와 `later` 수로 본다.

**형식** — 노출면은 `## \`이름\` — 설명`, 칸은 표의 첫 열 `` `이름` ``(영소문자·숫자·밑줄). 스크립트가 이 형식을 읽는다.
칸은 "무엇을 확인하나" 를 기대 결과까지 쓴다 — 그래야 Phase 3 이 이 칸을 `RETRY_FIX` 의 근거로 쓸 수 있다.
출처가 이 프로젝트의 태스크가 아니면(스타터가 다른 프로젝트에서 가져온 것) 프로젝트 이름을 붙인다.

---

## `http_error_path` — 새로 열거나 바꾼 HTTP 경로의 오류 응답

언제: 컨트롤러·정적 리소스·SPA 폴백·필터·보안 체인을 새로 열거나 바꿀 때. 이 경로의 모든 오류가 `conventions.md` C-ERROR 형식인가.

| 칸 | 무엇을 확인하나 | 출처 |
|---|---|---|
| `method_not_allowed` | 허용하지 않은 메서드 → 우리 형식의 405 (500 이 아니다) | ssirleague TASK-004 RC-1 |
| `media_type` | 받지 않는 Content-Type → 415, 받을 수 없는 Accept → 406, 둘 다 우리 형식 | ssirleague TASK-004 RC-2 |
| `request_binding` | 필수 파라미터·헤더 누락, 타입 변환 실패 → 400 우리 형식 | ssirleague TASK-004 RC-2 |
| `status_preserved` | 프레임워크가 상태를 정한 예외(4xx·5xx)가 catch-all 에서 500 으로 바뀌지 않는다 | ssirleague TASK-004 RC-2 |
| `accept_html` | `Accept: text/html` 만 보낸 요청의 오류도 상태·형식을 잃지 않는다 | ssirleague TASK-004 RC-3 |
| `container_level` | 서블릿 컨테이너·프록시가 직접 내는 오류(깨진 퍼센트 인코딩·긴 URL·잘못된 헤더) | ssirleague TASK-004 RC-3 |
| `error_dispatch_auth` | 오류 디스패치(`/error`)가 인증 대상이 되어 400·405·415 가 401 로 바뀌지 않는다 | ticket-booking TASK-009 RC-2 |

## `static_serving` — 정적 파일·SPA 폴백

언제: 빌드 결과물을 서버가 서빙하거나 SPA 폴백을 둘 때.

| 칸 | 무엇을 확인하나 | 출처 |
|---|---|---|
| `range_invalid` | 잘못된 Range → 416 이 우리 형식이고 본문이 파일 내용이 아니다 | ssirleague TASK-004 RC-3 |
| `fallback_boundary` | API·actuator 경로의 404 가 index.html 로 떨어지지 않는다 · 확장자가 있는데 없는 파일은 index.html 이 아니라 404 | ssirleague TASK-004 |
| `cache_on_error` | 정적 처리기가 붙인 장기 캐시 헤더가 오류 응답에 남지 않는다 | ssirleague TASK-004 RC-3 |

## `response_commit` — 이미 쓰기 시작한 응답

언제: 스트리밍·파일 전송·헤더를 먼저 정하는 처리기가 있을 때.

| 칸 | 무엇을 확인하나 | 출처 |
|---|---|---|
| `error_after_commit` | 본문을 쓰고 flush 한 뒤의 예외에 오류 JSON 을 덧붙이지 않는다 | ssirleague TASK-004 RC-4 |
| `preset_headers` | 처리기가 미리 정한 Content-Length·Content-Range 등이 오류 응답을 자르거나 남지 않는다 | ssirleague TASK-004 RC-3 |

## `broad_catch` — 넓게 잡는 예외 처리

언제: 예외를 넓게 잡아 한 가지 응답으로 바꿀 때(무결성 위반 → 409, 모든 예외 → 500).

| 칸 | 무엇을 확인하나 | 출처 |
|---|---|---|
| `other_causes` | 같은 예외를 내는 다른 원인 각각이 맞는 응답을 받는다(UNIQUE 아닌 무결성 위반이 409 로 오보되지 않는다) | ticket-booking TASK-009 RC-1 |
| `enumerated_gap` | 예외를 하나씩 나열해 처리한다면 빠진 것이 무엇으로 가는가 — 상위 타입·상태 보존으로 한 곳에서 | ssirleague TASK-004 RC-2 |

## `shared_rule` — 같은 규칙을 여러 곳에서 판정

언제: 같은 판정(공백 여부·이메일 형식·경로 매칭·인증 화면 판별)을 둘 이상의 호출부가 할 때.

| 칸 | 무엇을 확인하나 | 출처 |
|---|---|---|
| `every_call_site` | 판정하는 모든 호출부(Grep 으로 열거)가 같은 함수를 쓴다 — 시나리오는 호출부마다 하나씩 | ticket-booking TASK-020 RC-1, TASK-011 RC-2 |
| `matcher_parity` | 직접 비교하는 판정이 실제 매칭 규칙(라우터의 끝 슬래시·대소문자·디코딩)과 같다 | ticket-booking TASK-018 RC-2 |

## `datetime_text` — 시각 문자열 해석

언제: 외부에서 받은 시각 문자열을 해석·검증할 때(서버 응답·토큰·폼).

| 칸 | 무엇을 확인하나 | 출처 |
|---|---|---|
| `calendar_rollover` | 달력에 없는 날(02-30·04-31·비윤년 02-29)이 다음 달로 넘어가지 않고 거부된다 | ticket-booking TASK-018 RC-1, TASK-020 RC-4 |
| `out_of_range_fields` | T24:00·초 60·월 00·일 00·오프셋 +24:00 | ticket-booking TASK-018 RC-1 |
| `two_digit_year` | 연도 0000~0099 가 보정되지 않는다 | ticket-booking TASK-020 RC-4 |
| `order_between` | 여러 시각 사이의 순서(열림 < 닫힘 < 시작) | ticket-booking TASK-020 RC-4 |

## `external_io` — 외부 호출

언제: 화면이나 서버가 외부·서버 API 를 기다릴 때.

| 칸 | 무엇을 확인하나 | 출처 |
|---|---|---|
| `timeout` | 응답이 오지 않으면 정해진 시간 뒤 실패 상태로 간다(영원히 로딩이 아니다) | ticket-booking TASK-020 RC-3 |
| `stalled_body` | 헤더는 왔는데 본문이 멈춘 경우 | ticket-booking TASK-020 RC-3 |
| `abort_on_leave` | 화면을 떠나거나 다시 요청하면 이전 요청을 멈추고 결과를 버린다 | ticket-booking TASK-020 RC-3 |

## `concurrent_write` — 같은 행을 여럿이 고침

언제: 읽고-고치고-저장하는 갱신, 수량·상태 전이.

| 칸 | 무엇을 확인하나 | 출처 |
|---|---|---|
| `lost_update` | 동시에 두 요청이 고치면 한쪽이 덮이지 않는다(버전·조건부 UPDATE·잠금) | ticket-booking TASK-023 RC-1 |

## `deploy_change` — 배포 순서가 있는 변경

언제: 서버와 클라이언트가 함께 바뀌거나, 마이그레이션이 기존 데이터를 바꿀 때.

| 칸 | 무엇을 확인하나 | 출처 |
|---|---|---|
| `transition_window` | 한쪽만 배포된 동안 옛 클라이언트·새 서버(또는 반대)가 동작한다 | ticket-booking TASK-022 RC-2 |
| `existing_rows` | 마이그레이션 뒤 기존 행이 새 규칙에서 쓸 수 있다(새 NOT NULL·소유자 컬럼) | ticket-booking TASK-022 RC-2 |

## `mockup_parity` — 시안을 코드로 옮김

언제: Frontend 태스크가 시안 화면을 구현할 때.

| 칸 | 무엇을 확인하나 | 출처 |
|---|---|---|
| `screen_specific_rules` | 시안의 화면 고유 클래스·맥락 규칙(`.plain .appbar` 같은)이 빠지지 않았다 — Phase 3 에서 시안과 나란히 대조 | ticket-booking TASK-018 RC-3 |
| `state_screens` | 시안의 상태 화면(빈·오류·만료)마다 같은 요소가 있다 | ticket-booking TASK-018 RC-3 |
