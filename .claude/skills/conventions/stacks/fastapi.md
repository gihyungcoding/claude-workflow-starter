# FastAPI — 추천 기본값

버전 번호는 적지 않는다 — 설치할 때의 최신 안정판을 쓴다(`uv add`). 바꾸면 `conventions.md` 「결정 메모」에 이유를 적는다.

| id | 추천 | 검사 |
|---|---|---|
| C-TESTDB | 운영과 같은 DB 를 testcontainers-python 으로. 세션 범위 픽스처 하나(`tests/conftest.py`) | 게이트 |
| C-LINT | ruff(lint + format), 타입은 pyright 또는 mypy 중 하나. 린트 명령 `uv run ruff check . && uv run ruff format --check .` | ruff |
| C-LAYOUT | `app/api/`(라우터) → `app/services/` → `app/repositories/` → `app/models/`(ORM). 요청·응답 스키마는 `app/schemas/`(pydantic) | 제약: `services`·`repositories`·`models` 는 `app.api` 를 import 하지 않는다 |
| C-ERROR | `{code, message, details?}` — 도메인 예외 클래스 하나 계층 + `app/errors.py` 의 exception handler 가 응답으로. `RequestValidationError` 도 같은 모양으로 바꾼다 | 리뷰 + 기준 구현 에러 테스트 |
| C-VALID | pydantic 스키마(필드 제약·`field_validator`). 라우터에서 손으로 검증하지 않는다 | 리뷰 |
| C-DATA | 쿼리는 `repositories/` 만, 세션·트랜잭션은 의존성(`Depends`) 하나에서 | 제약: `services` 에서 `sqlalchemy` 의 `select` import 금지 |
| C-TEST | `tests/<계층>/test_<모듈>.py`, 함수 `test_<무엇>_<조건>`. 시간은 주입한 시계(또는 freezegun) | 제약: `forbidden_path` `tests/**/test_task[0-9]*` |
| C-LOG | 표준 `logging`(모듈마다 `getLogger(__name__)`), `print(` 금지, 토큰·비밀번호 금지 | 제약: `forbidden_pattern` `^\s*print\(` in `app/**` |

## 설정 조각

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "T20"]   # T20 = print 금지
```

## 기준 구현 (wf-init 4.5)
- 라우터 하나(입력이 있는 작은 엔드포인트), pydantic 요청·응답 스키마
- 검증 실패가 `C-ERROR` 형식 422→정한 코드로
- 서비스 + 저장소 + 테이블 하나(마이그레이션 하나 — Alembic)
- 테스트: 서비스 단위 1, API 통합 1(testcontainers, 성공·검증 실패), 고정 시계
- ruff·테스트·`check_architecture.py`(no_target 0) 통과
