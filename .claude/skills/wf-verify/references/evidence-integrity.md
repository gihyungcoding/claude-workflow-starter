# 증거의 무결성 — "검사하지 않은 것"을 "통과"로 적지 않기

`wf-verify` Step 1·3·3.5 에서 참조한다.

이 문서가 있는 이유는 하나다. **Phase 4 는 세 번 거짓 통과를 낸 적이 있다.**
전부 같은 형태였다 — 검사가 수행되지 않았는데 결과가 `0` 으로 기록됐다.

| 사례 | 기록된 값 | 실제 |
|---|---|---|
| `constraints.yaml` 의 glob 이 실제 패키지 경로와 어긋남 | `위반 0건` | 파일 0개를 검사함 |
| 프로젝트에 린트 도구가 없음 | `{"command": "N/A", "errors": 0}` | 린트를 돌린 적 없음 |
| `architecture.md` 의 규칙이 `constraints.yaml` 에 없음 | `제약 3건 모두 통과` | 그 규칙은 검사 대상이 아니었음 |

`0` 은 **"검사했고 없었다"** 는 뜻이다. 검사하지 않았으면 `null` 이다.

---

## 1. 도구가 없을 때

```jsonc
// 옳다
"lint": { "command": null, "exit_code": null,
          "skipped_reason": "린트 도구 미도입 — CLAUDE.md 의 린트 항목이 TODO" }

// 틀렸다 — EXIT GATE 가 이것을 통과로 읽는다
"lint": { "command": "N/A", "exit_code": 0, "errors": 0 }
```

`skipped_reason` 이 있으면 `status` 는 최소 `WARN` 이다. PASS 가 될 수 없다.

**도구를 지금 도입할 수 있으면 도입하는 쪽이 낫다.** 린트가 없는 채로 Phase 3 의
"린트 error 0" 게이트를 통과시키면, 그 게이트는 이후 모든 태스크에서 무의미해진다.
도입했으면 `CLAUDE.md` 의 해당 줄도 함께 채운다.

---

## 2. 검사 대상이 0개일 때 (`no_target`)

```bash
python3 scripts/check_architecture.py --json
```

```jsonc
{ "status": "no_target", "error_count": 0,
  "no_target": ["ARCH-001"], "files_scanned": 0 }
```

`no_target` 에 ID 가 있으면 **그 제약은 죽어 있다.** `status: FAIL` 로 판정하고
`constraints.yaml` 의 `detect.paths` 를 실제 경로와 맞춘 뒤 다시 돌린다.

흔한 원인:

| 증상 | 원인 |
|---|---|
| 계층 이름이 다름 | 문서는 `controller/`, 코드는 `api/` |
| 언어별 소스 루트 누락 | `src/**` 인데 실제는 `backend/src/main/java/**` |
| 아직 만들지 않은 계층 | `frontend/**` 인데 스캐폴딩 전 |

마지막 경우는 정당하다. 그때는 제약을 지우지 말고 **`severity: warn` 으로 낮추고
사유를 `rationale` 에 적는다** — 계층이 생기면 되돌린다.

---

## 3. 산문 규칙 ↔ 기계 규칙 대조 (Step 3.5)

`constraints.yaml` 은 `architecture.md` 의 부분집합이다. 어느 산문 규칙이 아직 옮겨지지
않았는지 세지 않으면, 지켜지지 않은 규칙이 "위반 0건" 뒤에 숨는다.

`architecture.md` §2 계층 표의 **「하지 않는 것」 열**을 한 줄씩 대조한다.

```
계층 표의 「하지 않는 것」        대응 제약        상태
────────────────────────────────────────────────────
API: 비즈니스 로직               —                 검사 불가 (판단 필요)
API: DB 접근                    ARCH-001          ✓
Service: HTTP 관심사             ARCH-002          ✓
Service: SQL 직접 작성           —                 ⚠ 미인코딩
Repository: 도메인 규칙 판단      —                 검사 불가 (판단 필요)
```

세 가지 상태만 쓴다.

| 상태 | 뜻 | 다음 |
|---|---|---|
| ✓ | 기계 검사가 있다 | — |
| ⚠ 미인코딩 | 옮길 수 있는데 안 옮겼다 | Phase 5 `rule_proposals` 로 |
| 검사 불가 | 정규식으로 잡히지 않는다 | 코드 리뷰(Step 5)의 몫 |

**목표는 100% 가 아니라 갭이 보이는 것이다.**

### 이 Phase 에서 제약을 추가하지 않는다

검증 중에 검증 규칙을 바꾸면 그 변경이 검토를 거치지 않는다. `⚠ 미인코딩` 은
Phase 5 로 넘긴다.

**단 하나의 예외** — 그 산문 규칙의 위반이 **이번 변경 코드에 실제로 있으면**
`status: FAIL` 이다. 제약이 없어서 못 잡은 것이지 지켜진 것이 아니다.
그 경우 코드를 Phase 3 으로 되돌리고, 제약 추가는 그와 별개로 Phase 5 에 남긴다.
