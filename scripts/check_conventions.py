#!/usr/bin/env python3
r"""코딩 규칙 게이트 — 첫 태스크를 시작하기 전에 규칙이 정해지고 증명됐는가.

왜 필요한가
-----------
새 프로젝트에는 코드가 없어 "주변 코드의 관례"가 없다. 그대로 두면 첫 태스크가 우연히 쓴 코드가 컨벤션이 된다.
시험 실행(ticket-booking)에서 컨벤션 문제 10건 중 7건은 코드 없이 정할 수 있었는데 나중에 정해 재작업이 생겼다 —
테스트 DB 를 "나중에 전환"하기로 하고 두 달 동안 전환하지 않아 Phase 4 FAIL 4회, 포매터를 첫 Red 뒤에 넣어 15개 파일
재정렬, 빈 저장소에서 쓴 제약 경로가 실제 패키지와 달라 계속 거짓 통과. wf-init 에 "권고"가 있었지만 지켜지지 않았다 —
그래서 게이트로 만든다. 정하는 법은 .claude/skills/conventions/SKILL.md.

검사하는 것
-----------
- docs/architecture/conventions.md 가 있다 · 필수 항목(C-…)이 모두 있고 결정·검사·상태가 TODO 가 아니다
- C-TESTDB 결정이 `같음` 또는 `다름` 으로 시작한다. `다름` 이면 실재하는 ADR 과 전환할 태스크(TASK-…)가 결정 칸에 있다
- C-LINT 를 정했으면 린트 설정 파일이 실제로 있다(eslint·oxlint·biome·ruff·mypy·checkstyle·prettier, pyproject 의 [tool.ruff], gradle 의 spotless)
- 상태가 모두 '기준 구현 확인'(해당 없으면 '해당 없음', C-COMMIT 제외) — 4.5 의 사람 확인
- 표의 칸이 정확히 4개다(칸 안의 | 는 \| 로)
- 「기준 파일」이 하나 이상이고 모두 실재한다
- CLAUDE.md 린트 줄이 채워져 있다(예시·TODO 가 아니다)
- constraints.yaml: error 위반이 없다 · warn 인데 promote_after 가 없는 제약이 없다 · 검사 대상 없음(no_target)이 없다
  (forbidden_path 는 파일이 없는 것이 통과다 — 대상 없음으로 세지 않는다)

언제 막나
---------
첫 태스크 전(done 인 태스크가 없음)에만 exit 1. 이미 진행 중인 프로젝트(done 태스크가 있음)는 결과를 보여 주고 exit 0 —
소급 적용은 conventions 스킬로 따로 한다. wf-start 가 부른다.

사용
----
    python3 scripts/check_conventions.py [--json]

exit code
---------
    0  통과 (또는 진행 중인 프로젝트라 경고만)
    1  첫 태스크 전인데 불통과
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _utils import decisions_dir, docs_root, load_constraints, repo_root  # noqa: E402
from check_architecture import check_one, task_statuses  # noqa: E402

REQUIRED = ("C-TESTDB", "C-LINT", "C-LAYOUT", "C-ERROR", "C-VALID", "C-DATA", "C-TEST", "C-LOG", "C-FE", "C-COMMIT")
ROW_RE = re.compile(r"^\|\s*(C-[A-Z0-9-]+)\s*\|(.*)\|\s*$")
CELL_SPLIT = re.compile(r"(?<!\\)\|")          # 칸 안의 | 는 \| 로 적는다 (정규식 a|b)
DONE_STATUS = ("기준 구현 확인", "해당 없음")      # 4.5 사람 확인을 거친 상태
LINT_LINE_RE = re.compile(r"^-\s*\*\*린트\*\*\s*:\s*(.*)$", re.M)


def conventions_path() -> Path:
    return docs_root() / "architecture" / "conventions.md"


def is_todo(cell: str) -> bool:
    c = cell.strip().strip("`").strip()
    return not c or "TODO" in c          # "TODO 나중에 — …" 도 미결정이다 (실제 실행에서 통과했다)


LINT_CONFIG_NAMES = re.compile(r"^(\.eslintrc(\..*)?|eslint\.config\..*|\.oxlintrc.*|biome\.jsonc?|\.?ruff\.toml|\.?mypy\.ini"
                               r"|checkstyle.*\.xml|\.prettierrc(\..*)?|prettier\.config\..*)$")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "build", "dist", ".claude", "__pycache__", ".gradle"}


def has_lint_config(root: Path) -> bool:
    """린트 설정 파일이 실제로 있는가 — 명령 줄만 채우고 설정은 없는 경우를 잡는다."""
    for path in _walk(root, depth=4):
        name = path.name
        if LINT_CONFIG_NAMES.match(name):
            return True
        if name == "pyproject.toml" and "[tool.ruff" in _read(path):
            return True
        if name in ("build.gradle", "build.gradle.kts") and re.search(r"spotless|checkstyle", _read(path)):
            return True
    return False


def _walk(root: Path, depth: int):
    stack = [(root, 0)]
    while stack:
        d, n = stack.pop()
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for e in entries:
            if e.is_dir():
                if n < depth and e.name not in SKIP_DIRS:
                    stack.append((e, n + 1))
            else:
                yield e


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def adr_exists(adr_id: str) -> bool:
    d = decisions_dir()
    return d.is_dir() and any(p.name.startswith(adr_id) for p in d.iterdir())


def parse(text: str) -> tuple[dict[str, dict], list[str]]:
    """→ ({id: {decision, check, status, cells}}, [기준 파일 경로])"""
    rows: dict[str, dict] = {}
    for line in text.splitlines():
        m = ROW_RE.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in CELL_SPLIT.split(m.group(2))]
        n = len(cells)
        cells += [""] * (3 - len(cells))
        rows[m.group(1)] = {"decision": cells[0], "check": cells[1], "status": cells[2], "cells": n}
    refs: list[str] = []
    sec = re.search(r"^##\s*기준 파일\s*$(.*?)(?=^##\s|\Z)", text, flags=re.M | re.S)
    if sec:
        for line in sec.group(1).splitlines():
            m = re.match(r"^\s*-\s*`?([^`\s—]+)`?", line)
            if m:
                refs.append(m.group(1))
    return rows, refs


def check_constraints(root: Path) -> list[str]:
    constraints, err = load_constraints()
    if err:
        return []          # 제약 파일이 없거나 읽을 수 없는 것은 check_architecture 가 알린다
    out = []
    for c in constraints:
        cid = c.get("id", "?")
        if str(c.get("severity", "error")).lower() == "warn" and not c.get("promote_after"):
            out.append(f"{cid}: warn 인데 promote_after 가 없다 — 언제 error 로 올릴지 적지 않으면 영원히 warn 이다")
        kind = (c.get("detect") or {}).get("type")
        violations, scanned = check_one(c, root, None)
        if violations and str(c.get("severity", "error")).lower() == "error":
            out.append(f"{cid}: 위반 {len(violations)}건 — 기준 구현이 자기 규칙을 어긴다 ({violations[0]['file']})")
        if scanned == 0 and not violations and kind != "forbidden_path":
            out.append(f"{cid}: 검사 대상이 0개다 — 경로(glob)가 실제 파일과 맞는지 기준 구현 뒤 확인")
    return out


def run() -> dict:
    root = repo_root()
    problems: list[str] = []
    path = conventions_path()
    started = any(str(s).lower() == "done" for s in task_statuses().values())   # tasks.json — 승격 판정과 같은 출처

    if not path.is_file():
        problems.append(f"{path.relative_to(root)} 가 없다 — /wf-init 2.7 (conventions 스킬)")
    else:
        rows, refs = parse(path.read_text(encoding="utf-8"))
        for rid in REQUIRED:
            r = rows.get(rid)
            if r is None:
                problems.append(f"{rid}: 표에 없다")
                continue
            if r["cells"] != 3:
                problems.append(f"{rid}: 표의 칸이 {r['cells'] + 1}개다(4개여야 한다) — 칸 안의 | 는 \\| 로 적는다")
                continue
            empty = [k for k in ("decision", "check", "status") if is_todo(r[k])]
            if empty:
                problems.append(f"{rid}: TODO 가 남았다 — {'·'.join({'decision': '결정', 'check': '검사', 'status': '상태'}[k] for k in empty)}")
        # 4.5 의 사람 확인 — 결정만 하고 기준 구현으로 보이지 않은 규칙은 첫 태스크가 다르게 쓴다
        for rid in REQUIRED:
            r = rows.get(rid)
            if not r or r["cells"] != 3 or is_todo(r["status"]) or rid == "C-COMMIT":
                continue
            if r["status"].strip("` ") not in DONE_STATUS:
                problems.append(f"{rid}: 상태가 '{r['status']}' — 기준 구현으로 확인하고 사람이 승인하면 '기준 구현 확인'"
                                f"(해당 없는 항목은 '해당 없음')")
        tdb = rows.get("C-TESTDB")
        if tdb and not is_todo(tdb["decision"]):
            head = tdb["decision"].strip("` ")
            if not (head.startswith("같음") or head.startswith("다름")):
                problems.append("C-TESTDB: 결정은 '같음 — …' 또는 '다름 — …' 으로 시작한다(운영 DB 와 같은지가 이 항목의 전부다)")
            elif head.startswith("다름"):
                adr = re.search(r"ADR-\d{4}", head)
                if not adr or not re.search(r"TASK-\d+", head):
                    problems.append("C-TESTDB: 운영과 다른 테스트 DB 인데 ADR 번호와 전환할 태스크(TASK-…)가 없다 — "
                                    "'나중에 전환'만 적으면 전환하지 않는다")
                elif not adr_exists(adr.group(0)):
                    problems.append(f"C-TESTDB: {adr.group(0)} 가 docs/decisions 에 없다")
        lint = rows.get("C-LINT")
        if lint and not is_todo(lint["decision"]) and not lint["decision"].startswith("해당 없음") \
                and not has_lint_config(root):
            problems.append("C-LINT: 정했는데 린트 설정 파일이 없다 — 4.5 골격에서 설정을 넣는다")
        if not refs:
            problems.append("기준 파일이 없다 — /wf-init 4.5 기준 구현을 만들고 「## 기준 파일」에 적는다")
        for ref in refs:
            if not (root / ref).is_file():
                kind = "폴더다 — 본뜰 파일을 하나씩 적는다" if (root / ref).is_dir() else "없다"
                problems.append(f"기준 파일이 {kind}: {ref}")

    claude = root / "CLAUDE.md"
    if claude.is_file():
        m = LINT_LINE_RE.search(claude.read_text(encoding="utf-8"))
        val = (m.group(1) if m else "").strip()
        if not val or val.startswith("(예:") or "TODO" in val.upper():
            problems.append("CLAUDE.md 린트 명령이 비어 있다 — /wf-init 4 · 4.5 에서 린터를 넣고 명령을 적는다")

    problems += check_constraints(root)
    ok = not problems
    return {"pass": ok, "blocking": (not ok) and not started, "started": started, "problems": problems,
            "path": str(path.relative_to(root))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    res = run()
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif res["pass"]:
        print("✓ 코딩 규칙 — 정해지고 기준 구현으로 증명됐다")
    else:
        head = "✗ 코딩 규칙 — 첫 태스크 전에 마쳐야 한다" if res["blocking"] else \
            "⚠ 코딩 규칙 — 진행 중인 프로젝트라 막지 않는다 (소급 적용: conventions 스킬)"
        print(head)
        for p in res["problems"]:
            print(f"  - {p}")
    return 1 if res["blocking"] else 0


if __name__ == "__main__":
    sys.exit(main())
