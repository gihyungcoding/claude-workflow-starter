#!/usr/bin/env python3
"""스타터와 프로젝트의 어긋남을 점검한다 — 반영이 사람의 기억에만 맡겨져 있던 곳.

왜 필요한가
-----------
스타터와 프로젝트(ticket-booking)는 같은 워크플로우 파일을 나눠 갖고, 한쪽에서 고친 것을
다른 쪽에 cherry-pick 으로 옮긴다. 이 반영을 확인하는 장치가 없어서 세 가지가 실제로 유실됐다.

  1. 푸시되지 않은 작업 — 스타터의 `.gitkeep` 수정이 20일 동안 로컬 브랜치에만 있었다.
     그 사이 프로젝트의 `.gitkeep` 위반이 6개에서 48개로 늘었다.
  2. 기준 브랜치에 닿지 못한 PR — 프로젝트의 #19 는 #18 위에 쌓은 PR 이었는데, #18 이
     머지된 뒤에도 그 브랜치가 남아 있어 #19 가 이미 머지된 브랜치로 머지됐다.
     내용은 develop 에 들어오지 않았다.
  3. 한쪽에만 있는 변경 — 프로젝트에만 있는 게이트 로직은 스타터 CI 의 테스트를 받지 않는다.

점검하는 것
-----------
A. 공유 파일 (.claude/ · scripts/ · docs/workflow/ · .pre-commit-config.yaml)
   두 저장소의 기본 브랜치 끝을 비교한다. 작업 트리가 아니라 커밋된 것을 본다 — 진행 중인
   작업이 어긋남으로 보이지 않게 하기 위해서다. 다른 파일은 어느 쪽이 뒤처졌는지를
   git 이력으로 가린다: 한쪽의 현재 내용이 다른 쪽 파일의 이전 버전이면 그쪽이 뒤처진 것이다.
   어느 쪽 이력에도 없으면 양쪽이 갈라진 것이다 (충돌이 나는 경우).
B. 푸시되지 않은 작업 — 원격 어디에도 없는 커밋이 있는 로컬 브랜치
C. 머지됐지만 기본 브랜치에 닿지 못한 PR, 그리고 base 가 이미 머지된 브랜치인 열린 PR

수용된 차이
-----------
프로젝트에만 있어야 하는 차이(예: 프로젝트 사례를 인용한 문장)는 영원히 어긋남으로 보이면
점검이 소음이 된다. 그래서 이유와 함께 수용한다.

    python3 scripts/check_sync.py --project ../ticket-booking --accept .claude/skills/x/SKILL.md --reason "..."

프로젝트의 `docs/workflow/sync-accepted.json` 에 기록되며, **그 순간의 양쪽 내용에 묶인다.**
어느 한쪽이 다시 바뀌면 수용이 풀리고 다시 어긋남으로 보인다. 한 번 수용하면 영원히 침묵하는
예외 목록이 되지 않게 하려는 것이다.

PR 도 같다. 기본 브랜치에 닿지 못한 PR 을 cherry-pick 으로 따로 복구하면 patch-id 가 달라
(base 가 다르므로 문맥이 다르다) 점검이 복구를 알아볼 수 없다. 복구한 뒤에 수용한다:

    python3 scripts/check_sync.py --project ../ticket-booking --accept-pr 19 --repo project \\
        --reason "develop 에 #41 로 다시 올렸다"

그 PR 의 머지 커밋에 묶인다.

사용
----
    python3 scripts/check_sync.py --project ../ticket-booking              # 스타터에서 실행
    python3 scripts/check_sync.py --project ../ticket-booking --json
    python3 scripts/check_sync.py --project ../ticket-booking --strict      # 파일 어긋남도 실패로

exit code
---------
    0  유실 위험 없음 (--strict 가 아니면 파일 어긋남은 보고만 한다)
    1  유실 위험이 있다 (오래 푸시되지 않은 작업 · 기본 브랜치에 닿지 못한 PR · 수용이 풀림),
       또는 --strict 이고 파일이 어긋나 있다
    2  인자 오류 / 저장소를 읽을 수 없음

이 점검이 못 잡는 것
-------------------
- **검사하지 못한 것은 통과가 아니라 '검사하지 못함'으로 보고한다.** gh 가 없거나 원격이 없으면
  C 와 B 의 일부를 건너뛰며, 그렇게 말한다. 0 건은 '없다'가 아니라 '확인했고 없다'일 때만 쓴다.
- 파일 내용의 *의미*는 보지 않는다. 같은 줄을 서로 다르게 고친 두 버전이 어느 쪽이 옳은지
  모른다. 갈라진 파일은 사람이 본다.
- 열린 PR 은 아직 기본 브랜치에 없으므로 A 가 보지 못한다. 열린 PR 의 변경은 머지된 뒤에 보인다.
- 커밋되지 않은 작업 트리 변경은 보지 않는다 (스타터 메인 체크아웃을 다른 세션이 쓰고 있어도
  이 점검이 영향을 받지 않는다).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

#: 두 저장소가 나눠 갖는 경로. CLAUDE.md · README.md 는 프로젝트마다 다르게 채워지므로 뺀다.
SHARED_ROOTS = (".claude/", "scripts/", "docs/workflow/", ".pre-commit-config.yaml")

#: 공유 경로 안에 있어도 비교하지 않는 것
EXCLUDE_PARTS = ("__pycache__", ".pyc", "/worktrees/", "settings.local.json", "/launch.json")

#: 수용 기록. 프로젝트에 두고, 비교 대상에서는 뺀다.
ACCEPTED_PATH = "docs/workflow/sync-accepted.json"

#: 푸시되지 않은 채 이만큼 지나면 유실 위험으로 본다. 작업 중인 브랜치는 당연히 푸시 전이다.
STALE_DAYS_DEFAULT = 2


# --- git ----------------------------------------------------------------------


def git(repo: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    except FileNotFoundError:
        return None
    return out.stdout if out.returncode == 0 else None


def is_repo(path: Path) -> bool:
    return git(path, "rev-parse", "--git-dir") is not None


def default_branch(repo: Path) -> tuple[str, str] | None:
    """(브랜치 이름, 비교에 쓸 ref). 원격의 기본 브랜치를 우선하고, 없으면 로컬 설정을 쓴다."""
    head = git(repo, "symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD")
    if head and head.strip():
        ref = head.strip()
        return ref.split("/", 1)[1], ref
    configured = (git(repo, "config", "workflow.baseBranch") or "").strip()
    candidates = [configured] if configured else []
    candidates += ["develop", "main", "master"]
    for name in candidates:
        for ref in (f"origin/{name}", name):
            if git(repo, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}"):
                return name, ref
    return None


def tip(repo: Path, ref: str) -> str:
    return (git(repo, "rev-parse", "--short", ref) or "").strip()


def tracked_blobs(repo: Path, ref: str) -> dict[str, str]:
    """공유 경로의 {파일: blob}. ref 에 커밋된 것만."""
    out = git(repo, "ls-tree", "-r", "-z", ref, "--", *[r.rstrip("/") for r in SHARED_ROOTS])
    blobs: dict[str, str] = {}
    for entry in (out or "").split("\0"):
        if not entry:
            continue
        meta, _, path = entry.partition("\t")
        parts = meta.split()
        if len(parts) < 3 or parts[1] != "blob":
            continue
        if any(x in "/" + path for x in EXCLUDE_PARTS) or path == ACCEPTED_PATH:
            continue
        blobs[path] = parts[2]
    return blobs


def blob_history(repo: Path, ref: str, path: str) -> set[str]:
    """그 ref 에서 path 가 가졌던 모든 blob."""
    log = git(repo, "log", "--format=%H", ref, "--", path) or ""
    blobs = set()
    for sha in log.split():
        blob = (git(repo, "rev-parse", f"{sha}:{path}") or "").strip()
        if blob:
            blobs.add(blob)
    return blobs


def last_commit(repo: Path, ref: str, path: str) -> str:
    return (git(repo, "log", "-1", "--format=%h %ad %s", "--date=short", ref, "--", path) or "").strip()[:80]


# --- A. 공유 파일 --------------------------------------------------------------


def load_accepted(project: Path, ref: str) -> tuple[list[dict], list[dict], str]:
    """(수용한 파일, 수용한 PR, 문제). 읽을 수 없으면 목록은 비고 문제를 돌려준다."""
    blob = git(project, "show", f"{ref}:{ACCEPTED_PATH}")
    if blob is None:
        return [], [], ""
    try:
        data = json.loads(blob)
    except json.JSONDecodeError as exc:
        return [], [], f"{ACCEPTED_PATH} 를 읽을 수 없다: {exc}"
    if not isinstance(data, dict) or not isinstance(data.get("accepted", []), list):
        return [], [], f"{ACCEPTED_PATH} 에 accepted 배열이 없다"
    files = [i for i in data.get("accepted", []) if isinstance(i, dict)]
    prs_ = [i for i in data.get("accepted_prs", []) if isinstance(i, dict)]
    return files, prs_, ""


def compare_files(starter: Path, s_ref: str, project: Path, p_ref: str) -> dict:
    s_blobs, p_blobs = tracked_blobs(starter, s_ref), tracked_blobs(project, p_ref)
    accepted, _, accepted_problem = load_accepted(project, p_ref)
    by_path = {a.get("path"): a for a in accepted}

    result = {
        "same": 0,
        "only_starter": sorted(set(s_blobs) - set(p_blobs)),
        "only_project": sorted(set(p_blobs) - set(s_blobs)),
        "project_behind": [], "starter_behind": [], "diverged": [],
        "accepted": [], "accepted_stale": [], "accepted_invalid": [],
        "problem": accepted_problem,
    }
    for path in sorted(set(s_blobs) & set(p_blobs)):
        sb, pb = s_blobs[path], p_blobs[path]
        if sb == pb:
            result["same"] += 1
            continue
        entry = by_path.get(path)
        item = {"path": path, "starter": last_commit(starter, s_ref, path),
                "project": last_commit(project, p_ref, path)}
        if entry is not None:
            if not str(entry.get("reason") or "").strip():
                result["accepted_invalid"].append({**item, "why": "reason 이 비어 있다"})
                continue
            if entry.get("starter_blob") == sb and entry.get("project_blob") == pb:
                result["accepted"].append({**item, "reason": str(entry["reason"]).strip()})
                continue
            result["accepted_stale"].append({**item, "reason": str(entry["reason"]).strip()})
            continue
        # 방향: 한쪽의 현재 내용이 다른 쪽 이력에 있으면 그쪽이 뒤처진 것
        if pb in blob_history(starter, s_ref, path):
            result["project_behind"].append(item)
        elif sb in blob_history(project, p_ref, path):
            result["starter_behind"].append(item)
        else:
            result["diverged"].append(item)
    # 수용했는데 이제 두 파일이 같아졌거나 사라졌다면 기록이 낡은 것이다
    for path, entry in by_path.items():
        if path in s_blobs and path in p_blobs and s_blobs[path] == p_blobs[path]:
            result["accepted_stale"].append({"path": path, "reason": str(entry.get("reason") or ""),
                                             "starter": "", "project": "",
                                             "note": "두 파일이 이미 같다 — 수용 기록을 지운다"})
    return result


def accept(starter: Path, s_ref: str, project: Path, p_ref: str, path: str, reason: str) -> str:
    """수용 기록을 프로젝트 작업 트리에 쓴다. 커밋은 하지 않는다."""
    if not reason.strip():
        return "이유 없이 수용하지 않는다 — --reason 에 왜 프로젝트에만 있어야 하는지 적는다"
    s_blobs, p_blobs = tracked_blobs(starter, s_ref), tracked_blobs(project, p_ref)
    if path not in s_blobs or path not in p_blobs:
        return f"양쪽에 있는 공유 파일이 아니다: {path}"
    if s_blobs[path] == p_blobs[path]:
        return f"{path} 는 두 저장소가 같다 — 수용할 차이가 없다"
    target = project / ACCEPTED_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {}
    except json.JSONDecodeError:
        return f"{ACCEPTED_PATH} 가 깨져 있다 — 먼저 고친다"
    items = [i for i in data.get("accepted", []) if isinstance(i, dict) and i.get("path") != path]
    items.append({"path": path, "reason": reason.strip(),
                  "starter_blob": s_blobs[path], "project_blob": p_blobs[path]})
    out = {"version": 1, "accepted": sorted(items, key=lambda i: i["path"])}
    if data.get("accepted_prs"):
        out["accepted_prs"] = data["accepted_prs"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ""


# --- B. 푸시되지 않은 작업 ----------------------------------------------------


def unpushed(repo: Path, stale_days: int, default_ref: str | None = None,
             now: float | None = None) -> dict:
    """원격 어디에도 없는 커밋이 있는 로컬 브랜치.

    스쿼시·리베이스 머지는 커밋 자체는 원격에 없지만 같은 패치가 기본 브랜치에 들어가 있다.
    그런 커밋은 유실이 아니므로 `git cherry` 로 같은 패치가 있는 것을 뺀다.
    """
    now = now or time.time()
    remotes = (git(repo, "remote") or "").split()
    if not remotes:
        return {"checked": False, "why": "원격이 없어 푸시 여부를 판단할 수 없다", "branches": []}
    names = (git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads") or "").split()
    branches = []
    for name in names:
        shas = set((git(repo, "rev-list", name, "--not", "--remotes") or "").split())
        if shas and default_ref:
            # '+' 는 기본 브랜치에 같은 패치가 없는 커밋, '-' 는 있는 커밋
            cherry = git(repo, "cherry", default_ref, name)
            if cherry is not None:
                shas &= {line[2:].strip() for line in cherry.splitlines() if line.startswith("+ ")}
        count = str(len(shas))
        if not shas:
            continue
        info = (git(repo, "log", "-1", "--format=%ct|%s", name) or "").strip()
        ts, _, subject = info.partition("|")
        age = (now - int(ts)) / 86400 if ts.isdigit() else 0.0
        branches.append({"branch": name, "commits": int(count), "age_days": round(age, 1),
                         "subject": subject[:70], "stale": age >= stale_days})
    return {"checked": True, "why": "", "branches": sorted(branches, key=lambda b: -b["age_days"])}


# --- C. PR --------------------------------------------------------------------


def fetch_prs(repo: Path) -> tuple[list[dict], list[dict], str]:
    """(머지된 PR, 열린 PR, 검사하지 못한 사유)."""
    if shutil.which("gh") is None:
        return [], [], "gh 가 없다"
    fields = "number,title,baseRefName,headRefName,mergeCommit,state"
    out: dict[str, list[dict]] = {}
    for state in ("merged", "open"):
        try:
            r = subprocess.run(["gh", "pr", "list", "--state", state, "--limit", "200", "--json", fields],
                               capture_output=True, text=True, cwd=repo, timeout=60)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return [], [], f"gh 실행 실패: {exc}"
        if r.returncode != 0:
            return [], [], f"gh pr list 실패: {(r.stderr or r.stdout).strip().splitlines()[0][:80] if (r.stderr or r.stdout).strip() else r.returncode}"
        try:
            out[state] = json.loads(r.stdout)
        except json.JSONDecodeError:
            return [], [], "gh 출력을 읽을 수 없다"
    return out["merged"], out["open"], ""


def classify_prs(merged: list[dict], open_prs: list[dict], default: str, reaches_default,
                 accepted: list[dict] | None = None) -> dict:
    """(순수 함수) 기본 브랜치에 닿지 못한 머지 PR, base 가 어긋난 열린 PR.

    reaches_default(커밋 oid) -> True | False | None(커밋을 모름)
    accepted: 복구했다고 수용한 PR [{pr, merge_commit, reason}] — 머지 커밋이 같을 때만 유효하다.
    """
    merged_heads = {p.get("headRefName"): p for p in merged}
    accepted_by_pr = {a.get("pr"): a for a in (accepted or [])}
    lost, unknown, accepted_prs = [], [], []
    for p in merged:
        if p.get("baseRefName") == default:
            continue  # 기본 브랜치로 머지된 PR 은 닿은 것이다
        oid = ((p.get("mergeCommit") or {}).get("oid")) or ""
        reached = reaches_default(oid) if oid else None
        item = {"number": p.get("number"), "title": str(p.get("title", ""))[:60],
                "base": p.get("baseRefName"), "head": p.get("headRefName")}
        if reached is False:
            entry = accepted_by_pr.get(p.get("number"))
            if entry and entry.get("merge_commit") == oid and str(entry.get("reason") or "").strip():
                accepted_prs.append({**item, "reason": str(entry["reason"]).strip()})
            else:
                lost.append({**item, "accept_stale": entry is not None})
        elif reached is None:
            unknown.append(item)
    stacked = []
    for p in open_prs:
        base = p.get("baseRefName")
        if base == default:
            continue
        item = {"number": p.get("number"), "title": str(p.get("title", ""))[:60],
                "base": base, "head": p.get("headRefName"),
                "base_already_merged": base in merged_heads
                and (merged_heads[base].get("baseRefName") == default)}
        stacked.append(item)
    return {"lost": lost, "unknown": unknown, "stacked": stacked, "accepted": accepted_prs}


def prs(repo: Path, default: str, d_ref: str, accepted: list[dict] | None = None) -> dict:
    merged, open_prs, why = fetch_prs(repo)
    if why:
        return {"checked": False, "why": why, "lost": [], "unknown": [], "stacked": [], "accepted": []}

    def reaches(oid: str):
        if git(repo, "cat-file", "-e", f"{oid}^{{commit}}") is None:
            return None
        return subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", oid, d_ref],
                              capture_output=True).returncode == 0

    return {"checked": True, "why": "", **classify_prs(merged, open_prs, default, reaches, accepted)}


def accept_pr(starter: Path, s_def: tuple[str, str], project: Path, p_def: tuple[str, str],
              number: int, repo_side: str, reason: str) -> str:
    """복구한 PR 의 수용 기록을 프로젝트 작업 트리에 쓴다. 커밋은 하지 않는다."""
    if not reason.strip():
        return "이유 없이 수용하지 않는다 — --reason 에 어떻게 복구했는지 적는다"
    if repo_side not in ("starter", "project"):
        return "--repo 는 starter 또는 project 여야 한다"
    repo, (default, d_ref) = (starter, s_def) if repo_side == "starter" else (project, p_def)
    merged, _, why = fetch_prs(repo)
    if why:
        return f"PR 정보를 가져오지 못해 수용하지 않는다: {why}"
    pr = next((p for p in merged if p.get("number") == number), None)
    if pr is None:
        return f"{repo_side} 의 머지된 PR 중 #{number} 가 없다"
    oid = ((pr.get("mergeCommit") or {}).get("oid")) or ""
    if pr.get("baseRefName") == default:
        return f"#{number} 는 기본 브랜치({default})로 머지됐다 — 수용할 유실이 없다"
    target = project / ACCEPTED_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {}
    except json.JSONDecodeError:
        return f"{ACCEPTED_PATH} 가 깨져 있다 — 먼저 고친다"
    items = [i for i in data.get("accepted_prs", []) if isinstance(i, dict) and i.get("pr") != number]
    items.append({"pr": number, "repo": repo_side, "merge_commit": oid, "reason": reason.strip()})
    data = {"version": 1, "accepted": data.get("accepted", []),
            "accepted_prs": sorted(items, key=lambda i: i["pr"])}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ""


# --- 출력 ---------------------------------------------------------------------


def lost_risk(report: dict) -> bool:
    """유실 위험이 있나 — exit 1 의 기준."""
    f = report["files"]
    if f["accepted_stale"] or f["accepted_invalid"] or f["problem"]:
        return True
    for side in ("starter", "project"):
        if any(b["stale"] for b in report[side]["unpushed"]["branches"]):
            return True
        p = report[side]["prs"]
        if p["lost"] or any(s["base_already_merged"] for s in p["stacked"]):
            return True
    return False


def drifted(report: dict) -> bool:
    f = report["files"]
    return bool(f["project_behind"] or f["starter_behind"] or f["diverged"])


def render(r: dict) -> str:
    f = r["files"]
    out = ["스타터 ↔ 프로젝트 어긋남 점검", "",
           f"  스타터   {r['starter']['path']}  ({r['starter']['branch']} @ {r['starter']['tip']})",
           f"  프로젝트 {r['project']['path']}  ({r['project']['branch']} @ {r['project']['tip']})", ""]

    total = f["same"] + sum(len(f[k]) for k in ("project_behind", "starter_behind", "diverged",
                                                 "accepted", "accepted_stale", "accepted_invalid"))
    out.append(f"A. 공유 파일 {total}개 (기본 브랜치 끝에 커밋된 것)")
    out.append(f"  ✓ 동일 {f['same']}")
    groups = (
        ("project_behind", "⚠", "프로젝트가 뒤처짐 — 스타터의 변경이 아직 안 들어왔다"),
        ("starter_behind", "⚠", "스타터가 뒤처짐 — 프로젝트에만 있는 변경이 스타터에 없다"),
        ("diverged", "⚠", "양쪽이 갈라짐 — 같은 파일을 서로 다르게 고쳤다 (사람이 본다)"),
        ("accepted_stale", "✗", "수용한 뒤 바뀜 — 수용이 풀렸다"),
        ("accepted_invalid", "✗", "수용 기록이 잘못됨"),
    )
    for key, mark, label in groups:
        if f[key]:
            out.append(f"  {mark} {label}: {len(f[key])}")
            for i in f[key]:
                out.append(f"      {i['path']}")
                if i.get("starter"):
                    out.append(f"        스타터   {i['starter']}")
                if i.get("project"):
                    out.append(f"        프로젝트 {i['project']}")
                if i.get("why") or i.get("note"):
                    out.append(f"        {i.get('why') or i.get('note')}")
    if f["accepted"]:
        out.append(f"  – 수용된 차이 {len(f['accepted'])}")
        for i in f["accepted"]:
            out.append(f"      {i['path']}  — {i['reason'][:60]}")
    for key, label in (("only_starter", "스타터에만 있음"), ("only_project", "프로젝트에만 있음")):
        if f[key]:
            out.append(f"  · {label} {len(f[key])}: " + ", ".join(f[key][:4]) + (" …" if len(f[key]) > 4 else ""))
    if f["problem"]:
        out.append(f"  ✗ {f['problem']}")

    for side, title in (("starter", "스타터"), ("project", "프로젝트")):
        u = r[side]["unpushed"]
        out.append("")
        out.append(f"B. 푸시되지 않은 작업 — {title}")
        if not u["checked"]:
            out.append(f"  ? 검사하지 못함: {u['why']}")
        elif not u["branches"]:
            out.append("  ✓ 없음 (원격에 없는 커밋이 있는 로컬 브랜치 0)")
        for b in u["branches"]:
            mark = "✗" if b["stale"] else "·"
            out.append(f"  {mark} {b['branch']}  {b['commits']}커밋  {b['age_days']}일 전  {b['subject']}")

    for side, title in (("starter", "스타터"), ("project", "프로젝트")):
        p = r[side]["prs"]
        out.append("")
        out.append(f"C. PR — {title}")
        if not p["checked"]:
            out.append(f"  ? 검사하지 못함: {p['why']}")
            continue
        if not (p["lost"] or p["unknown"] or p["stacked"] or p.get("accepted")):
            out.append("  ✓ 기본 브랜치에 닿지 못한 머지 PR 없음, 쌓은 PR 없음")
        for i in p["lost"]:
            note = " (수용했지만 머지 커밋이 바뀌어 풀렸다)" if i.get("accept_stale") else ""
            out.append(f"  ✗ #{i['number']} 는 {i['base']} 로 머지됐지만 기본 브랜치에 닿지 못했다 — {i['title']}{note}")
        for i in p.get("accepted", []):
            out.append(f"  – #{i['number']} 수용됨 — {i['reason'][:60]}")
        for i in p["unknown"]:
            out.append(f"  ? #{i['number']} 머지 커밋이 이 저장소에 없어 판단하지 못했다 (fetch 필요)")
        for i in p["stacked"]:
            if i["base_already_merged"]:
                out.append(f"  ✗ #{i['number']} 의 base({i['base']})는 이미 머지됐다 — base 를 기본 브랜치로 바꿔야 한다")
            else:
                out.append(f"  · #{i['number']} 는 {i['base']} 위에 쌓은 PR 이다 — 그 PR 이 머지되면 base 를 바꿔야 한다")

    out.append("")
    if lost_risk(r):
        out.append("유실 위험이 있다 (✗).")
    elif drifted(r):
        out.append("유실 위험은 없다. 파일 어긋남이 있다 (⚠).")
    else:
        out.append("어긋남 없음.")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", required=True, help="프로젝트 저장소 경로")
    ap.add_argument("--starter", help="스타터 저장소 경로 (기본: 이 스크립트가 있는 저장소)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="파일 어긋남도 실패로 취급")
    ap.add_argument("--stale-days", type=int, default=STALE_DAYS_DEFAULT,
                    help=f"푸시되지 않은 채 이 일수가 지나면 유실 위험 (기본 {STALE_DAYS_DEFAULT})")
    ap.add_argument("--accept", metavar="PATH", help="이 공유 파일의 차이를 수용한다")
    ap.add_argument("--accept-pr", metavar="N", type=int, help="복구한 PR 을 수용한다")
    ap.add_argument("--repo", choices=("starter", "project"), default="project",
                    help="--accept-pr 의 PR 이 있는 저장소 (기본 project)")
    ap.add_argument("--reason", default="", help="--accept · --accept-pr 의 이유 (필수)")
    args = ap.parse_args()

    starter = Path(args.starter) if args.starter else Path(__file__).resolve().parent.parent
    project = Path(args.project)
    for label, repo in (("스타터", starter), ("프로젝트", project)):
        if not repo.is_dir() or not is_repo(repo):
            print(f"{label}가 git 저장소가 아니다: {repo}", file=sys.stderr)
            return 2
    if starter.resolve() == project.resolve():
        print("스타터와 프로젝트가 같은 저장소다", file=sys.stderr)
        return 2

    s_def, p_def = default_branch(starter), default_branch(project)
    if s_def is None or p_def is None:
        print("기본 브랜치를 찾지 못했다 (origin/HEAD · workflow.baseBranch · develop · main)", file=sys.stderr)
        return 2

    if args.accept:
        err = accept(starter, s_def[1], project, p_def[1], args.accept, args.reason)
        if err:
            print(err, file=sys.stderr)
            return 2
        print(f"수용 기록을 썼다: {project / ACCEPTED_PATH}  — 커밋은 하지 않았다. 이유: {args.reason.strip()}")
        return 0

    if args.accept_pr is not None:
        err = accept_pr(starter, s_def, project, p_def, args.accept_pr, args.repo, args.reason)
        if err:
            print(err, file=sys.stderr)
            return 2
        print(f"수용 기록을 썼다: {project / ACCEPTED_PATH}  — 커밋은 하지 않았다. 이유: {args.reason.strip()}")
        return 0

    _, accepted_prs, _ = load_accepted(project, p_def[1])
    by_side = {"starter": [a for a in accepted_prs if a.get("repo") == "starter"],
               "project": [a for a in accepted_prs if a.get("repo", "project") == "project"]}
    report = {
        "starter": {"path": str(starter), "branch": s_def[0], "tip": tip(starter, s_def[1]),
                    "unpushed": unpushed(starter, args.stale_days, s_def[1]),
                    "prs": prs(starter, *s_def, by_side["starter"])},
        "project": {"path": str(project), "branch": p_def[0], "tip": tip(project, p_def[1]),
                    "unpushed": unpushed(project, args.stale_days, p_def[1]),
                    "prs": prs(project, *p_def, by_side["project"])},
        "files": compare_files(starter, s_def[1], project, p_def[1]),
    }
    report["lost_risk"] = lost_risk(report)
    report["drifted"] = drifted(report)

    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render(report))
    return 1 if report["lost_risk"] or (args.strict and report["drifted"]) else 0


if __name__ == "__main__":
    sys.exit(main())
