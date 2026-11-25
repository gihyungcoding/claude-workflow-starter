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
- 키트 동기화 — 확정 전 시안의 components.css·desktop.css·palette.js 가 키트와 같다 (sync_kit.py 로만 옮긴다)
- 표면 프리셋 — screens.json surface 가 프리셋 이름이고, 모든 화면이 theme.css 를 걸고, theme.css 는 허용 변수만 바꾸며
  바탕·블록·막대에 브랜드 계열 색을 쓰지 않는다. dark-media 면 tokens.css 가 어두운 토큰(derive.py --mode dark)
- 데이터 묶음 — layout.md 「데이터 묶음」 표의 묶음을 data-bundle 로 표시한 곳끼리(같은 너비) 항목 순서와 부품이 같다

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
from html.parser import HTMLParser
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
RANGE_STYLE_RE = re.compile(r"^\s*(--(?:(?:from|to|x|y|w|h):\s*[\d.]+%|(?:cols|rows):\s*\d+);?\s*)+$")   # .range · .picker-mini 의 CSS 변수만
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
    blocks = STYLE_BLOCK_RE.findall(src)
    if blocks:
        warnings.append(f"{rel}: 화면 안 <style> {sum(len(b) for b in blocks)}자 — 키트 밖 부품은 화면마다 달라진다. "
                        "키트 부품(칸 고르기 등)으로 바꾸거나, 여러 화면에 쓰이면 키트에 더하자고 제안")
    for block in blocks:
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


# ── 데이터 묶음 ────────────────────────────────────────────────────────────
# 같은 데이터(금액·기한·계좌)를 화면마다 다른 부품으로 보이던 것(시험 실행)을 막는다. 부품 하나의 모양은 키트가 지키지만
# "이 데이터 묶음은 어떤 부품들로" 는 아무도 정하지 않아 화면마다 갈렸다. 그래서 layout.md 에 먼저 정하고 여기서 대조한다.
BUNDLE_HEAD_RE = re.compile(r"^##\s*데이터 묶음", re.M)


def read_bundles(root: Path) -> dict[str, list[str]]:
    """layout.md 「## 데이터 묶음」 표 → {묶음: [항목 순서]}. 표 첫 칸 묶음 이름, 둘째 칸 항목(쉼표)."""
    try:
        text = (root / "layout.md").read_text(encoding="utf-8")
    except OSError:
        return {}
    m = BUNDLE_HEAD_RE.search(text)
    if not m:
        return {}
    out: dict[str, list[str]] = {}
    for line in text[m.end():].splitlines()[1:]:
        if line.startswith("#"):
            break
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not re.fullmatch(r"[a-z][a-z0-9-]*", cells[0]):
            continue   # 머리줄·구분줄·빈 줄
        out[cells[0]] = [x.strip().strip("`") for x in cells[1].split(",") if x.strip()]
    return out


class _BundleParser(HTMLParser):
    """data-bundle 안의 data-item 을 순서대로 모은다 — [(묶음, [(항목, 클래스)])]"""
    VOID = {"img", "br", "hr", "input", "meta", "link", "source", "wbr", "area", "col", "embed", "track"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str | None] = []   # 열린 요소마다 그 요소가 연 묶음 이름(없으면 None)
        self.found: list[tuple[str, list[tuple[str, str]]]] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        bundle = a.get("data-bundle")
        if bundle:
            self.found.append((bundle, []))
        open_b = any(x for x in self.stack)
        if a.get("data-item") and (open_b or bundle) and self.found:
            # 상태 수식어(is-*)는 부품이 아니다 — due 와 due is-done 은 같은 부품의 다른 상태
            parts = sorted(c for c in (a.get("class") or "").split() if not c.startswith("is-"))
            self.found[-1][1].append((a["data-item"], " ".join(parts)))
        if tag not in self.VOID:
            self.stack.append(bundle)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag("img", attrs)   # 스스로 닫는 태그는 쌓지 않는다

    def handle_endtag(self, tag):
        if tag not in self.VOID and self.stack:
            self.stack.pop()


def check_bundles(root: Path, files: list[Path], errors: list[str], warnings: list[str]) -> None:
    declared = read_bundles(root)
    seen: dict[tuple[str, str, str], tuple[str, str]] = {}   # (너비, 묶음, 항목) → (클래스, 처음 본 화면)
    used: set[str] = set()
    for f in files:
        rel = str(f.relative_to(root))
        width = "desktop" if "/desktop/" in f.as_posix() else "mobile"
        p = _BundleParser()
        try:
            p.feed(strip_scripts(f.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001 — 깨진 HTML 은 다른 검사가 잡는다
            continue
        for name, items in p.found:
            used.add(name)
            if name not in declared:
                errors.append(f"{rel}: layout.md 「데이터 묶음」 표에 없는 묶음 — data-bundle=\"{name}\"")
                continue
            order = declared[name]
            names = [i for i, _ in items]
            unknown = [i for i in names if i not in order]
            if unknown:
                errors.append(f"{rel}: 묶음 {name} 에 정하지 않은 항목 — {', '.join(unknown)}")
                continue
            if names != sorted(names, key=order.index):
                errors.append(f"{rel}: 묶음 {name} 의 항목 순서가 표와 다르다 — {', '.join(names)} (표: {', '.join(order)})")
            if not names:
                errors.append(f"{rel}: 묶음 {name} 에 data-item 이 없다")
            for item, cls in items:
                key = (width, name, item)
                if key in seen and seen[key][0] != cls:
                    errors.append(f"{rel}: 묶음 {name}.{item} 의 부품이 {seen[key][1]} 와 다르다 — "
                                  f"\"{cls or '(없음)'}\" ↔ \"{seen[key][0] or '(없음)'}\"")
                seen.setdefault(key, (cls, rel))
    for name in sorted(set(declared) - used):
        warnings.append(f"layout.md 의 묶음 {name} 을 쓰는 화면이 없다")


def check_kit(root: Path, errors: list[str]) -> None:
    """확정 전 시안의 키트 파일이 키트와 다르면 위반 — 부품을 시안 폴더에서만 고치면 다음 요청이 못 쓴다."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from sync_kit import differing, kit_sources, mockup_status
    if mockup_status(root) == "approved":
        return   # 확정된 시안은 그 시점의 기록
    src = kit_sources(root)
    for name in differing(root):
        origin = src[name].relative_to(src[name].parent.parent) if name == "theme.css" else name
        errors.append(f"{name}: 키트와 다르다 — 키트(kit/{origin})에 고치고 sync_kit.py 로 옮긴다")


# ── 표면 프리셋(테마) ──────────────────────────────────────────────────────
# 시험: 교육 앱에 "연한 색 판" 테마를 즉석에서 만들어 블록·버튼이 모두 연보라가 되고 버튼 모양이 사라졌다.
# 테마는 키트가 정한 변수만, 바탕에는 브랜드 계열 색을 못 쓰게 막는다. 측정(audit.html)이 그 결과를 한 번 더 본다.
THEME_VARS = {"--page-bg", "--page-fill", "--bar-bg", "--block-bg", "--block-mx", "--block-radius", "--block-rule", "--page-gap",
              "--photo-radius", "--photo-bleed", "--photo-bleed-top", "--btn-radius", "--btn-depth", "--btn-depth-primary", "--font-title"}
BG_VARS = {"--page-bg", "--page-fill", "--bar-bg", "--block-bg"}
THEME_LINK_RE = re.compile(r"""<link\b[^>]*href\s*=\s*["'](?:\.\./)+theme\.css["']""", re.I)


def theme_problems(css: str) -> list[str]:
    body = re.sub(r"/\*.*?\*/", "", css, flags=re.S).strip()
    m = re.fullmatch(r":root\s*\{([^{}]*)\}", body)
    if not m:
        return ["테마는 :root { 변수 } 하나만 둔다 — 다른 선택자·@import 금지"]
    out = []
    for decl in [d.strip() for d in m.group(1).split(";") if d.strip()]:
        name, _, value = decl.partition(":")
        name = name.strip()
        if name not in THEME_VARS:
            out.append(f"테마가 바꿀 수 없는 변수 — {name} (허용: 테마 고리 변수)")
        elif name in BG_VARS and "--c-brand" in value:
            out.append(f"{name} 에 브랜드 계열 색 — 바탕·블록·막대에는 쓰지 않는다")
    return out


def check_theme(root: Path, files: list[Path], errors: list[str]) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from sync_kit import SURFACES, surface_of
    try:
        declared = json.loads((root / "screens.json").read_text(encoding="utf-8")).get("surface")
    except (OSError, json.JSONDecodeError):
        return
    if declared is None:
        return
    if declared not in SURFACES:
        errors.append(f"screens.json surface 가 프리셋이 아니다 — {declared!r} (가능: {', '.join(SURFACES)})")
        return
    theme = root / "theme.css"
    if not theme.is_file():
        errors.append("theme.css 가 없다 — sync_kit.py 로 프리셋을 옮긴다")
    else:
        errors.extend(f"theme.css: {p}" for p in theme_problems(theme.read_text(encoding="utf-8")))
    for f in files:
        if not THEME_LINK_RE.search(f.read_text(encoding="utf-8", errors="ignore")):
            errors.append(f"{f.relative_to(root)}: theme.css 를 걸지 않았다 (components.css 다음 줄)")
    if surface_of(root) == "dark-media":
        tok = root / "tokens.css"
        if tok.is_file() and "--mode dark" not in tok.read_text(encoding="utf-8"):
            errors.append("dark-media 인데 tokens.css 가 밝은 토큰이다 — derive.py --mode dark 로 만든다")


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
    check_bundles(root, files, errors, warnings)
    check_kit(root, errors)
    check_theme(root, files, errors)
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
