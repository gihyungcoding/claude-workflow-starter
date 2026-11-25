---
name: ui-mockup
description: >-
  계획 확정 전에 화면 시안을 만든다 — 모바일(375)과 데스크톱(1280) HTML 화면, 흐름별 캔버스, 정적·렌더링 검사,
  사람의 의견 루프. Use when wf-plan 의 Refine 에서 scope.ui 가 mockup 일 때, "시안", "화면 초안",
  "와이어프레임", "목업" 요청을 받을 때, 캔버스에서 복사한 `[ui-mockup 수정 요청]` 을 붙여넣었을 때.
---

# ui-mockup — 계획을 확정하기 전에 화면으로 본다

요청의 계획(BRIEF)을 받아 **모바일 화면과 데스크톱 화면을 각각** 만들고, 사람이 캔버스에서 보고 의견을 주며
다듬은 뒤 시안을 확정한다. 시안이 계획을 바꾸면(새 화면·새 데이터) 그것은 사용자 결정으로 기록부에 올라간다.
**예쁨보다 이해와 빠짐없음이 먼저다.** 데스크톱은 모바일을 늘린 것이 아니라 따로 짠 화면이다.

> 블라인드 검증 2회(PRD 2개, 판정자 1명)에서 이 절차가 k-style-ui-ux 결과와 같거나 나았고(4개 비교 중 3개 1위),
> frontend-design 단독보다 모든 비교에서 나았다. 원칙·부품 키트·캔버스·의견 해석표는 k-style-ui-ux(MIT)에서
> 가져와 고쳤다 — `NOTICE.md`.

경로: 이 파일이 있는 폴더를 `UM`, 시안 폴더를 `OUT = workflow_design/01_brief/mockup/<REQ-ID>` 라 한다.

먼저 읽는다: `UM/references/principles.md`(원칙) · `UM/kit/COMPONENTS.md`(모바일 부품) · `UM/kit/DESKTOP.md`(데스크톱 부품) ·
`UM/references/screen-kinds.md`(화면 유형) · `UM/references/desktop.md`(데스크톱 배치·패턴) · `UM/references/checklist.md`(비평).

## MUST

1. 화면 전에 여정을 쓴다 — 요구를 바로 버튼·화면으로 바꾸지 않는다
2. 화면은 키트 클래스와 토큰만 조합한다. 인라인 style·임의 색·이모지 금지
3. 데스크톱 화면은 배치 계획(`layout.md`)을 먼저 쓰고 만든다
4. 검사(정적 + 렌더링)를 통과시킨 뒤 사람에게 보인다
5. 계획을 넓히는 시안 변경(새 화면·흐름·데이터 요소, BRIEF 완료 조건을 빼거나 가볍게 하기)은 **묻는다** — 사용자 결정

## FORBIDDEN

1. ❌ 시안 확정(`mockup.status: approved`)을 사람의 답 없이 쓰기
2. ❌ 사실 표에 없는 날짜·숫자·상태를 화면에 지어내기
3. ❌ 출처·라이선스를 기록하지 않은 사진 쓰기
4. ❌ 데스크톱 화면을 모바일 파일 복사 + 폭 넓히기로 만들기

---

## 0. 준비

```bash
OUT=workflow_design/01_brief/mockup/<REQ-ID>
mkdir -p "$OUT/screens/desktop"
python3 UM/scripts/sync_kit.py "$OUT" && cp -R UM/assets "$OUT/assets"   # 부품 파일 + kit.json(복사한 키트 버전)
```

**키트 부품 파일은 `sync_kit.py` 로만 옮긴다.** 시안 도중 부품을 더하거나 고치면 `UM/kit/` 에 고치고 다시 `sync_kit.py` —
시안 폴더의 css 를 직접 고치면 다음 요청이 그 부품을 못 쓴다. 정적 검사가 확정 전 시안의 부품 파일을 키트와 대조한다.
확정된 시안은 그 시점의 기록이라 다시 옮기지 않는다.

**토큰** — 프로젝트 정본을 먼저 본다.

| 상황 | 할 일 |
|---|---|
| `docs/product/design-tokens.css` 가 키트 변수(`--c-brand`·`--fs-body` 등)를 정의한다 | 그대로 `OUT/tokens.css` 로 복사 |
| 정본이 있지만 변수 이름이 다르다 | `design.md` §4 의 브랜드 색으로 생성하고, 시안은 **구조·위계·흐름·문구만** 본다고 리뷰 화면에 적는다 |
| 정본이 비어 있다 (첫 UI 기능) | 브랜드 색 하나를 제품 성격에서 골라 생성. 이 토큰이 `design.md` §4·§5 초안이 된다 — BRIEF `scope.design_tokens: true` |

```bash
python3 UM/kit/derive.py --brand "#RRGGBB" --tone warm|neutral|cool [--mode dark] -o "$OUT/tokens.css"
```

**표면 프리셋** — 도메인이 다르면 같은 골격이라도 표면 관례가 다르다(시험: 쇼핑·SNS·방송·배달·교육·여행 홈을 키트로 그렸더니
브랜드 색만 다른 "회색 바탕 + 흰 블록" 일곱 장이 나왔다). 참조 서비스의 표면을 보고 `screens.json` 에 `"surface"` 를 정한다 —
`kit/themes/<이름>.css` 의 머리말에 근거 서비스가 있다. 정하면 `sync_kit.py` 가 `theme.css` 로 옮기고, 모든 화면이
`components.css` 다음 줄에 `theme.css` 를 건다.

| surface | 도메인 | 표면 |
|---|---|---|
| `card-stack` (기본) | 금융·생활 유틸리티 | 회색 바탕 + 흰 둥근 블록 |
| `flat-dense` | 쇼핑·패션 | 흰 바탕, 블록 없이 구역을 띠로, 각진 사진, 촘촘하게 |
| `edge` | SNS·커뮤니티 | 흰 바탕, 카드 없이 사진을 화면 끝까지 |
| `dark-media` | 방송·영상 | 어두운 화면 — 토큰을 `--mode dark` 로. 밝은 화면 전환도 둔다 |
| `flat-banded` | 배달·장보기·여행 | 흰 바탕, 구역 사이 굵은 회색 띠, 둥근 사진 |
| `chunky` | 학습·습관 | 흰 바탕, 누르는 것마다 아래 그림자가 있는 두툼한 버튼 |

**프리셋을 지어내지 않는다.** 맞는 것이 없으면 가장 가까운 것을 쓰고 BRIEF 에 "표면 프리셋 추가 제안"으로 남긴다.
테마 파일은 키트의 테마 고리 변수만 바꾸고 바탕·블록·막대에 브랜드 계열 색을 못 쓴다(정적 검사). 렌더링 측정은
버튼 바탕이 놓인 바탕과 구분되는지, 브랜드색이 첫 화면을 30% 넘게 덮지 않는지 본다.

## 1. 여정 (`OUT/journey.md`)

입력은 BRIEF(목표·완료 조건·범위 외·결정), `product.md` 의 사용자 역할, feature 문서 §2-2 참조 서비스.

1. **사람 카드** — `product.md` 역할 이름 그대로. 사람마다: 누구(나이·성별처럼 그림에 영향을 주는 특성 포함) ·
   처음 오는 이유 · 그때 마음 · **알고 싶은 것 3~5개**(머릿속의 질문과 답이 보일 화면 id) · 성공한 순간 · 주로 쓰는 화면.
   핵심 사람 하나와 이유.
2. **여정표** — 시기(쓰기 전·중·후) × 사람 전부 × {할 일, 궁금해지는 것, **막히는 순간 → 푸는 화면**}.
3. **범위** — 다룬다 / 다루지 않는다(이미 쓰는 앱이 하는 일) / 경계. BRIEF `out_of_scope` 와 어긋나면 사용자 결정.
4. **흐름 고리** — 만들거나 신청하는 대상마다 만들기·보기·고치기(지우기·취소)·끝(결과 화면).
   - **여러 사람이 함께 쓰는 앱이면 "함께 쓰기 시작" 고리**: 시작 → 다른 사람을 부름 → 들어옴 → 연결된 첫 화면
   - **결과 화면에는 세 가지**: 무엇이 정해졌나 · 누구에게 어떻게(언제) 전해졌나 · 다음에 무슨 일이 일어나나(되돌릴 수 있나)
5. **사실 표** — 모든 날짜·시간·인원·상태 이름. 화면은 이 표만 인용한다. 2a 시나리오의 Given 데이터로도 쓴다.
   사람마다 아바타 파일(`assets/avatars/avatars.json` 에서 앱 전체 스타일 하나). 그 스타일의 그림이 모자라면 다른 스타일로 바꾼다 — 한 사람에 한 그림, 겹치지 않게.
6. **가정 로그** — 대신 정한 것과 이유.

## 2. 제품 판단 (`OUT/decisions.json`)

후보 = BRIEF 완료 조건 + 여정에서 떠오른 것. 여섯 질문으로 `keep`·`lighten`·`cut`·`later`:
핵심 갈등을 푸는가 · 이미 쓰는 앱이 하는가 · 누구에게 새 할 일이 생기나 · 없으면 무슨 일(빈도 × 피해) ·
더 가볍게 대신할 수 있나 · 어느 사람의 처음 오는 이유나 성공한 순간에 닿나.
판정 전에 반대 입장 셋(서로 가장 다른 두 사람의 하루, "30% 를 빼야 하는 PM").

**BRIEF 완료 조건을 `cut`·`lighten` 하거나 여정에서 새 기능을 `keep` 하면 BRIEF `decisions` 에 `user_challenge` 로 올리고
묻는다**(`AskUserQuestion`, 추천안 먼저). 답을 받기 전에는 그 화면을 만들지 않는다.

## 3. 모바일 화면 목록 (`OUT/screens.json`)

```json
{"title": "…", "story": {"headline": "이 앱이 갈등을 푸는 방식 한 문장(<em>강조</em>)", "summary": "2~3문장", "ideas": [{"title": "", "desc": ""}]},
 "badges": {"…": "is-brand"}, "avatar_style": "people",
 "people": [{"name": "", "why": "", "win": "", "wants": [{"q": "", "at": ["화면 id"]}], "core": true}],
 "groups": ["흐름 이름", "…"],
 "screens": [{"id": "home", "file": "screens/home.html", "title": "", "group": "흐름 이름",
   "kind": "home|list|detail|form|result|sheet", "archetype": "screen-kinds.md 의 유형",
   "purpose": "한 줄", "policies": ["화면 정책 1~3줄"], "branches": [{"to": "", "label": ""}],
   "sample": false, "desktop": "속한 데스크톱 화면 id"}],
 "desktop": [{"id": "d-home", "file": "screens/desktop/d-home.html", "title": "", "group": "", "merges": ["home"], "pattern": "", "purpose": "한 줄", "policies": []}]}
```
- **장 수가 아니라 흐름 고리로 멈춘다** — 고리가 다 차면 끝. 모바일 20장을 넘으면 요청을 나누자고 제안한다(사용자 결정).
- 같은 종류의 목록 행 여러 개가 예시 화면 하나로 이어지면 그 화면에 `"sample": true` 와 정책 한 줄("목록의 다른 행도 이 모양").
- 화면을 벗어나지 않고 고르거나 확인하는 일이면 `kind: "sheet"`.
- **1차는 기본 화면 + 결과 화면**. 밖으로 내보내는 행동·한 번 누르는 요청은 `<id>--done`. 오류·확인·빈 화면은 §7.
- 배지는 뜻마다 다른 색, 앱 전체에 하나의 표.

## 4. 데스크톱 배치 계획 (`OUT/layout.md`)

`references/desktop.md` §1 을 그대로 — 묶기 → 도메인에서 구조 끌어내기 → 화면마다 ASCII → "모바일을 늘린 것과 무엇이 다른가".
모든 모바일 화면이 정확히 하나의 데스크톱 화면에 속한다. 결과를 `screens.json` 의 `desktop` 에 적는다.

**데이터 묶음** — 두 화면 이상에 나오는 데이터 묶음(금액·기한·계좌, 예매 요약처럼)은 화면을 만들기 **전에** `layout.md` 에 정한다.
부품 하나의 모양은 키트가 지키지만 "이 묶음을 어떤 부품들로" 는 정하지 않으면 화면마다 갈린다(시험 실행: 같은 금액이 목록 행·
타임라인 글·숫자 카드로 넷).

```markdown
## 데이터 묶음

| 묶음 | 항목(순서) | 모바일 | 데스크톱 | 왜 이 모양 |
|---|---|---|---|---|
| `payment` | amount, deadline, account | 금액 크게 + 기한 칩 + 계좌 행 | 같은 묶음을 본문 첫 블록에 | 금액=얼마, 기한=언제까지(행동을 재촉), 계좌=어디로 — 성격이 달라 부품도 다르다 |
```

- 화면에서 묶음을 감싼 요소에 `data-bundle="payment"`, 항목마다 `data-item="amount"`. 정적 검사가 같은 너비의 화면끼리
  항목 순서(표 순서)와 항목의 부품(class)이 같은지 대조한다. 상태 화면에서 항목이 빠지는 것은 된다(순서는 유지)
- **성격이 다른 항목을 같은 부품으로 나란히 두지 않는다** — 금액과 기한을 같은 크기 숫자 카드 둘로 두면 무엇이 먼저인지 모른다

## 5. 빌드

- **모바일** `OUT/screens/<id>.html` — `kit/COMPONENTS.md` 뼈대(375). 화면 유형의 주인공이 첫 화면에서 가장 크게(`data-anchor`),
  그 위에 지금 상황 한 문장(`hero`). 사람 카드의 알고 싶은 것의 답을 첫 화면에 크게 — 질답지로 만들지 않는다.
- **데스크톱** `OUT/screens/desktop/<id>.html` — `kit/DESKTOP.md` 뼈대(1280) + 모바일 부품. `layout.md` 의 ASCII 대로.
- 누르는 것은 실제 파일 `href` / `data-back` / `data-stay="바뀐 뒤 안내 한 문장"`. 모바일은 모바일끼리, 데스크톱은 데스크톱끼리.
- **키트에 없는 부품을 화면 안 `<style>` 로 만들지 않는다** — 모바일과 데스크톱이 따로 만들어 어긋난다(정적 검사가 경고). 좌석·자리는
  `kit/COMPONENTS.md` 「칸 고르기」. 정말 없으면 한 화면에서 만들고 같은 흐름의 모든 화면이 같은 클래스를 쓰게 하고, 키트에 더하자고 제안한다
- 데스크톱은 `kit/DESKTOP.md` 「뼈대」「버튼」을 지킨다 — 머리는 두 열 위, 정해진 폭, 상태 화면은 기본 화면 복사, 버튼 한 줄·`btn-row`
- 사물은 `assets/fluent/` 일러스트, 사람은 아바타. **사진은 사용자가 준 것이나 출처·라이선스를 `credits.json`
  (`[{slot, file, author, license, url}]`)에 적을 수 있는 것만** — 없으면 사진 자리를 쓰지 않는다.

화면이 많으면 흐름별로 서브에이전트에 나눠 맡겨도 된다(각자 자기 파일만). 각자에게 원칙 전문, 부품 문서, 사실 표, 맡은 화면 항목을 준다.

## 6. 검사 (통과할 때까지, 수정은 흐름별로 한꺼번에)

```bash
python3 UM/scripts/check_mockup.py "$OUT"          # 정적: h1·주 버튼·인라인 style·색 값·이모지·링크·이미지·데스크톱 묶음
python3 UM/scripts/build_canvas.py "$OUT"          # 캔버스 index.html + foundation·components + audit.html
python3 UM/scripts/prune_assets.py "$OUT"          # 화면이 쓰지 않는 그림을 지운다 (커밋 크기)
```

렌더링 검사는 브라우저가 필요하다. 시안 폴더를 띄우고(백그라운드) 브라우저 패널에서 `audit.html` 을 연다:

```bash
python3 -m http.server 8790 --bind 127.0.0.1 --directory "$OUT"
```

`window.__audit` 의 결과를 `OUT/audit.json` 으로 저장한다. 대비 AA · 터치(모바일 44px, 데스크톱 24px) · 가로 넘침 ·
글자 크기 7종·굵기 3종·서체 2종 이하 · 4px 격자 95% · radius 4종 · 그림자 3종 · h1 1개 · 주 버튼 1개 · 데스크톱 한 줄 80자.
그다음 `references/checklist.md` 의 P0·P1 을 화면마다 보고 고친다.

## 7. 사람 검토 — 캔버스와 의견

캔버스(`http://127.0.0.1:8790/index.html`)를 브라우저 패널에 연다. 캔버스는 흐름별 줄(모바일 줄, 그 아래 데스크톱 줄)·
갈래 화살표·화면별 정책·정한 것과 뺀 것을 보여 주고, 화면을 누르면 크게 보며 직접 눌러 볼 수 있다.
사람은 크게 보기의 **의견**으로 요소를 골라 적고 **의견 복사**로 붙여넣는다 → `references/feedback.md` 대로 그 요소만 고친다.

**의견마다 계획 영향을 분류해 BRIEF `mockup.feedback` 에 남긴다** — `visual` · `state` · `screen` · `data`.
`screen`·`data` 는 범위가 바뀌므로 고치기 전에 묻는다.

한 회차가 끝나면 `mockup.rev` 를 올리고 `AskUserQuestion` 으로 묻는다:

| 선택지 | 다음 |
|---|---|
| 시안 확정 | `mockup.status: approved` · `mockup.coverage` (완료 조건 → 화면 id) 기록 |
| 의견 계속 | 캔버스에서 의견을 받아 고친다 |
| 상태 화면까지 | 오류·확인·빈 화면·진행 중을 더한다 — 완료 조건에 오류 경우가 있으면 추천. 2a 시나리오가 이 상태들이다 |

상태 화면 규칙: 목록 + 첫 사용 → `empty` · 폼 → `error`(같은 요소에서 문제 칸만) · 되돌릴 수 없는 행동·중복 경고 → `confirm` ·
지켜봐야 하는 긴 작업 → `progress`. 화면당 기본 포함 3개 이하. 기본 화면 파일을 복사해 바뀐 부분만 고친다.

팀과 함께 보려면 사용자가 원할 때 비공개 Artifact 로 발행한다(시안 폴더 전체 — `index.html` 이 진입점).

## 8. 끝 — BRIEF 에 남기는 것

**앞 요청의 화면을 대체하면** 그 화면에 `"replaces": ["REQ-001/seat"]`(이름이 같으면 생략 — 같은 id 는 나중 요청이 이긴다).
워크플로우 전부터 있던 시안 폴더의 화면이면 `"out:seat"`. 상태 화면은 따로 적는다(남겨야 할 상태 화면이 있을 수 있다).
확정한 뒤 앱 전체 캔버스를 다시 만든다:

```bash
python3 UM/scripts/build_app_canvas.py [--base out]    # → workflow_design/01_brief/mockup/index.html · app-screens.json
```

화면마다 가장 최근 정본 하나를 모은다. 사람에게 "지금 앱의 화면"은 이것을 보여 준다.

**프론트 부품 대응** — 시안이 쓰는 키트 부품마다 프론트 공통 부품이 있는지 대조한다:

```bash
python3 UM/scripts/ui_map.py "$OUT" [--desktop] [--init]   # 대응표 docs/product/ui-components.json
```

대응이 없는 부품(`null`)은 이 요청의 Frontend 태스크가 공통 부품으로 만든다 — `wf-plan` Dispatch 의 `tasks` 가 태스크 설명에 넣는다.

- `mockup`: `status`, `rev`, `coverage`, `feedback`, (발행했으면) `artifact_url`
- 시안이 만든 결정(제품 판단의 사용자 결정, 의견의 `screen`·`data`)은 BRIEF `decisions` 에
- 화면에 보이는 데이터 요소 목록을 Eng 리뷰에 넘긴다 — 백엔드 DTO 에 없는 필드는 새 필드(범위 확대)

커밋 대상: `screens.json` · `journey.md` · `decisions.json` · `layout.md` · `audit.json` · `screens/` · css · `palette.js` ·
`assets/`(정리 후) · `index.html` · `foundation.html` · `components.html` · `audit.html`. 이후 Phase 3 의 시안 대조와 Phase 4 의
화면 확인이 이 폴더를 기준으로 한다 — 같은 `audit.html` 측정을 실제 앱에도 쓴다.

## 붙여넣은 `[ui-mockup 수정 요청]` 이 오면

새로 만들지 않는다. `references/feedback.md` 대로 적힌 화면의 그 요소만 고치고, §6 검사를 다시 돌리고, 영향을 분류해 남긴다.
