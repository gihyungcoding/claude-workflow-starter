#!/usr/bin/env python3
"""시안이 쓰는 키트 부품마다 프론트 부품이 있는지 대응표와 대조한다.

왜 필요한가
-----------
시안에 새 부품(좌석 고르기·기한)이 생겨도 frontend 의 공통 부품에 대응이 있는지 아무도 보지 않았다(시험 실행:
태스크 설명에 손으로 적었다). 대응표 하나를 정본으로 두고, 계획의 후속 작업(Dispatch)과 Phase 4 가 이것으로 대조한다.

대응표 — docs/product/ui-components.json
    {"parts": {
       "row":    "frontend/src/components/ui/Row.tsx",
       "picker": {"path": "frontend/src/components/ui/SeatPicker.tsx", "note": "좌석 고르기 + 미니맵"},
       "page":   {"none": "레이아웃 — GlobalTokens 가 맡는다"},
       "due":    null                      ← 아직 없음 (만들어야 할 부품)
    }}

부품(루트 클래스): 키트 CSS(components.css · desktop.css)의 클래스 중, 다른 키트 클래스 + "-" 로 시작하지 않는 것.
picker-mini 는 picker 의 일부, is-* 는 상태, .btn.primary 의 primary 처럼 붙어서만 쓰는 수식어는 세지 않는다.

사용
----
    python3 ui_map.py <시안 폴더> [--map docs/product/ui-components.json] [--desktop] [--init] [--json]

    --desktop  데스크톱 화면(screens/desktop/)도 센다 (기본: 모바일만 — 데스크톱을 구현하지 않는 프로젝트가 있다)
    --init     대응표에 없는 부품을 null 로 더해 쓴다 (채우는 것은 사람·태스크)

exit code: 0 모두 대응 · 1 대응 없는 부품 또는 없는 파일 · 2 인자 오류
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent / "kit"
CLASS_DEF_RE = re.compile(r"\.([a-z][a-z0-9-]*)")
CLASS_ATTR_RE = re.compile(r"""\bclass\s*=\s*["']([^"']*)["']""", re.I)


#: 이름 접두가 달라 접두로 못 묶는 부속 → 부품. 키트에 이런 부속을 더하면 여기에도 적는다.
PART_OF = {"tl-item": "timeline", "tl-date": "timeline", "tl-body": "timeline", "seat": "picker"}
#: 다른 클래스 뒤에 붙어서만 나오는 클래스(.btn.primary · body.has-cta)는 수식어 — 부품이 아니다
STANDALONE_RE = re.compile(r"(?:^|[\s>+~,(])\.([a-z][a-z0-9-]*)")


def kit_classes(kit: Path = KIT) -> set[str]:
    out: set[str] = set()
    for name in ("components.css", "desktop.css"):
        f = kit / name
        if f.is_file():
            css = re.sub(r"/\*.*?\*/", "", f.read_text(encoding="utf-8"), flags=re.S)
            for sel in re.findall(r"([^{}]+)\{", css):      # 선택자 부분만 — 값 안의 .5 같은 숫자를 세지 않게
                out.update(STANDALONE_RE.findall(sel.strip()))
    return {c for c in out if not c.startswith("is-")}


def root_of(cls: str, kit: set[str]) -> str:
    """picker-mini-view → picker. 키트에 있는 가장 짧은 접두를 루트로."""
    if cls in PART_OF:
        return PART_OF[cls]
    parts = cls.split("-")
    for i in range(1, len(parts) + 1):
        cand = "-".join(parts[:i])
        if cand in kit:
            return cand
    return cls


def used_parts(out: Path, desktop: bool, kit: set[str]) -> dict[str, list[str]]:
    """{루트 부품: [쓴 화면 id]}"""
    files = sorted((out / "screens").glob("*.html"))
    if desktop:
        files += sorted((out / "screens" / "desktop").glob("*.html"))
    used: dict[str, list[str]] = {}
    for f in files:
        for v in CLASS_ATTR_RE.findall(f.read_text(encoding="utf-8", errors="ignore")):
            for c in v.split():
                if c in kit:
                    used.setdefault(root_of(c, kit), [])
                    if f.stem not in used[root_of(c, kit)]:
                        used[root_of(c, kit)].append(f.stem)
    return dict(sorted(used.items()))


def check(out: Path, map_path: Path, desktop: bool = False, repo: Path = Path(".")) -> dict:
    kit = kit_classes()
    used = used_parts(out, desktop, kit)
    try:
        table = json.loads(map_path.read_text(encoding="utf-8")).get("parts") or {}
    except (OSError, json.JSONDecodeError):
        table = {}
    missing, broken = [], []
    for part, screens in used.items():
        v = table.get(part)
        if v is None:
            missing.append({"part": part, "screens": screens[:5]})
            continue
        path = v if isinstance(v, str) else (v.get("path") if isinstance(v, dict) else None)
        if path and not (repo / path).exists():
            broken.append({"part": part, "path": path})
    return {"used": used, "missing": missing, "broken": broken, "map": str(map_path), "has_map": map_path.is_file()}


def init(map_path: Path, missing: list[dict]) -> None:
    try:
        data = json.loads(map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    parts = data.setdefault("parts", {})
    for m in missing:
        parts.setdefault(m["part"], None)
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out")
    ap.add_argument("--map", default="docs/product/ui-components.json")
    ap.add_argument("--desktop", action="store_true")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out = Path(args.out)
    if not (out / "screens").is_dir():
        print(f"시안 폴더가 아니다(screens/ 없음): {out}", file=sys.stderr)
        return 2
    res = check(out, Path(args.map), args.desktop)
    if args.init and res["missing"]:
        init(Path(args.map), res["missing"])
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(f"부품 {len(res['used'])}개 · 대응 없음 {len(res['missing'])} · 없는 파일 {len(res['broken'])}"
              + ("" if res["has_map"] else f" (대응표 없음: {res['map']})"))
        for m in res["missing"]:
            print(f"  ✗ {m['part']} — {', '.join(m['screens'])}")
        for b in res["broken"]:
            print(f"  ✗ {b['part']} → {b['path']} 가 없다")
    return 1 if res["missing"] or res["broken"] else 0


if __name__ == "__main__":
    sys.exit(main())
