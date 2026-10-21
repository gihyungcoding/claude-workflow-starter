#!/usr/bin/env python3
"""Phase 4 VERIFY 의 뿌리 원인(root_causes) 기록을 검증한다.

왜 필요한가
-----------
Phase 4 가 결함을 찾아 Phase 3 으로 돌려보내고, 고친 뒤 다시 들어왔더니 **같은 뿌리의 다른
입력**이 또 나오는 일이 반복됐다. TASK-009 는 이메일 정규화 길이 오보(409)를 고쳤더니 다음
라운드에 name 의 NUL 문자가 같은 409 를 냈다 — 둘 다 "모든 DataIntegrityViolationException 을
UNIQUE 위반으로 취급하는 catch" 가 뿌리였다. 증상 하나를 고치고 뿌리를 남기면 되돌아가는
횟수는 증상 수만큼 늘고, 되돌아갈 때마다 독립검증·HITL·Red·Green·리뷰를 다시 돈다.

그래서 FAIL 을 낼 때 리뷰어가 증상 목록이 아니라 **뿌리와 같은 뿌리의 변종**을 함께 적고
프로브로 재현 여부를 확인하게 한다. 이 스크립트는 그 기록이 *남아 있는지*를 본다.

검사하는 것
-----------
- `root_causes` 의 구조 (id, 요약, 변종 목록 또는 변종이 없는 사유, 변종마다 출처·프로브 결과)
- FAIL 이면 `root_causes` 가 비어 있지 않다 — 결함이 있다는 판정에 뿌리가 없을 수 없다
- FAIL 이 아니면 **재현된 변종은 모두 해소(resolved)** 되어 있고 근거가 있다
- 이전에 커밋된 VERIFY 에 있던 뿌리·변종이 지금 파일에서 **사라지지 않았다** —
  불리한 항목을 지워 PASS 로 가는 길을 막는다
- **이전 라운드에서 `not_probed` 였던 변종은 이번 라운드에 프로브되어 있다.** 프로브하지
  않은 채 넘긴 변종이 다음 FAIL 이 됐다 — TASK-009 3차에 "password 의 짝 없는 서로게이트" 를
  "영향 없다고 판단" 하고 건너뛰었고, 그것이 4차 FAIL(로그인 비밀번호 200)이었다.
  Phase 3 가 그 변종의 테스트를 쓰는 것이 프로브다. `not_reproduced` 로 바꾸려면 그것을 보인
  테스트를 `evidence` 에 적는다

"이전 라운드" 는 그 VERIFY 버전 이후 이 브랜치에서 소스가 바뀐 경우다. Phase 4 는 코드를
고치지 않으므로 소스 변경은 Phase 2b·3 을 거쳤다는 뜻이다. 기준 브랜치를 병합해 들어온
변경은 세지 않는다 (first-parent, 병합 커밋 제외).

사용
----
    python3 scripts/check_root_causes.py --task-id TASK-001
    python3 scripts/check_root_causes.py --task-id TASK-001 --json

exit code
---------
    0  기록에 문제 없음
    1  위반 있음
    2  인자 오류 / VERIFY 를 읽을 수 없음

이 검사가 못 잡는 것
-------------------
**기록의 질은 보지 않는다.** 뿌리 요약이 그럴듯한지, 변종 후보가 충분한지, 프로브가 실제로
실행됐는지는 알 수 없다. 형식을 채우는 것만으로 통과할 수 있고, 그래서 `not_probed`(프로브하지
못함)와 `later`(이후 라운드에서 뒤늦게 나온 변종 — 스윕이 놓친 것)를 숨기지 않고 센다.
HITL#3 요약과 Phase 5 회고가 그 숫자를 본다.
이력 대조는 변종의 `case` 문자열이 같은지로 한다. 라운드를 넘길 때 문구를 다시 쓰면 지운 것으로
읽히므로 그대로 옮겨 적는다.
라운드 판정은 커밋된 소스 변경에 기댄다. Phase 4 중에 코드를 고치고 커밋하면(금지된 일이다)
같은 라운드가 이전 라운드로 읽힌다.
**수정이 뿌리를 고쳤는지**(공통 지점인지, 필드마다 따로인지)는 보지 않는다. 그것은 리뷰어가
재검증 때 본다 (→ references/root-cause-sweep.md 「뿌리를 고친다는 것」).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _utils import (  # noqa: E402
    artifact_path,
    is_source_file,
    is_valid_task_id,
    load_json,
    repo_root,
    task_id_error,
)

RC_ID_RE = re.compile(r"^RC-\d+$")

#: found     리뷰어가 보고한 결함 그 자체
#: predicted 같은 뿌리라서 있을 법하다고 첫 라운드에 미리 적은 변종
#: later     이후 라운드에서 뒤늦게 나온 변종 — 첫 라운드의 스윕이 놓친 것
ORIGINS = ("found", "predicted", "later")

#: reproduced     프로브로 실제 재현했다
#: not_reproduced 프로브했으나 재현되지 않았다
#: not_probed     프로브하지 못했다 (사유 필수)
PROBES = ("reproduced", "not_reproduced", "not_probed")


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def validate_record(data: dict) -> tuple[list[str], dict]:
    """VERIFY 한 건의 root_causes 를 검사한다. (위반 목록, 집계)"""
    problems: list[str] = []
    stats = {
        "root_causes": 0,
        "variants": 0,
        "by_origin": {o: 0 for o in ORIGINS},
        "reproduced": 0,
        "unresolved_reproduced": 0,
        "not_probed": 0,
    }
    status = data.get("status")
    raw = data.get("root_causes")

    if raw is None:
        if status == "FAIL":
            problems.append("status 가 FAIL 인데 root_causes 가 없다 — 결함의 뿌리와 변종을 적는다")
        return problems, stats
    if not isinstance(raw, list):
        problems.append("root_causes 는 배열이어야 한다")
        return problems, stats
    if status == "FAIL" and not raw:
        problems.append("status 가 FAIL 인데 root_causes 가 비어 있다 — 결함의 뿌리와 변종을 적는다")

    seen_ids: set[str] = set()
    for i, rc in enumerate(raw):
        where = f"root_causes[{i}]"
        if not isinstance(rc, dict):
            problems.append(f"{where} 가 객체가 아니다")
            continue
        rc_id = rc.get("id")
        label = rc_id if isinstance(rc_id, str) else where
        stats["root_causes"] += 1

        if not isinstance(rc_id, str) or not RC_ID_RE.match(rc_id):
            problems.append(f"{where}: id 가 RC-숫자 형식이 아니다: {rc_id!r}")
        elif rc_id in seen_ids:
            problems.append(f"{label}: id 가 중복된다")
        else:
            seen_ids.add(rc_id)

        if not _text(rc.get("summary")):
            problems.append(f"{label}: summary 가 비어 있다")
        rnd = rc.get("found_in_round")
        if not isinstance(rnd, int) or isinstance(rnd, bool) or rnd < 1:
            problems.append(f"{label}: found_in_round 는 1 이상의 정수여야 한다: {rnd!r}")

        variants = rc.get("variants")
        if variants is None:
            variants = []
        if not isinstance(variants, list):
            problems.append(f"{label}: variants 는 배열이어야 한다")
            variants = []
        if not variants and not _text(rc.get("no_variants_reason")):
            problems.append(
                f"{label}: 변종이 없으면 no_variants_reason 에 같은 뿌리의 다른 입력을 "
                "검토했으나 없는 이유를 적는다"
            )

        cases: set[str] = set()
        for j, v in enumerate(variants):
            vw = f"{label}.variants[{j}]"
            if not isinstance(v, dict):
                problems.append(f"{vw} 가 객체가 아니다")
                continue
            stats["variants"] += 1
            case = _text(v.get("case"))
            if not case:
                problems.append(f"{vw}: case 가 비어 있다")
            elif case in cases:
                problems.append(f"{vw}: case 가 중복된다 — {case!r}")
            cases.add(case)

            origin, probe = v.get("origin"), v.get("probe")
            if origin not in ORIGINS:
                problems.append(f"{vw}: origin 은 {list(ORIGINS)} 중 하나여야 한다: {origin!r}")
            else:
                stats["by_origin"][origin] += 1
            if probe not in PROBES:
                problems.append(f"{vw}: probe 는 {list(PROBES)} 중 하나여야 한다: {probe!r}")
            if probe == "not_probed":
                stats["not_probed"] += 1
                if not _text(v.get("reason")):
                    problems.append(f"{vw}: 프로브하지 못했으면 reason 에 사유를 적는다")

            resolved = v.get("resolved")
            if resolved not in (None, True, False):
                problems.append(f"{vw}: resolved 는 true/false/null 이어야 한다: {resolved!r}")
            if resolved is True and not _text(v.get("evidence")):
                problems.append(f"{vw}: resolved 인데 evidence 가 없다 — 어떤 테스트가 이것을 막는지 적는다")

            if probe == "reproduced":
                stats["reproduced"] += 1
                if resolved is not True:
                    stats["unresolved_reproduced"] += 1
                    # FAIL 은 아직 고치기 전이라 정상이다. 그 밖의 판정은 안 된다.
                    if status != "FAIL":
                        problems.append(
                            f"{vw}: 재현된 변종이 해소되지 않았다 — {case!r}. "
                            "고치고 resolved: true 와 evidence 를 적거나, status 를 FAIL 로 둔다"
                        )
    return problems, stats


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], capture_output=True, text=True, cwd=repo_root(), check=True
        )
        return out.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def committed_versions(path: Path) -> list[tuple[str, dict]]:
    """이전에 커밋된 같은 파일의 (커밋, 내용). root_causes 가 배열인 버전만."""
    try:
        rel = str(path.resolve().relative_to(repo_root().resolve()))
    except ValueError:
        return []
    log = _git("log", "--format=%H", "--", rel)
    if not log:
        return []
    versions = []
    for sha in log.split():
        blob = _git("show", f"{sha}:{rel}")
        if blob is None:
            continue
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and isinstance(data.get("root_causes"), list):
            versions.append((sha, data))
    return versions


def _variants(data: dict):
    """(RC id, case, variant) 를 차례로."""
    for rc in data.get("root_causes") or []:
        if not (isinstance(rc, dict) and isinstance(rc.get("id"), str)):
            continue
        for v in rc.get("variants") or []:
            if isinstance(v, dict) and _text(v.get("case")):
                yield rc["id"], _text(v.get("case")), v


def earlier_records(path: Path) -> list[dict[str, set[str]]]:
    """이전에 커밋된 같은 파일의 root_causes. 각 버전은 {RC id: {case, ...}}."""
    versions = []
    for _, data in committed_versions(path):
        snapshot: dict[str, set[str]] = {}
        for rc in data["root_causes"]:
            if isinstance(rc, dict) and isinstance(rc.get("id"), str):
                snapshot.setdefault(rc["id"], set())
        for rc_id, case, _ in _variants(data):
            snapshot[rc_id].add(case)
        if snapshot:
            versions.append(snapshot)
    return versions


def source_changed_since(sha: str) -> bool:
    """그 커밋 이후 이 브랜치에서 소스가 바뀌었나 — 그렇다면 그 VERIFY 는 이전 라운드다.

    기준 브랜치를 병합해 들어온 변경은 이 태스크의 라운드가 아니므로 세지 않는다.
    """
    out = _git("log", "--first-parent", "--no-merges", "--format=", "--name-only", f"{sha}..HEAD")
    if not out:
        return False
    return any(is_source_file(f) for f in out.splitlines() if f.strip())


def previous_round_unprobed(path: Path) -> set[tuple[str, str]]:
    """이전 라운드의 VERIFY 에서 not_probed 였던 (RC id, case)."""
    keys: set[tuple[str, str]] = set()
    for sha, data in committed_versions(path):
        if not source_changed_since(sha):
            continue  # 같은 라운드 안에서 다시 커밋한 것
        for rc_id, case, v in _variants(data):
            if v.get("probe") == "not_probed":
                keys.add((rc_id, case))
    return keys


def unprobed_followup_problems(data: dict, keys: set[tuple[str, str]]) -> list[str]:
    """이전 라운드에서 프로브하지 않은 변종은 이번 라운드에 프로브되어 있어야 한다."""
    current = {(rc_id, case): v for rc_id, case, v in _variants(data)}
    problems = []
    for rc_id, case in sorted(keys):
        v = current.get((rc_id, case))
        if v is None:
            continue  # 사라진 변종은 carried_forward_problems 가 이미 잡는다
        probe = v.get("probe")
        if probe == "not_probed":
            problems.append(
                f"{rc_id}: 이전 라운드에서 프로브하지 않은 변종이 아직 not_probed 다 — {case!r}. "
                "Phase 3 가 이 변종의 테스트를 썼어야 한다 (테스트가 프로브다)"
            )
        elif probe == "not_reproduced" and not _text(v.get("evidence")):
            problems.append(
                f"{rc_id}: 이전 라운드에서 프로브하지 않은 변종을 not_reproduced 로 바꿨는데 "
                f"evidence 가 없다 — {case!r}. 재현되지 않음을 보인 테스트를 적는다"
            )
    return problems


def carried_forward_problems(data: dict, earlier: list[dict[str, set[str]]]) -> list[str]:
    """이전 커밋에 있던 뿌리·변종이 지금 없으면 위반. 불리한 항목을 지워 통과하는 길을 막는다."""
    current: dict[str, set[str]] = {}
    for rc in data.get("root_causes") or []:
        if isinstance(rc, dict) and isinstance(rc.get("id"), str):
            current[rc["id"]] = {
                _text(v.get("case"))
                for v in (rc.get("variants") or [])
                if isinstance(v, dict)
            }
    problems, reported = [], set()
    for snapshot in earlier:
        for rc_id, cases in snapshot.items():
            if rc_id not in current:
                if (rc_id, None) not in reported:
                    reported.add((rc_id, None))
                    problems.append(
                        f"{rc_id}: 이전 라운드에 기록된 뿌리가 사라졌다 — 해소했어도 지우지 않고 "
                        "resolved 로 남긴다"
                    )
                continue
            for case in sorted(cases - current[rc_id]):
                if (rc_id, case) not in reported:
                    reported.add((rc_id, case))
                    problems.append(
                        f"{rc_id}: 이전 라운드의 변종이 사라졌다 — {case!r}. "
                        "문구를 바꾸지 말고 그대로 옮겨 적는다"
                    )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not is_valid_task_id(args.task_id):
        print(task_id_error(args.task_id), file=sys.stderr)
        return 2

    path = artifact_path(args.task_id, "4")
    data, err = load_json(path) if path else (None, "경로 계산 실패")
    if err or not isinstance(data, dict):
        print(f"VERIFY 를 읽을 수 없다: {err or '객체가 아니다'}", file=sys.stderr)
        return 2

    problems, stats = validate_record(data)
    problems += carried_forward_problems(data, earlier_records(path))
    problems += unprobed_followup_problems(data, previous_round_unprobed(path))
    status = data.get("status")

    if args.json:
        print(json.dumps({"task_id": args.task_id, "verify_status": status,
                          "ok": not problems, "problems": problems, "stats": stats},
                         ensure_ascii=False, indent=2))
        return 1 if problems else 0

    print(f"뿌리 원인 점검 — {args.task_id}  (VERIFY status: {status})")
    print()
    for p in problems:
        print(f"  ✗ {p}")
    if stats["root_causes"] == 0 and not problems:
        # '결함이 없었다'는 뜻이 아니다 — 이 필드가 생기기 전의 VERIFY 도 같은 모양이다
        print("  – 뿌리 원인 기록 없음 (결함이 없었다는 뜻이 아니라 기록이 없다는 뜻이다)")
    elif stats["root_causes"]:
        o = stats["by_origin"]
        print(
            f"  뿌리 {stats['root_causes']}건 · 변종 {stats['variants']}건 "
            f"(found {o['found']} · predicted {o['predicted']} · later {o['later']}) · "
            f"재현 {stats['reproduced']} · 미확인 {stats['not_probed']}"
        )
        if stats["by_origin"]["later"]:
            print(
                f"  ⚠ 스윕이 놓친 변종(later) {stats['by_origin']['later']}건 — "
                "첫 라운드에 찾았어야 할 같은 뿌리의 결함이다. Phase 5 회고에서 본다"
            )
        if stats["not_probed"]:
            print(f"  ⚠ 프로브하지 못한 변종 {stats['not_probed']}건 — 재현 여부를 모르는 채다")
    print()
    print(f"{len(problems)}건 위반" if problems else "기록에 문제 없음")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
