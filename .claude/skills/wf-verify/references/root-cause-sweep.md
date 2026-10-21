# 뿌리 원인 스윕 — FAIL 한 번에 같은 뿌리를 다 드러낸다

`wf-verify` Step 5·7 과 `wf-develop`·`wf-scenario` 의 Phase 4 롤백 재진입에서 참조한다.

## 왜 필요한가

Phase 4 가 FAIL 을 내면 Phase 3(또는 2a)으로 돌아가고, 고친 뒤 다시 검증하면 **같은 뿌리의
다른 입력**이 또 나온다. 되돌아갈 때마다 독립검증 · HITL · Red · Green · 리뷰를 다시 돈다.

| 태스크 | 증상이 나온 순서 | 뿌리 |
|---|---|---|
| TASK-009 | ① 소문자화로 길이가 늘어나는 이메일 → 409 오보 ② name 의 NUL 문자 → 409 오보 | 모든 `DataIntegrityViolationException` 을 UNIQUE 위반으로 취급하는 catch |
| TASK-004 | 좌석 상한 우회 → 길이 초과 · null 원소 → 소수 절삭 | 서비스 계층의 수동 검증에 새 필드·새 경로가 빠짐 |
| TASK-003 | 폰트 굵기 → 배지 radius → 구분선 → lineHeight … | 설정 객체 값이 렌더 결과에 반영되는지를 설계하지 않음 |

회고와 VERIFY 가 세 태스크 모두 뿌리가 같았다고 적었다(TASK-009 는 2차 판정이 "같은 뿌리의
결함"이라고 썼다). 증상 하나씩 고쳐 돌려보내서 라운드가 늘었다. 첫 라운드에 뿌리를 *미리*
알 수 있었는지는 사후 기록으로 확인할 수 없다 — 이 문서는 그것을 시도하게 만드는 장치이고,
효과는 다음 태스크들에서 `later` 가 얼마나 나오는지로 본다.

## 규칙 셋

1. **첫 FAIL 에서 리뷰어가 뿌리와 변종을 적는다.** 결함마다 뿌리를 한 문장으로 쓰고, 같은
   뿌리에서 나올 법한 다른 입력(변종)을 **프로브로 재현해 본다.**
2. **Phase 3 은 뿌리를 고친다.** 증상 하나가 아니라 뿌리를. 재현된 변종마다 테스트를 먼저
   실패시킨 뒤 고친다(Red → Green).
3. **재검증은 이전 기록을 이어받는다.** 지난 `root_causes` 를 그대로 받아 변종이 모두 해소됐는지
   본다. 새 결함이 기존 뿌리에 속하면 새 뿌리를 만들지 않고 **같은 뿌리에 `origin: "later"` 로
   덧붙인다** — 첫 라운드의 스윕이 놓친 것이라는 기록이다.

## 기록 형식

`VERIFY_<ID>.json` 최상위에 둔다. `code_review` 안이 아니다 — 그쪽은 태스크마다 모양이 달라서
기계가 읽을 수 없었다.

```jsonc
"root_causes": [
  {
    "id": "RC-1",
    "summary": "DataIntegrityViolationException 을 전부 UNIQUE 위반으로 취급하는 catch",
    "found_in_round": 1,
    "variants": [
      { "case": "소문자화로 길이가 늘어나는 이메일", "origin": "found",
        "probe": "reproduced", "resolved": true, "evidence": "AuthServiceTest.longEmail" },
      { "case": "name 에 NUL 문자", "origin": "predicted",
        "probe": "reproduced", "resolved": true, "evidence": "AuthServiceTest.nulName" },
      { "case": "name 이 컬럼 길이를 넘는다", "origin": "predicted",
        "probe": "not_reproduced" }
    ]
  }
]
```

| 필드 | 값 |
|---|---|
| `origin` | `found` 리뷰어가 보고한 결함 · `predicted` 같은 뿌리라 있을 법해서 첫 라운드에 미리 적음 · `later` 이후 라운드에서 뒤늦게 나옴 |
| `probe` | `reproduced` 재현함 · `not_reproduced` 시도했으나 재현 안 됨 · `not_probed` 못 함 (`reason` 필수) |
| `resolved` | 고쳤으면 `true` + `evidence`(그것을 막는 테스트). FAIL 이 아닌 판정에서 `reproduced` 변종은 반드시 `true` |

변종이 정말 없으면 `variants: []` 와 함께 `no_variants_reason` 에 **무엇을 검토했고 왜 없는지**
쓴다 (예: "이 catch 가 있는 진입점이 이 하나뿐임을 Grep 으로 확인").

**라운드를 넘길 때는 이전 항목을 그대로 옮겨 적는다.** 해소했어도 지우지 않고 `resolved` 로
남긴다. 문구를 고쳐 쓰면 `check_root_causes.py` 가 지운 것으로 읽는다.

## 변종을 찾는 질문

뿌리를 적은 뒤 아래를 하나씩 물어 후보를 만든다. 후보가 없으면 없다고 적는다.

- **같은 코드 경로를 지나는 다른 입력은?** 한 필드가 문제였다면 같은 DTO 의 다른 필드, 같은
  타입의 입력 전부 (예: 문자열 필드마다 길이·NUL·공백·유니코드)
- **같은 패턴이 다른 곳에도 있는가?** Grep 으로 같은 catch · 같은 변환 · 같은 분기를 찾는다
- **같은 예외를 일으키는 다른 원인은?** 넓게 잡은 catch 는 원인이 여럿이다
- **같은 가정이 깨지는 다른 환경은?** 테스트 DB 와 운영 DB 의 차이(H2 ↔ PostgreSQL), 설정값 조합
- **이 수정이 새로 만들 부작용은?** (`code-review-rounds.md` §2)

## 프로브 규칙

프로브는 **재현 시도**다. 저장소를 바꾸지 않는다.

- 임시 테스트·스크립트는 저장소 밖(시스템 임시 디렉터리)에 둔다. 저장소 안에 파일을 만들지 않는다
- 운영 DB · 외부 서비스에 쓰지 않는다. 로컬 · 인메모리 · 테스트 컨테이너만 쓴다
- 환경이 없어 못 하면(예: Docker 꺼짐) `not_probed` + `reason` 으로 정직하게 적는다.
  `not_reproduced` 로 적으면 "시도했는데 안 됐다"는 거짓 기록이 된다

## 검사

```bash
python3 scripts/check_root_causes.py --task-id TASK-001
```

| 막는 것 | 방식 |
|---|---|
| 뿌리 없는 FAIL | FAIL 이면 `root_causes` 가 비어 있지 않아야 한다 |
| 재현된 변종을 남긴 채 통과 | FAIL 이 아닌 판정에서 `reproduced` 변종은 `resolved: true` + `evidence` |
| 불리한 항목 삭제 | 이전에 커밋된 VERIFY 의 뿌리·변종이 지금 파일에 있어야 한다 (git 이력 대조) |

**못 막는 것: 기록의 질.** 요약이 그럴듯한지, 변종 후보가 충분한지, 프로브를 실제로 돌렸는지는
알 수 없다. 형식만 채워도 통과한다. 그래서 `not_probed` 와 `later` 를 숨기지 않고 세어 보여준다.

## 사람에게 보이는 것

- **FAIL 롤백 요약** — 뿌리 N건 · 변종 M건(재현 K건 · 미확인 J건). 사람은 증상 목록이 아니라
  이 숫자로 "이 롤백이 한 번에 끝날 만한가"를 본다
- **Phase 5 회고** — `later` 가 있으면 첫 라운드 스윕이 놓친 것이다. 어떤 질문이 빠졌는지가
  개선 재료가 된다
