#!/usr/bin/env python3
"""시안 폴더를 정적으로 검사한다 — 렌더링 없이 파일만 읽어 잡을 수 있는 것.

왜 필요한가
-----------
시안을 만든 에이전트는 "링크가 다 이어진다·주 버튼은 하나다"를 스스로 확인했다고 보고한다.
블라인드 검증에서도 두 에이전트가 같은 보고를 했지만, 렌더링해 보니 대비·넘침이 남아 있었다.
렌더링 검사(audit.html)는 브라우저가 필요하므로, 파일만으로 잡을 수 있는 것은 여기서 먼저 잡는다.

검사하는 것
-----------
- screens.json 파싱 · 화면 파일 존재 · 데스크톱 화면 파일 존재
- 모든 모바일 화면이 정확히 하나의 데스크톱 화면에 묶임 (desktop 이 있으면)
- branches 의 to 가 실재하는 화면
- 화면마다 h1 정확히 1개 · 채워진 주 버튼(btn primary) 1개 이하
- 인라인 style 금지 (.range 의 --from/--to 만 예외) · <style> 안의 색 값 금지 · 이모지 금지
- href · img src 가 가리키는 파일이 실재 (외부 URL·#·data-back 제외)
- 배지 색 클래스가 screens.json badges 표에 있는 것만

사용
----
    python3 check_mockup.py <시안 폴더> [--json]

exit code
---------
    0  통과 (경고는 있을 수 있다)
    1  위반 있음
    2  폴더나 screens.json 을 읽을 수 없음

이 검사가 못 잡는 것
-------------------
대비·터치 크기·넘침·글자 크기 종류처럼 렌더링해야 아는 것 — audit.html 이 본다.
화면이 좋은지는 보지 않는다. 그건 사람과 비평 체크리스트(references/checklist.md)의 몫이다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

H1_RE = re.compile(r"<h1\b", re.I)
CLASS_RE = re.compile(r"""\bclass\s*=\s*["']([^"']*)["']""", re.I)
STYLE_ATTR_RE = re.compile(r"""\bstyle\s*=\s*["']([^"']*)["']""", re.I)
STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.S | re.I)
COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")
HREF_RE = re.compile(r"""<a\b([^>]*)>""", re.I)
ATTR_RE = lambda name: re.compile(rf"""\b{name}\s*=\s*["']([^"']*)["']""", re.I)
SRC_RE = re.compile(r"""<img\b[^>]*\bsrc\s*=\s*["']([^"']+)["']""", re.I)
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]")
RANGE_STYLE_RE = re.compile(r"^\s*(--from:\s*[\d.]+%;?\s*|--to:\s*[\d.]+%;?\s*)+$")
BADGE_COLORS = ("is-brand", "is-warning", "is-info", "is-success", "is-danger")


def strip_scripts(src: str) -> str:
    return re.sub(r"<script\b.*?</script>", "", src, flags=re.S | re.I)


def check_file(path: Path, root: Path, badge_classes: set[str], errors: list[str], warnings: list[str]) -> None:
    rel = path.relative_to(root)
    src = strip_scripts(path.read_text(encoding="utf-8"))
    n_h1 = len(H1_RE.findall(src))
    if n_h1 != 1:
        errors.append(f"{rel}: h1 이 {n_h1}개 — 화면당 정확히 1개")
    primaries = sum(1 for c in CLASS_RE.findall(src) if {"btn", "primary"} <= set(c.split()))
    if primaries > 1:
        errors.append(f"{rel}: 채워진 주 버튼(btn primary)이 {primaries}개 — 1개 이하")
    for style in STYLE_ATTR_RE.findall(src):
        if not RANGE_STYLE_RE.match(style):
            errors.append(f"{rel}: 인라인 style 금지 — style=\"{style[:40]}\"")
            break
    for block in STYLE_BLOCK_RE.findall(src):
        if COLOR_RE.search(block):
            errors.append(f"{rel}: <style> 안에 색 값을 직접 썼다 — 토큰 변수만 쓴다")
            break
    text = re.sub(r"<[^>]+>", " ", src)
    if EMOJI_RE.search(text):
        errors.append(f"{rel}: 이모지 — 사물은 일러스트, 누르는 것은 선 아이콘")
    for attrs in HREF_RE.findall(src):
        if re.search(r"\bdata-back\b", attrs):
            continue
        m = ATTR_RE("href").search(attrs)
        if not m:
            if not re.search(r"\bdata-stay\b", attrs):
                warnings.append(f"{rel}: href 없는 링크 — 다른 화면 / data-back / data-stay 중 하나")
            continue
        target = m.group(1).split("#")[0].split("?")[0]
        if not target or re.match(r"[a-z][a-z0-9+.-]*:", target, re.I):
            continue
        if not (path.parent / target).is_file():
            errors.append(f"{rel}: 링크가 가리키는 파일이 없다 — {target}")
    for src_attr in SRC_RE.findall(src):
        if re.match(r"[a-z][a-z0-9+.-]*:", src_attr, re.I):
            continue
        if not (path.parent / src_attr).is_file():
            errors.append(f"{rel}: 이미지 파일이 없다 — {src_attr}")
    if badge_classes:
        for c in CLASS_RE.findall(src):
            parts = c.split()
            if "badge" in parts:
                for color in (p for p in parts if p in BADGE_COLORS):
                    if color not in badge_classes:
                        warnings.append(f"{rel}: badges 표에 없는 배지 색 {color}")


def run(root: Path) -> tuple[list[str], list[str], str]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        m = json.loads((root / "screens.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return errors, warnings, f"screens.json 을 읽을 수 없다 — {exc}"

    screens = [s for s in m.get("screens", []) if isinstance(s, dict) and s.get("id")]
    desktop = [d for d in m.get("desktop", []) if isinstance(d, dict) and d.get("id")]
    if not screens:
        errors.append("screens.json 에 화면이 없다")
    badge_classes = {v for v in (m.get("badges") or {}).values() if v}

    ids = {s["id"] for s in screens}
    files = []
    for s in screens:
        f = root / (s.get("file") or f"screens/{s['id']}.html")
        if not f.is_file():
            errors.append(f"{s['id']}: 화면 파일이 없다 — {f.relative_to(root)}")
        else:
            files.append(f)
        for b in s.get("branches") or []:
            if b.get("to") not in ids:
                errors.append(f"{s['id']}: 갈래가 없는 화면을 가리킨다 — {b.get('to')}")
    owners: dict[str, list[str]] = {}
    for d in desktop:
        f = root / (d.get("file") or f"screens/desktop/{d['id']}.html")
        if not f.is_file():
            errors.append(f"{d['id']}: 데스크톱 화면 파일이 없다 — {f.relative_to(root)}")
        else:
            files.append(f)
        for x in d.get("merges") or []:
            if x not in ids:
                errors.append(f"{d['id']}: 없는 모바일 화면을 묶었다 — {x}")
            owners.setdefault(x, []).append(d["id"])
    if desktop:
        for sid in sorted(ids):
            got = owners.get(sid, [])
            if len(got) != 1:
                errors.append(f"{sid}: 데스크톱 화면 {len(got)}개에 묶였다 — 정확히 하나여야 한다")
    for f in files:
        check_file(f, root, badge_classes, errors, warnings)
    return errors, warnings, ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = Path(args.out).resolve()
    errors, warnings, fatal = run(root)
    if fatal:
        print(json.dumps({"fatal": fatal}, ensure_ascii=False) if args.json else f"✗ {fatal}", file=sys.stdout if args.json else sys.stderr)
        return 2
    ok = not errors
    if args.json:
        print(json.dumps({"pass": ok, "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
    else:
        print(f"{'✓' if ok else '✗'} 시안 정적 검사 — 위반 {len(errors)} · 경고 {len(warnings)}")
        for e in errors:
            print(f"  ✗ {e}")
        for w in warnings[:30]:
            print(f"  ⚠ {w}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
