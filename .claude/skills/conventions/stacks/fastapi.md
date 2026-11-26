# FastAPI — 추천 기본값

버전 번호는 적지 않는다 — 설치할 때의 최신 안정판을 쓴다(`uv add`). 바꾸면 `conventions.md` 「결정 메모」에 이유를 적는다
(추천에서 벗어나면 ADR — SKILL MUST 3). 정규식은 표에 **날것으로**, `constraints.yaml` 에는 큰따옴표 안에 역슬래시 두 번으로 옮긴다.

| id | 추천 | 검사 |
|---|---|---|
| C-TESTDB | `같음` — 운영과 같은 DB 를 testcontainers-python 으로(Docker 안에서 돌리면 컨테이너 안에서 Docker 를 못 쓰니 compose 의 DB 서비스 + 테스트 전용 데이터베이스로 — 같은 DB 라 여전히 `같음`)(`PostgresContainer(driver="psycopg")`). 세션 범위 픽스처 하나(`tests/conftest.py`)가 컨테이너를 띄우고 **`alembic upgrade head`** 로 스키마를 만든다(`create_all` 은 마이그레이션을 검증하지 않는다) | 게이트 |
| C-LINT | ruff(lint + format) + 타입 검사기 하나(pyright — Node 가 없으면 mypy strict). 린트 명령 `uv run ruff check . && uv run ruff format --check . && uv run pyright`. uv 가 없으면 `pip` + requirements 로 같은 명령을 `python -m …` 로 | ruff · 타입 검사기 |
| C-LAYOUT | `app/main.py`(앱·라우터 등록) · `app/api/`(라우터, `app/api/errors.py` = 예외→응답 핸들러) → `app/services/` → `app/repositories/` → `app/models/`(ORM). 요청·응답 스키마 `app/schemas/`(pydantic). 공용: `app/db.py`(엔진·세션 팩토리) · `app/deps.py`(`Depends` 의존성 — 세션·시계) · `app/clock.py` · `app/exceptions.py`(도메인 예외 — **fastapi 를 import 하지 않는다**) | 제약: `services`·`repositories`·`models`·`schemas`·`exceptions` 는 `api` 를 import 하지 않는다(절대·상대·`from app import api` 모두) / `exceptions`·`services` 는 `fastapi` 를 import 하지 않는다 |
| C-ERROR | 본문 `{code, message, details?}`. `app/exceptions.py` 에 기반 `AppError(code, message, status)` 하나와 그 하위 클래스들(`NotFound`·`Conflict` …). `app/api/errors.py` 가 `AppError`·`RequestValidationError` 를 같은 모양으로 바꾼다. **code 는 `UPPER_SNAKE`**, 검증 실패는 HTTP 422 그대로 `code: "VALIDATION_FAILED"` + `details` 에 칸별 오류 | 리뷰 + 기준 구현 에러 테스트 |
| C-VALID | pydantic 스키마(필드 제약·`field_validator`). 라우터에서 손으로 검증하지 않는다. 도메인 규칙(중복 등)은 서비스가 `AppError` 로. **숫자만 받는 입력은 `[0-9]`** — `str.isdigit()` 는 `١٢٣`(아라비아)·`１２３`(전각)·`²` 를, `\d` 는 아라비아·전각을 받아 겉모습이 다른 값이 중복 검사를 빠져나간다(실제 실행: 기준 구현이 `isdigit()` 로 아라비아 숫자 10자리를 통과시켰다). 식별자는 정규화(공백·하이픈) 뒤 저장·비교, 경계 테스트에 비 ASCII 숫자 하나 | 제약 `forbidden_pattern` `\.isdigit\(` in `app/**` + 리뷰(`\d`) |
| C-DATA | **동기 SQLAlchemy 2 + psycopg**(비동기가 필요하면 ADR). 쿼리는 `repositories/` 만. 세션·트랜잭션은 `app/deps.py` 의 의존성 하나(요청 하나 = 트랜잭션 하나). 의존성은 `Annotated[Session, Depends(get_session)]` 로 쓴다(ruff B008 과 충돌하지 않게) | 제약: services 에서 쿼리 빌더(`select`·`insert`·`update`·`delete`·`text`) import 금지 — 한 줄 import 와 괄호로 여러 줄에 나눈 import 둘 다(ruff format 이 긴 import 를 여러 줄로 바꾼다) + 리뷰(`import sqlalchemy as sa` 뒤 `sa.select` 같은 별칭은 정규식이 못 잡는다) |
| C-TEST | `tests/<계층>/test_<모듈>.py`, 함수 `test_<무엇>_<조건>`. 서비스 단위 테스트는 저장소를 가짜로, API 통합 테스트는 testcontainers. 시간은 `app/clock.py` 의 시계를 의존성으로 주입하고 테스트에서 고정 | 제약: 파일 `forbidden_path` + 함수 `forbidden_pattern`(태스크 번호 — 아래) |
| C-LOG | 표준 `logging`(모듈마다 `getLogger(__name__)`), 토큰·비밀번호 금지 | **ruff T20**(print 금지 — `if x: print()` 도 잡는다). 정규식 제약은 두지 않는다 |

## 설정 조각

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
# 스타터의 워크플로우 도구(scripts/·.claude/)는 프로젝트 코드가 아니다 — 빼지 않으면 실제 실행에서 623건이 걸렸다
# alembic/versions 는 생성 템플릿(Union·typing.Sequence)이 UP 규칙에 걸린다
extend-exclude = ["scripts", ".claude", "alembic/versions"]
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "T20"]     # T20 = print 금지
[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = ["fastapi.Depends", "fastapi.Query"]   # Annotated 를 안 쓰는 옛 코드가 섞일 때
[tool.ruff.lint.isort]
known-third-party = ["alembic"]                 # 루트의 alembic/ 폴더 때문에 first-party 로 오분류된다

[tool.mypy]                                     # pyright 대신 mypy 를 쓸 때
strict = true
plugins = ["pydantic.mypy"]
files = ["app", "tests"]                        # alembic/env.py 는 ruff 대상, mypy 대상은 아님
```

```python
# alembic/env.py — 생성 템플릿에서 고칠 세 곳 (그대로 두면 autogenerate·연결이 안 되고 테스트 로그가 꺼진다)
from app.models import Base                      # target_metadata = None 대신
target_metadata = Base.metadata
url = config.get_main_option("sqlalchemy.url") or os.environ["DATABASE_URL"]   # alembic.ini 의 driver://… 는 비운다
fileConfig(config.config_file_name, disable_existing_loggers=False)          # 기본 True 는 앱 로거를 끈다
```

```yaml
# constraints.yaml — 블록 매핑, 인라인 리스트, 큰따옴표 정규식(역슬래시 두 번)
  - id: ARCH-001
    rule: api 밖은 api 를 import 하지 않는다 (절대·상대 import)
    severity: error
    detect:
      type: forbidden_import
      paths: ["app/services/**/*.py", "app/repositories/**/*.py", "app/models/**/*.py", "app/schemas/**/*.py", "app/exceptions.py"]
      pattern: "^\\s*(from\\s+(app\\.api|\\.+api)\\b|import\\s+app\\.api\\b|from\\s+(app|\\.+)\\s+import\\s+(.*,\\s*)?api\\b)"
  - id: ARCH-003
    rule: 도메인 예외·서비스는 웹 프레임워크를 모른다
    severity: error
    detect:
      type: forbidden_import
      paths: ["app/exceptions.py", "app/services/**/*.py"]
      pattern: "^\\s*(from|import)\\s+(fastapi|starlette)\\b"
  - id: ARCH-002
    rule: 쿼리는 저장소만 — 서비스에서 쿼리 빌더를 import 하지 않는다 (한 줄·여러 줄 import 모두)
    severity: error
    detect:
      type: forbidden_import
      paths: ["app/services/**/*.py"]
      pattern: "^\\s*from\\s+sqlalchemy(\\.\\w+)*\\s+import\\s+.*\\b(select|insert|update|delete|text)\\b|^\\s+(select|insert|update|delete|text)\\s*,?\\s*$"
  - id: TEST-001
    rule: 테스트 파일 이름에 태스크 번호를 넣지 않는다
    severity: error
    detect:
      type: forbidden_path
      paths: ["tests/**/*[Tt][Aa][Ss][Kk][0-9]*", "tests/**/*[Tt][Aa][Ss][Kk][_-][0-9]*"]   # task 바로 뒤 숫자만 — test_tasks_v2.py 는 통과
  - id: TEST-002
    rule: 테스트 함수 이름에 태스크 번호를 넣지 않는다
    severity: error
    detect:
      type: forbidden_pattern
      paths: ["tests/**/*.py"]
      pattern: "(?i)(def\\s+test_\\w*task[_-]?\\d|class\\s+test\\w*task[_-]?\\d)"
```

## 기준 구현 (wf-init 4.5)
- `app/main.py` + 라우터 하나(입력이 있는 작은 엔드포인트), pydantic 요청·응답 스키마
- 검증 실패 → 422 `VALIDATION_FAILED`(정한 본문), 도메인 규칙 실패 → `AppError` 하위 클래스 하나(예: 409 `ALREADY_EXISTS`)
- 서비스 + 저장소 + 테이블 하나(Alembic 마이그레이션 하나), `app/db.py`·`app/deps.py`·`app/clock.py`·`app/exceptions.py`·`app/api/errors.py`
- 테스트 파일 둘: 서비스 단위(`tests/services/test_<모듈>.py` — 성공·규칙 실패), API 통합(`tests/api/test_<모듈>.py` — testcontainers, 성공·검증 실패). 고정 시계
- ruff·pyright·테스트·`check_architecture.py`(위반 0, no_target 0) 통과
