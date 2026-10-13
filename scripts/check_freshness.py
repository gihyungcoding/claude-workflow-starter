#!/usr/bin/env python3
"""Phase 4에서 승인한 코드가 그대로인지 확인한다.

왜 필요한가
-----------
Phase 4는 사람이 승인하는 지점(HITL#3)이다. 승인 후 코드가 바뀌면 그 승인이 거짓이 되고,
여섯 단계에 걸쳐 세운 EXIT GATE 전체가 무력해진다. 원본 저장소 실측으로 산출물 188건 중
14건(7.4%)이 이 상태였다.

원본은 author date != committer date 로 rebase 를 추측했다. 여기서는 Phase 4 승인 시점에
VERIFY_<ID>.json 에 verified_commit 을 기록해 두고 그것과 대조한다 — 추측이 아니라 대조다.

★ HEAD 를 그대로 비교하지 않는 이유
----------------------------------
Phase 4 승인 직후에도 체크포인트 갱신 커밋이 이어지고, Phase 5 회고 산출물도 커밋된다.
그래서 HEAD SHA 를 단순 비교하면 정상 흐름에서도 항상 stale 로 판정된다.
verified_commit..HEAD 의 diff 에서 **워크플로우 산출물이 아닌 파일**이 바뀌었을 때만
stale 로 본다 (_utils.is_source_file).

사용
----
    python3 scripts/check_freshness.py --task-id TASK-001
    python3 scripts/check_freshness.py --task-id TASK-001 --json

exit code
---------
    0  신선함 — 승인한 코드가 그대로다
    1  stale — 승인 이후 소스가 바뀌었다
    2  판정 불가 — VERIFY 산출물이 없거나 verified_commit 이 기록되지 않았다

이 검사가 못 잡는 것
-------------------
커밋되지 않은 작업 트리 변경은 diff 대상이 아니다. 그건 ship_preflight 가 따로 본다.
force-push 로 verified_commit 이 저장소에서 사라진 경우 판정 불가(exit 2)로 떨어진다.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _utils import (  # noqa: E402
    artifact_path,
    changed_files_between,
    head_commit,
    is_source_file,
    is_valid_task_id,
    load_json,
    repo_root,
    task_id_error,
)


def commit_exists(sha: str) -> bool:
    try:
        out = subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
            capture_output=True, cwd=repo_root(),
        )
        return out.returncode == 0
    except FileNotFoundError:
        return False


def diff_stat(base: str, paths: list[str]) -> str:
    """바뀐 소스 파일들의 변경 규모 요약."""
    if not paths:
        return ""
    try:
        out = subprocess.run(
            ["git", "diff", "--stat", f"{base}..HEAD", "--", *paths],
            capture_output=True, text=True, cwd=repo_root(),
        )
        return out.stdout.strip()
    except FileNotFoundError:
        return ""


def check(task_id: str) -> dict:
    result = {
        "task_id": task_id,
        "status": "unknown",
        "verified_commit": None,
        "head": head_commit(),
        "changed_source": [],
        "changed_artifacts": [],
        "reason": "",
    }

    path = artifact_path(task_id, "4")
    if path is None:
        result["reason"] = "Phase 4 산출물 경로를 계산할 수 없다"
        return result

    data, err = load_json(path)
    if err:
        result["reason"] = f"{err} — Phase 4를 아직 수행하지 않았을 수 있다"
        return result
    if not isinstance(data, dict):
        result["reason"] = f"VERIFY 산출물이 객체가 아니다: {path.name}"
        return result

    review = data.get("human_review") or {}
    verified = review.get("verified_commit")

    if not verified:
        result["reason"] = (
            "human_review.verified_commit 이 없다 — Phase 4 승인이 이 필드를 기록하도록 "
            "wf-verify 스킬을 따랐는지 확인하라"
        )
        return result

    result["verified_commit"] = verified

    if not commit_exists(verified):
        result["reason"] = (
            f"승인 커밋을 저장소에서 찾을 수 없다: {verified[:12]} — "
            "force-push 나 브랜치 재작성이 있었다면 Phase 4를 다시 수행해야 한다"
        )
        return result

    changed, err = changed_files_between(verified)
    if err:
        result["reason"] = err
        return result

    source = [f for f in changed if is_source_file(f)]
    artifacts = [f for f in changed if not is_source_file(f)]
    result["changed_source"] = source
    result["changed_artifacts"] = artifacts

    if source:
        result["status"] = "stale"
        result["reason"] = f"승인 이후 소스 파일 {len(source)}개가 바뀌었다"
    else:
        result["status"] = "fresh"
        result["reason"] = (
            "승인한 코드가 그대로다"
            + (f" (워크플로우 산출물 {len(artifacts)}건만 추가됨)" if artifacts else "")
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not is_valid_task_id(args.task_id):
        print(task_id_error(args.task_id), file=sys.stderr)
        return 2

    result = check(args.task_id)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"신선도 검사 — {args.task_id}")
        print()
        if result["status"] == "fresh":
            print(f"  ✓ {result['reason']}")
            print(f"      승인 커밋 {result['verified_commit'][:12]}")
            if result["changed_artifacts"]:
                print(f"      산출물 변경 {len(result['changed_artifacts'])}건 (무해)")
        elif result["status"] == "stale":
            print(f"  ✗ {result['reason']}")
            print(f"      승인 커밋 {result['verified_commit'][:12]}  →  HEAD {result['head'][:12]}")
            print()
            for f in result["changed_source"][:12]:
                print(f"      {f}")
            if len(result["changed_source"]) > 12:
                print(f"      ... 외 {len(result['changed_source']) - 12}개")
            stat = diff_stat(result["verified_commit"], result["changed_source"])
            if stat:
                print()
                for line in stat.splitlines()[-1:]:
                    print(f"      {line.strip()}")
            print()
            print("  사람이 승인한 코드가 아닙니다. Phase 4를 다시 수행해 재승인을 받으세요.")
        else:
            print(f"  ? 판정 불가 — {result['reason']}")

    return {"fresh": 0, "stale": 1}.get(result["status"], 2)


if __name__ == "__main__":
    sys.exit(main())
