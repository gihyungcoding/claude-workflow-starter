---
name: architecture-doc
description: >-
  아키텍처 문서(architecture.md)와 검사 가능한 제약(constraints.yaml)을 작성·갱신한다.
  산문 규칙에서 기계가 검증할 수 있는 제약을 뽑아내는 것이 핵심이다. Use when 시스템 구조를
  정하거나 문서화할 때, 계층·모듈 경계를 정의할 때, 아키텍처 제약을 추가할 때, 또는 Phase 5
  회고가 아키텍처 drift 를 지적했을 때.
---

# 아키텍처 문서

두 파일을 함께 관리한다. **역할이 다르고, 섞으면 둘 다 쓸모가 줄어든다.**

| 파일 | 성격 | 읽는 쪽 |
|---|---|---|
| `docs/architecture/architecture.md` | 산문 — 구조, 계층, 흐름, 왜 이렇게 나눴는가 | 사람, Phase 1 |
| `docs/architecture/constraints.yaml` | 기계 검사 가능한 제약만 | `check_architecture.py`, Phase 4 |

## MUST

1. 의존 방향을 명시한다 — 무엇이 무엇을 호출해도 되고 안 되는지
2. 계층마다 **"하지 않는 것"** 을 쓴다. 그것이 경계를 만든다
3. 산문 규칙 중 검사 가능한 것을 `constraints.yaml` 로 옮긴다
4. 제약을 추가하면 `check_architecture.py` 로 **실제로 걸리는지 확인**한다
5. 큰 결정은 ADR 로 빼고 여기서는 링크만 남긴다

## FORBIDDEN

1. ❌ **검사할 수 없는 규칙을 `constraints.yaml` 에 넣기** — 검사되지 않으면서 검사되는 것처럼 보인다
2. ❌ 검증하지 않은 제약을 커밋하기 — 정규식이 아무것도 안 잡거나 모든 걸 잡을 수 있다
3. ❌ 이상적인 구조를 쓰고 현실과 다른 채로 두기 — `## 7. 알려진 부채` 에 적는다
4. ❌ mermaid·이미지 다이어그램 — ASCII 로 쓴다
5. ❌ 결정의 이유를 산문으로 길게 쓰기 — ADR 로 뺀다

---

## architecture.md 작성

`docs/architecture/architecture.md` 의 TODO 를 채운다.

### 1. 전체 구조

ASCII 로 그린다. **화살표 방향이 의존 방향**이다.

```
┌──────────┐     ┌──────────┐     ┌──────────────┐     ┌────┐
│  Client  │────►│   API    │────►│   Service    │────►│ DB │
└──────────┘     └──────────┘     └──────┬───────┘     └────┘
                                         │
                                  ┌──────▼───────┐
                                  │  Repository  │
                                  └──────────────┘
```

### 2. 계층

각 계층의 **"하지 않는 것"** 이 가장 중요한 열이다. 그것이 경계다.

| 계층 | 책임 | 하지 않는 것 | 위치 |
|---|---|---|---|
| API | 요청 검증, 응답 직렬화 | 비즈니스 로직, DB 접근 | `src/api/` |
| Service | 비즈니스 규칙, 트랜잭션 경계 | HTTP 관심사 | `src/services/` |
| Repository | 데이터 접근 | 비즈니스 판단 | `src/repositories/` |

### 3. 의존 방향

```
허용:  API ──► Service ──► Repository ──► DB
금지:  API ──╳─► Repository        (트랜잭션 경계가 흐려진다)
       Service ──╳─► API           (역방향 의존)
```

여기서 "금지"로 적은 것 중 **검사 가능한 것을 다음 단계에서 제약으로 옮긴다.**

### 4~7

데이터 흐름(읽기·쓰기 구분), 외부 의존(실패하면 어떻게 되는지 포함),
이 구조를 고른 이유(ADR 링크), 알려진 부채.

부채를 숨기지 않는다. 현재 구조가 이상적이지 않은 지점과 그 이유를 적으면
Phase 1이 "왜 이렇게 되어 있지?"에서 시간을 쓰지 않는다.

---

## constraints.yaml — 제약 뽑아내기

산문 규칙을 하나씩 보며 묻는다: **"이걸 파일 내용만 보고 확인할 수 있나?"**

| 산문 규칙 | 검사 가능? | 어디로 |
|---|---|---|
| "API 는 Repository 를 직접 호출하지 않는다" | ✅ import 검사 | `constraints.yaml` |
| "도메인은 프레임워크에 의존하지 않는다" | ✅ import 검사 | `constraints.yaml` |
| "모든 API 모듈에 테스트가 있다" | ✅ 경로 존재 | `constraints.yaml` |
| "서비스는 응집도가 높아야 한다" | ❌ | `architecture.md` 에만 |
| "이름은 의도를 드러내야 한다" | ❌ | `architecture.md` 에만 |

### 작성

```yaml
constraints:
  - id: ARCH-001                       # 순번. 재사용하지 않는다
    rule: "API 계층은 리포지토리를 직접 호출하지 않는다 (서비스를 거친다)"
    rationale: "트랜잭션 경계를 서비스 계층에 고정하기 위함"
    adr: ADR-0002                      # 근거가 된 결정 (없으면 생략)
    detect:
      type: forbidden_import
      paths: ["src/api/**/*.py"]
      pattern: "^\\s*from .*repositories.* import"
    severity: error
```

`detect.type`

| type | 위반 조건 |
|---|---|
| `forbidden_import` | `paths` 의 파일에서 `pattern` 이 발견되면 |
| `forbidden_pattern` | `forbidden_import` 와 같다 — import 가 아닌 것(색상 리터럴, 매직 치수)을 금지할 때 이름으로 구분한다 |
| `forbidden_path` | `paths` 에 해당하는 파일이 존재하면 |
| `required_path` | `paths` 에 해당하는 파일이 하나도 없으면 |

`severity`

- `error` — Phase 4 가 `status: FAIL` 로 판정. 다음 Phase 진입 불가
- `warn` — 경고만 남기고 진행

새 제약은 `warn` 으로 시작해서, 기존 코드가 통과하는 것을 확인한 뒤 `error` 로 올리는
편이 안전하다. 처음부터 `error` 로 넣으면 무관한 태스크가 줄줄이 막힌다.
**`warn` 으로 시작하면 `promote_after: TASK-NNN` 을 반드시 적는다** — 없으면 `check_architecture.py` 가 경고하고, 그 태스크가 done 이 되면 승격 기한이 지났다고 알린다.

### ★ 반드시 검증한다

```bash
# 1. 제약이 실제로 위반을 잡는가 — 일부러 위반하는 파일을 만들어 본다
python3 scripts/check_architecture.py --id ARCH-001

# 2. 기존 코드가 통과하는가
python3 scripts/check_architecture.py
```

정규식이 아무것도 안 잡거나(오타) 모든 걸 잡으면(너무 넓음) 제약이 무의미하다.
**검증하지 않은 제약은 커밋하지 않는다.**

### 이 검사의 한계를 안다

정규식 매칭이다. 주석 안의 문자열도 잡고, 동적 import 는 못 잡는다.
완벽한 검사가 아니라 **명백한 위반을 싸게 잡는 장치**다. 이 한계를 사용자에게도 알린다.

---

## 갱신할 때

Phase 5 회고가 drift 를 지적했거나 구조가 실제로 바뀐 경우다.

1. `architecture.md` 를 고치고 **최종 갱신** 날짜를 바꾼다
2. 구조 변경이 결정을 동반했으면 `/wf-adr` 로 ADR 을 남긴다
3. 새로 검사 가능해진 규칙이 있으면 `constraints.yaml` 에 추가하고 검증한다
4. 더 이상 유효하지 않은 제약은 **지우지 말고** `severity: warn` 으로 낮추거나,
   지운다면 어느 ADR 때문인지 커밋 메시지에 남긴다
