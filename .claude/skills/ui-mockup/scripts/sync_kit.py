#!/usr/bin/env python3
"""키트 부품 파일을 시안 폴더로 복사하고, 어느 키트를 복사했는지 남긴다.

왜 필요한가
-----------
시안 폴더는 키트의 components.css · desktop.css · palette.js 를 복사해 쓴다(파일로 열어도 보이게).
손으로 cp 하면 키트를 고친 뒤 옮기는 것을 빠뜨린다 — 시험 실행에서 요청 도중 키트에 부품(좌석 고르기·기한)을
더할 때마다 손으로 옮겼고, 한 번은 시안 폴더에만 고친 CSS 가 남을 뻔했다. 이 스크립트로만 옮기고,
check_mockup.py 가 확정 전 시안의 부품 파일이 키트와 같은지 대조한다.

확정(BRIEF mockup.status = approved)된 시안은 그 시점의 기록이라 다시 복사하지 않는다 — --force 로만.

사용
----
    python3 sync_kit.py <시안 폴더> [--force] [--check]

    --check   복사하지 않고 다른 파일만 알린다 (exit 1 = 다름)

screens.json 의 "surface"(도메인 표면 프리셋)가 있으면 kit/themes/<surface>.css 를 theme.css 로 옮긴다.

출력: <시안 폴더>/kit.json — {"files": {"components.css": "<sha256 앞 12자>", …}}
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent / "kit"
KIT_FILES = ("components.css", "desktop.css", "palette.js")
SURFACES = ("card-stack", "flat-dense", "edge", "dark-media", "flat-banded", "chunky")   # kit/themes/<이름>.css


def surface_of(out: Path) -> str:
    """screens.json 의 "surface" — 도메인 표면 프리셋. 없으면 card-stack(키트 기본)."""
    try:
        return json.loads((out / "screens.json").read_text(encoding="utf-8")).get("surface") or "card-stack"
    except (OSError, json.JSONDecodeError, AttributeError):
        return "card-stack"


def kit_sources(out: Path, kit: Path = KIT) -> dict[str, Path]:
    """시안 폴더의 파일 이름 → 키트 원본. theme.css 는 screens.json surface 의 프리셋."""
    src = {n: kit / n for n in KIT_FILES}
    surface = surface_of(out)
    if surface in SURFACES:
        src["theme.css"] = kit / "themes" / f"{surface}.css"
    return src


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def mockup_status(out: Path) -> str | None:
    """시안 폴더(…/01_brief/mockup/<REQ>) 옆 BRIEF 의 mockup.status. BRIEF 가 없으면 None."""
    brief = out.parent.parent / f"BRIEF_{out.name}.json"
    try:
        data = json.loads(brief.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    mock = data.get("mockup") if isinstance(data, dict) else None
    return mock.get("status") if isinstance(mock, dict) else None


def differing(out: Path, kit: Path = KIT) -> list[str]:
    """시안 폴더에 있는 키트 파일 중 키트와 내용이 다른 것. 시안 폴더에 없는 파일은 세지 않는다."""
    return [n for n, k in kit_sources(out, kit).items()
            if (out / n).is_file() and k.is_file() and digest(out / n) != digest(k)]


def sync(out: Path, kit: Path = KIT) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for n, k in kit_sources(out, kit).items():
        if k.is_file():
            shutil.copyfile(k, out / n)
            files[n] = digest(k)
    record = {"surface": surface_of(out), "files": files}
    (out / "kit.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out")
    ap.add_argument("--force", action="store_true", help="확정된 시안에도 복사한다")
    ap.add_argument("--check", action="store_true", help="복사하지 않고 다른 파일만 알린다")
    args = ap.parse_args()
    out = Path(args.out)
    if args.check:
        diff = differing(out)
        print("키트와 같다" if not diff else "키트와 다르다 — " + ", ".join(diff))
        return 1 if diff else 0
    if mockup_status(out) == "approved" and not args.force:
        print(f"{out.name}: 확정된 시안이다 — 그 시점의 기록이라 복사하지 않는다 (--force 로만)", file=sys.stderr)
        return 1
    rec = sync(out)
    print(f"키트 → {out}: " + ", ".join(f"{k} {v}" for k, v in rec["files"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
