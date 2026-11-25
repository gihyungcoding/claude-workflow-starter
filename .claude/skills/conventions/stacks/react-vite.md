# React (Vite, TypeScript) — 추천 기본값

버전 번호는 적지 않는다 — 설치할 때의 최신 안정판을 쓴다. 바꾸면 `conventions.md` 「결정 메모」에 이유를 적는다.

| id | 추천 | 검사 |
|---|---|---|
| C-LINT | ESLint(typescript-eslint, Vite 템플릿의 `eslint.config.js`) + Prettier. `tsconfig.app.json` 에 `"strict": true` 를 **명시**(템플릿 기본값에 기대지 않는다). 린트 명령은 `npm run lint && npx prettier --check .` | 린트 + `tsc --noEmit` |
| C-LAYOUT / C-FE | `src/api/`(서버 호출·응답 타입) · `src/components/ui/`(키트 공통 부품 — `docs/product/ui-components.json` 대응표) · `src/components/`(도메인 부품) · `src/pages/`(라우트 한 장) · `src/theme/`(토큰) | 제약: `pages`·`components` 는 `fetch(` 를 직접 쓰지 않는다(`api/` 만) |
| C-FE 스타일 | 색·글자·여백은 `design-tokens.css`/테마 토큰만. 숫자 색·px 하드코딩 금지(`theme/` 제외) | 제약(`DESIGN-*`, 빈 저장소라 `error`): `src/**/*.tsx` 에서 `#[0-9a-fA-F]{3,6}\b` 금지(`src/theme/**` 제외) |
| C-ERROR | API 클라이언트가 서버 에러 본문(`{code, message}`)을 한 타입(`ApiError`)으로 바꾼다. 화면은 `code` 로 분기, `message` 는 그대로 보여 주지 않는다(문구는 화면이 정한다) | 리뷰 + 기준 구현 테스트 |
| C-VALID | 폼이 있으면 zod 스키마 하나를 폼·요청 타입이 함께 쓴다. 서버 검증 오류는 같은 칸에 | 리뷰 |
| C-TEST | Vitest + Testing Library, 대상 옆 `Component.test.tsx`(페이지는 `PageName.test.tsx`), 서버는 MSW 로 흉내. 시간은 `vi.useFakeTimers` + 고정 시각 | 제약: `forbidden_path` `src/**/task[0-9]*.*` |
| C-LOG | 화면 코드에 `console.log` 를 남기지 않는다(오류 보고는 한 곳) | ESLint `no-console` |

## 설정 조각

```jsonc
// tsconfig.app.json
{ "compilerOptions": { "strict": true, "noUncheckedIndexedAccess": true } }
```

```js
// eslint.config.js — 템플릿에 더한다
rules: { 'no-console': ['error', { allow: ['error'] }] }
```

## 기준 구현 (wf-init 4.5)
- `src/api/` 함수 하나(백엔드 기준 엔드포인트 호출) + `ApiError` 변환
- 페이지 하나: 폼 하나(입력 1칸, zod), 서버 검증 오류를 같은 칸에 표시, 성공 결과 표시 — **토큰만 써서**
- `components/ui/` 공통 부품 1~2개(버튼·입력)를 실제로 쓴다 → `ui-components.json` 대응표 첫 줄
- 테스트: 페이지 테스트 1(MSW 로 성공·검증 실패), 부품 테스트 1
- 린트·`tsc --noEmit`·테스트·`check_architecture.py`(no_target 0) 통과
