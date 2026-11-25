# Spring Boot — 추천 기본값

버전 번호는 적지 않는다 — 설치할 때의 최신 안정판을 쓴다. 아래는 **추천**이다. 바꾸면 `conventions.md` 「결정 메모」에 이유를 적는다.

| id | 추천 | 검사 |
|---|---|---|
| C-TESTDB | 운영과 같은 DB 를 Testcontainers 로(Spring Boot `@ServiceConnection`). 공용 베이스 클래스 하나 | 게이트 |
| C-LINT | Spotless + google-java-format, `removeUnusedImports()`. `./gradlew spotlessCheck` 를 린트 명령으로 | `spotlessCheck` |
| C-LAYOUT | `api/`(컨트롤러·요청 DTO `api/dto`) → `service/`(서비스·**응답 DTO `service/dto`**) → `repository/` → `domain/`. 설정은 `config/` | 제약: `service`·`repository`·`domain` 은 `api` 를 import 하지 않는다 / `domain` 은 `service` 를 import 하지 않는다 |
| C-ERROR | `{code, message, details?}` record 하나(`api/dto/ErrorResponse` 가 아니라 **`common/error/`** — 설정·필터도 쓰므로). 예외 → 응답 변환은 `@RestControllerAdvice` 하나. 코드는 `UPPER_SNAKE` | 리뷰 + 기준 구현 에러 테스트 |
| C-VALID | `spring-boot-starter-validation`, 요청 본문은 `@Valid @RequestBody`, 규칙은 DTO 애너테이션. 서비스는 도메인 규칙만 | 제약: `forbidden_pattern` `^(?!.*@Valid).*@RequestBody` in `src/main/java/**/api/**` (같은 줄에 `@Valid` 가 없는 `@RequestBody`) |
| C-DATA | 쿼리는 `repository/` 만(JPA Criteria·`EntityManager` 는 서비스에서 import 금지). 트랜잭션은 서비스 메서드 | 제약 + 리뷰: **통합 테스트에 클래스 단위 `@Transactional` 을 걸지 않는다** — 커밋 시점 제약 오류를 숨긴다. 필요하면 `saveAndFlush`·정리 메서드 |
| C-TEST | 단위 `<Class>Test`, 통합 `<Feature>IntegrationTest`, 대상과 같은 패키지. 시간은 `Clock` 빈을 주입하고 테스트는 고정 `Clock`. 공용 도구는 `src/test/.../support/` | 제약: `forbidden_path` `**/*Task[0-9]*Test.java` |
| C-LOG | SLF4J(`LoggerFactory`), 레벨: 요청 실패 `warn`, 서버 오류 `error`. 토큰·비밀번호·주민번호 금지 | 제약: `System.out.print` 금지 |

## 설정 조각

```groovy
// build.gradle
plugins { id 'com.diffplug.spotless' version '<최신>' }
spotless { java { googleJavaFormat(); removeUnusedImports() } }
dependencies {
  implementation 'org.springframework.boot:spring-boot-starter-validation'
  testImplementation 'org.springframework.boot:spring-boot-testcontainers'
  testImplementation 'org.testcontainers:postgresql'   // 운영 DB 에 맞춰
}
```

```yaml
# constraints.yaml — 빈 저장소에서 error 로 시작한다. 경로는 4.5 기준 구현 뒤 no_target 0 으로 확인
# 블록 형식으로 쓴다 — check_architecture.py 의 파서는 { } 흐름 매핑을 읽지 못한다
  - id: ARCH-001
    rule: service·repository·domain 은 api 를 import 하지 않는다
    detect:
      type: forbidden_import
      paths: ["src/main/java/**/service/**", "src/main/java/**/repository/**", "src/main/java/**/domain/**"]
      pattern: "^import .*\\.api\\."
    severity: error
  - id: TEST-001
    rule: 테스트 파일 이름에 태스크 번호를 넣지 않는다
    detect:
      type: forbidden_path
      paths: ["src/test/**/*Task[0-9]*"]
    severity: error
```

## 기준 구현 (wf-init 4.5)
- 엔드포인트 하나(예: `GET /api/health` 가 아니라 **입력이 있는** 작은 것 — `POST /api/echo` 처럼 검증 규칙 하나)
- 요청 DTO + `@Valid` → 검증 실패가 `C-ERROR` 형식 400 으로
- 서비스 + 응답 DTO(`service/dto`) + 저장소 하나(실제 테이블 하나, 마이그레이션 하나)
- 테스트: 서비스 단위 테스트 1, 통합 테스트 1(Testcontainers, 검증 실패·성공), 고정 `Clock`
- `spotlessCheck`·테스트·`check_architecture.py`(no_target 0) 통과
