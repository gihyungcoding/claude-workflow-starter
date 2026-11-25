#!/usr/bin/env python3
"""요청별 시안을 모아 앱 전체 캔버스를 만든다 — 화면마다 가장 최근 정본 하나.

왜 필요한가
-----------
시안은 요청마다 mockup/<REQ-ID>/ 에 따로 쌓인다. REQ-001·002·003 이 쌓이면 "지금 앱의 화면"을 한 번에 보는 곳이
없고, 어느 요청이 어느 화면을 대체했는지 사람이 대응표로 정리해야 한다(시험 실행: design.md 대응표를 손으로).
화면 id 를 요청을 넘어 같은 화면의 이름으로 쓰고, 나중 요청이 앞 요청의 화면을 대체하게 한다.

규칙
----
- 확정된 시안(BRIEF mockup.status = approved)만 모은다. --include-drafts 면 확정 전 시안도.
- 요청 번호 순으로 쌓는다. 같은 id 는 나중 요청이 이긴다 — 그때 앞 요청의 상태 화면(id--*)도 함께 내려간다.
- 이름이 바뀐 화면은 나중 요청의 screens.json 화면에 "replaces": ["REQ-001/seat", "seat"] 로 적는다.
  replaces 는 적은 화면 하나만 내린다(상태 화면은 따로 적는다 — 남겨야 할 상태 화면이 있을 수 있다).
- 워크플로우 전부터 있던 시안 폴더(예: out/)는 --base 로 맨 아래에 깐다. 요청 화면이 "replaces": ["out:seat"] 로
  그 화면을 내린다(접두는 바탕 폴더 이름). --base 가 없으면 "out:…" 은 기록만 한다.
- 데스크톱 화면도 같은 규칙(따로 센다).

사용
----
    python3 build_app_canvas.py [<mockup 폴더>] [--base out] [--include-drafts] [--json]

기본 mockup 폴더: workflow_design/01_brief/mockup (현재 폴더 기준)

출력 (mockup 폴더 바로 아래)
    index.html · foundation.html · components.html   앱 전체 캔버스 (화면은 REQ-xxx/screens/… 를 그대로 띄운다)
    app-screens.json                                 화면 id → 정본 요청 · 대체한 것
    tokens.css · components.css · desktop.css · palette.js   가장 최근 요청의 것 (Foundation·Components 판용)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_canvas  # noqa: E402
from sync_kit import mockup_status  # noqa: E402

REQ_DIR_RE = re.compile(r"^REQ-(\d{3,})$")
REPLACE_RE = re.compile(r"^(?:(REQ-\d{3,})/)?([a-z0-9][a-z0-9-]*)$")
SHARED = ("tokens.css", "components.css", "desktop.css", "palette.js")


def requests(root: Path, include_drafts: bool) -> list[Path]:
    out = []
    for d in root.iterdir() if root.is_dir() else []:
        m = REQ_DIR_RE.match(d.name)
        if not (m and d.is_dir() and (d / "screens.json").is_file()):
            continue
        if include_drafts or mockup_status(d) == "approved":
            out.append((int(m.group(1)), d))
    return [d for _, d in sorted(out)]


def merge(root: Path, reqs: list[Path], warnings: list[str], base: Path | None = None) -> tuple[dict, dict]:
    """→ (합친 screens.json, 화면 id → 출처 기록)"""
    mobile: dict[str, dict] = {}
    desktop: dict[str, dict] = {}
    origin: dict[str, dict] = {}
    groups: list[str] = []
    badges: dict[str, str] = {}

    def drop(reg: dict, sid: str, by: str, variants: bool = True) -> None:
        for k in [k for k in reg if k == sid or (variants and k.startswith(sid + "--"))]:
            old = reg.pop(k)
            origin.setdefault(k, {}).setdefault("replaced", []).append(f"{old['_req']} → {by}")

    sources = ([(base.name, base, os.path.relpath(base, root))] if base else []) + [(d.name, d, d.name) for d in reqs]
    for req, d, prefix in sources:
        m = json.loads((d / "screens.json").read_text(encoding="utf-8"))
        for g in m.get("groups") or []:
            if g not in groups:
                groups.append(g)
        badges.update({k: v for k, v in (m.get("badges") or {}).items() if v})
        for kind, reg, default in (("screens", mobile, "screens/{}.html"), ("desktop", desktop, "screens/desktop/{}.html")):
            items = [s for s in (m.get(kind) or []) if isinstance(s, dict) and s.get("id")]
            for s in items:                       # 같은 id 의 앞 정본(과 그 상태 화면)을 먼저 내린다
                if "--" not in s["id"]:
                    drop(reg, s["id"], req)
                for r in s.get("replaces") or []:
                    label, sep, rest = str(r).partition(":")
                    if sep:                       # 바탕 폴더의 화면 — "out:seat"
                        if base and label == base.name:
                            drop(reg, rest, req, variants=False)
                        else:
                            origin.setdefault(s["id"], {}).setdefault("replaces_outside", []).append(r)
                        continue
                    mm = REPLACE_RE.match(str(r))
                    if not mm:
                        warnings.append(f"{req}/{s['id']}: replaces 형식이 아니다 — {r!r} (REQ-001/seat 또는 seat)")
                        continue
                    if mm.group(2) not in reg:
                        warnings.append(f"{req}/{s['id']}: 대체할 화면이 앞 요청에 없다 — {r}")
                    drop(reg, mm.group(2), req, variants=False)
            for s in items:
                c = dict(s)
                c["_req"] = req
                c["file"] = f"{prefix}/" + (s.get("file") or default.format(s["id"]))
                c["policies"] = [f"정본 {req}"] + list(s.get("policies") or [])
                reg[s["id"]] = c
                origin.setdefault(s["id"], {})["req"] = req

    def clean(reg: dict) -> list[dict]:
        return [{k: v for k, v in s.items() if k != "_req"} for s in reg.values()]

    merged = {"title": "앱 전체 화면 — 요청별 최신 정본", "groups": groups, "badges": badges,
              "screens": clean(mobile), "desktop": clean(desktop)}
    for d in merged["desktop"]:               # 내려간 모바일 화면을 묶은 기록은 지운다
        d["merges"] = [x for x in d.get("merges") or [] if x in mobile]
    return merged, origin


def build(root: Path, include_drafts: bool = False, base: Path | None = None) -> dict:
    warnings: list[str] = []
    reqs = requests(root, include_drafts)
    if base and not (base / "screens.json").is_file():
        return {"ok": False, "error": f"바탕 시안에 screens.json 이 없다 — {base}", "warnings": warnings}
    if not reqs and not base:
        return {"ok": False, "error": "모을 시안이 없다 — 확정된 시안(mockup.status=approved)이 있는 요청 폴더가 없다", "warnings": warnings}
    merged, origin = merge(root, reqs, warnings, base)
    latest = reqs[-1] if reqs else base
    for n in SHARED:                          # Foundation·Components 판은 가장 최근 요청의 토큰·부품으로
        if (latest / n).is_file():
            shutil.copyfile(latest / n, root / n)
    n, na, ng = build_canvas.build_index(root, merged)
    build_canvas.build_foundation(root)
    files = [root / s["file"] for s in merged["screens"] + merged["desktop"] if (root / s["file"]).is_file()]
    build_canvas.build_components(root, merged, files)
    record = {"base": base.name if base else None, "requests": [d.name for d in reqs], "screens": origin}
    (root / "app-screens.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "base": record["base"], "requests": record["requests"], "mobile": len(merged["screens"]), "desktop": len(merged["desktop"]),
            "arrows": na, "replaced": {k: v["replaced"] for k, v in origin.items() if v.get("replaced")}, "warnings": warnings}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default="workflow_design/01_brief/mockup")
    ap.add_argument("--include-drafts", action="store_true")
    ap.add_argument("--base", help="워크플로우 전부터 있던 시안 폴더(screens.json 이 있는 곳) — 맨 아래에 깐다")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    res = build(Path(args.root), args.include_drafts, Path(args.base) if args.base else None)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif not res["ok"]:
        print(res["error"], file=sys.stderr)
    else:
        print(f"앱 전체 캔버스: 바탕 {res['base'] or '없음'} · 요청 {', '.join(res['requests']) or '없음'}"
              f" · 모바일 {res['mobile']} · 데스크톱 {res['desktop']}")
        for k, v in res["replaced"].items():
            print(f"  대체됨 {k}: {'; '.join(v)}")
        for w in res["warnings"]:
            print(f"  ⚠ {w}")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
