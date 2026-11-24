#!/usr/bin/env python3
"""시안 폴더에서 어느 화면도 쓰지 않는 그림을 지운다 — 커밋 크기를 줄인다.

키트의 assets/ 를 통째로 복사해 두고 작업하므로(일러스트·아바타 약 1.8MB), 요청마다 그대로 커밋하면
저장소가 커진다. screens/ 아래 HTML 과 credits.json 이 가리키는 파일만 남긴다. 라이선스 파일은 남긴다.

    python3 prune_assets.py <시안 폴더> [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REF_RE = re.compile(r"""(?:src|href)\s*=\s*["']([^"'#?]+)["']""", re.I)
KEEP_NAMES = {"LICENSE.md", "avatars.json"}


def referenced(out: Path) -> set[Path]:
    refs: set[Path] = set()
    for html in out.rglob("*.html"):
        for target in REF_RE.findall(html.read_text(encoding="utf-8", errors="replace")):
            if re.match(r"[a-z][a-z0-9+.-]*:", target, re.I):
                continue
            refs.add(Path(os.path.normpath(html.parent / target)))
    try:
        for c in json.loads((out / "credits.json").read_text(encoding="utf-8")):
            if isinstance(c, dict) and c.get("file"):
                refs.add(Path(os.path.normpath(out / c["file"])))
    except (OSError, json.JSONDecodeError):
        pass
    return refs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    out = Path(args.out).resolve()
    assets = out / "assets"
    if not assets.is_dir():
        print("assets/ 없음 — 할 일 없음")
        return 0
    refs = referenced(out)
    removed = 0
    for f in sorted(p for p in assets.rglob("*") if p.is_file()):
        if f.name in KEEP_NAMES or Path(os.path.normpath(f)) in refs:
            continue
        removed += 1
        if not args.dry_run:
            f.unlink()
    if not args.dry_run:
        for d in sorted((p for p in assets.rglob("*") if p.is_dir()), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
    print(f"{'지울' if args.dry_run else '지운'} 그림 {removed}개 · 남긴 참조 {len([r for r in refs if str(r).startswith(str(assets))])}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
