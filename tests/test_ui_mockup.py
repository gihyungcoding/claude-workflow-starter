"""ui-mockup 스킬의 스크립트 — 정적 검사·캔버스·그림 정리, 그리고 질문 기록 훅.

시안 검사는 "시안을 만든 에이전트의 자기 보고"를 대신한다. 블라인드 검증에서 두 에이전트 모두
"링크·주 버튼·h1 확인함"이라고 보고했으므로, 검사기가 거짓 통과를 내면 아무도 모른다.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from helpers import ProjectTestCase

UM = "../.claude/skills/ui-mockup/scripts"
CHECK = f"{UM}/check_mockup.py"
CANVAS = f"{UM}/build_canvas.py"
PRUNE = f"{UM}/prune_assets.py"
HOOK = "hooks/log_question.py"
OUT = "workflow_design/01_brief/mockup/REQ-001"
STARTER = Path(__file__).resolve().parent.parent

HEAD = '<!doctype html><html lang="ko"><head><meta charset="utf-8"><link id="tokens" rel="stylesheet" href="{up}tokens.css"></head><body>'


def page(body: str, up: str = "../") -> str:
    return HEAD.format(up=up) + body + "</body></html>"


class MockupTestCase(ProjectTestCase):
    def setUp(self):
        super().setUp()
        self.project.write(f"{OUT}/tokens.css", ":root{--c-brand:#2F6FDB}\n")
        self.project.write(f"{OUT}/assets/fluent/calendar.svg", "<svg/>")
        self.project.write(f"{OUT}/assets/fluent/unused.svg", "<svg/>")
        self.project.write(f"{OUT}/assets/fluent/LICENSE.md", "MIT\n")
        self.screens = {
            "app": "모임",
            "badges": {"확정": "is-brand"},
            "groups": ["모임"],
            "screens": [
                {"id": "home", "title": "홈", "group": "모임", "purpose": "지금 상황", "policies": ["정책 1"],
                 "branches": [{"to": "detail", "label": "모임을 누르면"}]},
                {"id": "detail", "title": "상세", "group": "모임"},
            ],
            "desktop": [{"id": "d-home", "title": "홈", "merges": ["home", "detail"], "pattern": "split"}],
        }
        self.pages = {
            "screens/home.html": page('<h1>홈</h1><a class="row" href="detail.html"><img src="../assets/fluent/calendar.svg" alt="">'
                                      '<span class="badge is-brand">확정</span></a><a class="btn primary" href="detail.html">만들기</a>'
                                      '<div class="range" style="--from:20%;--to:60%"></div>'),
            "screens/detail.html": page('<h1>상세</h1><a data-back>뒤로</a><a data-stay="저장했어요">저장</a>'),
            "screens/desktop/d-home.html": page('<h1>홈</h1><a href="d-home.html">새로고침</a>', up="../../"),
        }
        self.save()

    def save(self) -> None:
        self.project.write_json(f"{OUT}/screens.json", self.screens)
        for rel, html in self.pages.items():
            self.project.write(f"{OUT}/{rel}", html)

    def check(self) -> tuple[int, dict]:
        return self.project.run_json(CHECK, OUT, "--json")

    def assertFlags(self, needle: str) -> None:
        self.save()
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertTrue(any(needle in e for e in out["errors"]), f"{needle!r} 없음: {out['errors']}")


class CheckMockupTest(MockupTestCase):
    def test_valid_mockup_passes(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)

    def test_two_h1(self):
        self.pages["screens/detail.html"] = page("<h1>a</h1><h1>b</h1>")
        self.assertFlags("h1 이 2개")

    def test_two_primary_buttons(self):
        self.pages["screens/detail.html"] = page('<h1>a</h1><button class="btn primary">a</button><a class="primary btn full">b</a>')
        self.assertFlags("주 버튼")

    def test_inline_style(self):
        self.pages["screens/detail.html"] = page('<h1>a</h1><p style="color:red">x</p>')
        self.assertFlags("인라인 style")

    def test_color_in_style_block(self):
        self.pages["screens/detail.html"] = page("<style>.x{color:#ff0000}</style><h1>a</h1>")
        self.assertFlags("색 값")

    def test_emoji(self):
        self.pages["screens/detail.html"] = page("<h1>축하해요 \U0001F389</h1>")
        self.assertFlags("이모지")

    def test_broken_link(self):
        self.pages["screens/detail.html"] = page('<h1>a</h1><a href="nowhere.html">x</a>')
        self.assertFlags("nowhere.html")

    def test_missing_image(self):
        self.pages["screens/detail.html"] = page('<h1>a</h1><img src="../assets/fluent/none.svg" alt="">')
        self.assertFlags("이미지 파일이 없다")

    def test_missing_screen_file(self):
        self.screens["screens"].append({"id": "ghost", "group": "모임"})
        self.screens["desktop"][0]["merges"].append("ghost")
        self.assertFlags("ghost")

    def test_branch_to_unknown_screen(self):
        self.screens["screens"][0]["branches"] = [{"to": "elsewhere"}]
        self.assertFlags("elsewhere")

    def test_mobile_screen_must_belong_to_exactly_one_desktop_view(self):
        self.screens["desktop"][0]["merges"] = ["home"]
        self.assertFlags("detail: 데스크톱 화면 0개")
        self.screens["desktop"].append({"id": "d-home", "merges": ["detail", "home"]})
        self.assertFlags("home: 데스크톱 화면 2개")

    def test_local_style_block_is_a_warning(self):
        self.pages["screens/detail.html"] = page("<style>.x{gap:var(--stack-s)}</style><h1>a</h1>")
        self.save()
        code, out = self.check()
        self.assertEqual(code, 0)
        self.assertTrue(any("<style>" in w and w.startswith("screens/detail.html") for w in out["warnings"]))

    def test_minimap_css_variables_are_allowed_inline(self):
        self.pages["screens/detail.html"] = page('<h1>a</h1><div class="picker-mini-map" style="--cols:20;--rows:8"><span class="picker-mini-view" style="--x:5%;--y:0%;--w:25%;--h:60%"></span></div>')
        self.save()
        self.assertEqual(self.check()[0], 0)

    def test_minimap_counts_must_be_whole_numbers(self):
        self.pages["screens/detail.html"] = page('<h1>a</h1><div class="picker-mini-map" style="--cols:20;color:red"></div>')
        self.save()
        self.assertEqual(self.check()[0], 1)

    def test_desktop_is_optional(self):
        del self.screens["desktop"]
        self.save()
        self.assertEqual(self.check()[0], 0)

    def test_unknown_badge_color_is_a_warning(self):
        self.pages["screens/detail.html"] = page('<h1>a</h1><span class="badge is-danger">실패</span>')
        self.save()
        code, out = self.check()
        self.assertEqual(code, 0)
        self.assertTrue(any("is-danger" in w for w in out["warnings"]))

    def test_unreadable_folder_is_an_argument_error(self):
        self.assertEqual(self.project.run(CHECK, "workflow_design/01_brief/mockup/REQ-999").returncode, 2)


class BuildCanvasTest(MockupTestCase):
    def data(self) -> dict:
        html = self.project.path(f"{OUT}/index.html").read_text(encoding="utf-8")
        m = re.search(r'<script id="hd-data" type="application/json">(.*?)</script>', html, re.S)
        return json.loads(m.group(1).replace("<\\/", "</"))

    def test_builds_mobile_and_desktop_rows(self):
        out = self.project.run(CANVAS, OUT)
        self.assertEqual(out.returncode, 0, out.stderr)
        d = self.data()
        mobile = [r for r in d["rows"] if not r.get("desk")]
        desk = [r for r in d["rows"] if r.get("desk")]
        self.assertEqual([s["id"] for s in mobile[0]["screens"]], ["home", "detail"])
        self.assertEqual(desk[0]["group"], "모임")
        card = desk[0]["screens"][0]
        self.assertEqual((card["id"], card["file"], card["merges"]), ("d-home", "screens/desktop/d-home.html", ["home", "detail"]))
        self.assertEqual(d["desk_card"], {"w": 1280, "h": 800})
        self.assertEqual(d["arrows"], [{"from": "home", "to": "detail", "label": "모임을 누르면"}])

    def test_copies_audit_page_and_palette_script(self):
        self.project.run(CANVAS, OUT)
        for name in ("audit.html", "palette.js", "foundation.html", "components.html"):
            with self.subTest(name=name):
                self.assertTrue(self.project.path(f"{OUT}/{name}").is_file())

    def test_side_lane_labels_are_staggered(self):
        # 다른 줄로 넘어가는 화살표 이름표가 같은 자리에 겹치던 문제 — 놓인 자리를 피해 민다
        tpl = (STARTER / ".claude/skills/ui-mockup/scripts/canvas_template.html").read_text(encoding="utf-8")
        self.assertIn("ly = freeY(lx, (sg + tg) / 2)", tpl)

    def test_audit_checks_button_wrap_aside_offset_and_state_frames(self):
        audit = (STARTER / ".claude/skills/ui-mockup/scripts/audit.html").read_text(encoding="utf-8")
        for needle in ("버튼 글자가", "보조 열과 본문 첫 박스", "기본 화면(", "박스 폭이 다르다"):
            with self.subTest(needle=needle):
                self.assertIn(needle, audit)

    def test_desktop_kit_keeps_button_text_on_one_line_and_header_full_width(self):
        css = (STARTER / ".claude/skills/ui-mockup/kit/desktop.css").read_text(encoding="utf-8")
        self.assertIn(".main.has-aside > .d-head { grid-column: 1 / -1; }", css)
        self.assertIn("white-space: nowrap", css)
        self.assertIn(".aside .btn-row", css)

    def test_feedback_header_is_ours(self):
        self.project.run(CANVAS, OUT)
        html = self.project.path(f"{OUT}/index.html").read_text(encoding="utf-8")
        self.assertIn("[ui-mockup 수정 요청]", html)
        self.assertNotIn("k-style-ui-ux 수정 요청", html)

    def test_built_canvas_obeys_path_rules_and_static_check(self):
        self.project.run(CANVAS, OUT)
        self.assertEqual(self.project.run("hooks/check_artifact_paths.py", "--all").returncode, 0)
        self.assertEqual(self.check()[0], 0)


class PruneAssetsTest(MockupTestCase):
    def test_removes_only_unreferenced_files(self):
        out = self.project.run(PRUNE, OUT)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(self.project.path(f"{OUT}/assets/fluent/calendar.svg").is_file())
        self.assertTrue(self.project.path(f"{OUT}/assets/fluent/LICENSE.md").is_file())
        self.assertFalse(self.project.path(f"{OUT}/assets/fluent/unused.svg").exists())

    def test_keeps_credited_photos(self):
        self.project.write(f"{OUT}/assets/photos/hall.jpg", "x")
        self.project.write_json(f"{OUT}/credits.json", [{"slot": "hero", "file": "assets/photos/hall.jpg", "license": "CC0"}])
        self.project.run(PRUNE, OUT)
        self.assertTrue(self.project.path(f"{OUT}/assets/photos/hall.jpg").is_file())

    def test_dry_run_changes_nothing(self):
        self.project.run(PRUNE, OUT, "--dry-run")
        self.assertTrue(self.project.path(f"{OUT}/assets/fluent/unused.svg").is_file())


class LogQuestionHookTest(ProjectTestCase):
    def ask(self, event: str = "PreToolUse", tool: str = "AskUserQuestion") -> int:
        payload = {"hook_event_name": event, "tool_name": tool,
                   "tool_input": {"questions": [{"header": "동시 수정", "question": "어떻게?"}]}}
        return self.project.run(HOOK, stdin=json.dumps(payload)).returncode

    def lines(self, rid: str) -> list[dict]:
        p = self.project.path(f"workflow_design/09_telemetry/{rid}.jsonl")
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []

    def test_records_question_and_answer_for_refining_request(self):
        self.project.write_json("workflow_design/01_brief/BRIEF_REQ-001.json", {"id": "REQ-001", "status": "refining"})
        self.assertEqual(self.ask("PreToolUse"), 0)
        self.assertEqual(self.ask("PostToolUse"), 0)
        got = self.lines("REQ-001")
        self.assertEqual([e["event"] for e in got], ["question_asked", "question_answered"])
        self.assertEqual(got[0]["data"], {"n": 1, "headers": ["동시 수정"]})
        self.assertNotIn("어떻게", json.dumps(got, ensure_ascii=False))   # 질문 본문은 남기지 않는다

    def test_locked_request_is_not_a_target(self):
        self.project.write_json("workflow_design/01_brief/BRIEF_REQ-001.json", {"id": "REQ-001", "status": "locked"})
        self.ask()
        self.assertEqual(self.lines("REQ-001"), [])

    def test_single_active_task_is_the_fallback_target(self):
        self.project.write("memory-bank/TASK-001/activeContext.md", "---\ntask_id: TASK-001\nstatus: ACTIVE\nphase: \"2b\"\n---\n")
        self.ask()
        self.assertEqual([e["event"] for e in self.lines("TASK-001")], ["question_asked"])

    def test_ids_from_file_contents_cannot_escape_the_telemetry_folder(self):
        self.project.write_json("workflow_design/01_brief/BRIEF_REQ-001.json", {"id": "../../escaped", "status": "refining"})
        self.project.write("memory-bank/TASK-001/activeContext.md", "---\ntask_id: ../../../escaped2\nstatus: ACTIVE\n---\n")
        self.assertEqual(self.ask(), 0)
        self.assertEqual(list(self.project.root.rglob("escaped*")), [])
        self.assertFalse(self.project.path("workflow_design/09_telemetry").exists())

    def test_other_tools_and_garbage_never_block(self):
        self.assertEqual(self.ask(tool="Write"), 0)
        self.assertEqual(self.project.run(HOOK, stdin="{not json").returncode, 0)

    def test_hook_is_registered_for_both_sides(self):
        hooks = json.loads((STARTER / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
        for side in ("PreToolUse", "PostToolUse"):
            with self.subTest(side=side):
                cmds = [h["command"] for m in hooks[side] if m.get("matcher") == "AskUserQuestion" for h in m["hooks"]]
                self.assertTrue(any("log_question.py" in c for c in cmds))


if __name__ == "__main__":
    unittest.main()


class DataBundleTest(MockupTestCase):
    """같은 데이터 묶음은 같은 너비의 화면끼리 같은 순서·같은 부품 (시험 실행: 금액이 화면마다 다른 부품)"""

    LAYOUT = "# 배치\n\n## 데이터 묶음\n\n| 묶음 | 항목(순서) | 모바일 | 데스크톱 |\n|---|---|---|---|\n| `payment` | amount, deadline, account | 금액 크게 | 카드 |\n"
    PAY = ('<section class="block" data-bundle="payment"><p class="pay-amount" data-item="amount">297,000원</p>'
           '<span class="countdown" data-item="deadline">11:59까지</span><div class="row" data-item="account">계좌</div></section>')

    def setUp(self):
        super().setUp()
        self.project.write(f"{OUT}/layout.md", self.LAYOUT)

    def test_same_bundle_same_parts_passes(self):
        self.pages["screens/home.html"] = page("<h1>홈</h1>" + self.PAY)
        self.pages["screens/detail.html"] = page("<h1>상세</h1>" + self.PAY)
        self.save()
        self.assertEqual(self.check()[0], 0)

    def test_item_with_different_part_fails(self):
        self.pages["screens/home.html"] = page("<h1>홈</h1>" + self.PAY)
        self.pages["screens/detail.html"] = page("<h1>상세</h1>" + self.PAY.replace('class="pay-amount"', 'class="row-title"'))
        self.assertFlags("payment.amount 의 부품이")

    def test_order_differs_from_table_fails(self):
        swapped = ('<section data-bundle="payment"><span class="countdown" data-item="deadline">x</span>'
                   '<p class="pay-amount" data-item="amount">y</p></section>')
        self.pages["screens/detail.html"] = page("<h1>상세</h1>" + swapped)
        self.assertFlags("항목 순서가 표와 다르다")

    def test_undeclared_bundle_fails(self):
        self.pages["screens/detail.html"] = page('<h1>상세</h1><div data-bundle="ticket"><p data-item="seat">A1</p></div>')
        self.assertFlags("표에 없는 묶음")

    def test_mobile_and_desktop_may_differ(self):
        self.pages["screens/home.html"] = page("<h1>홈</h1>" + self.PAY)
        self.pages["screens/desktop/d-home.html"] = page("<h1>홈</h1>" + self.PAY.replace('class="pay-amount"', 'class="stat-num"'), up="../../")
        self.save()
        self.assertEqual(self.check()[0], 0)

    def test_missing_item_is_allowed_but_order_kept(self):
        self.pages["screens/home.html"] = page("<h1>홈</h1>" + self.PAY)
        no_account = self.PAY.replace('<div class="row" data-item="account">계좌</div>', "")
        self.pages["screens/detail.html"] = page("<h1>상세</h1>" + no_account)
        self.save()
        self.assertEqual(self.check()[0], 0)

    def test_state_modifiers_are_same_part(self):
        self.pages["screens/home.html"] = page("<h1>홈</h1>" + self.PAY)
        self.pages["screens/detail.html"] = page("<h1>상세</h1>" + self.PAY.replace('class="countdown"', 'class="countdown is-done"'))
        self.save()
        self.assertEqual(self.check()[0], 0)


SYNC = f"{UM}/sync_kit.py"
APP = f"{UM}/build_app_canvas.py"
UIMAP = f"{UM}/ui_map.py"
KIT = STARTER / ".claude/skills/ui-mockup/kit"
ROOT = "workflow_design/01_brief/mockup"


class FloorTest(MockupTestCase):
    """하한 — 상한만 재면 빈 화면이 통과한다 (시험 2: 내용이 위 절반에서 끝나고 누를 것·서비스 이름이 없는 홈, 데스크톱에만 있는 규칙,
    사진 없는 안내 화면에 SNS 피드 표면)"""

    def setUp(self):
        super().setUp()
        self.screens["screens"][0]["kind"] = "home"
        self.pages["screens/home.html"] = self.pages["screens/home.html"].replace("<h1>홈</h1>", '<p class="eyebrow">모임</p><h1>홈</h1>', 1)
        self.save()

    def test_home_with_app_name_and_action_passes(self):
        self.assertEqual(self.check()[0], 0, self.check()[1])

    def test_missing_app_field_fails(self):
        del self.screens["app"]
        self.assertFlags("app(서비스 이름)이 없다")

    def test_app_name_missing_on_home_fails(self):
        self.screens["app"] = "썰리그"
        self.assertFlags("홈 화면에 서비스 이름(썰리그)이 없다")

    def test_home_without_anything_to_press_fails(self):
        self.pages["screens/home.html"] = page('<p class="eyebrow">모임</p><h1>홈</h1><p>이번 주 일정</p>')
        self.assertFlags("홈 화면에 누를 것이 없다")

    def test_closed_button_counts_as_the_action_slot(self):
        self.pages["screens/home.html"] = page('<p class="eyebrow">모임</p><h1>홈</h1>'
                                               '<span class="btn full is-closed" aria-disabled="true">썰 풀기 — 곧 열려</span>')
        self.save()
        self.assertEqual(self.check()[0], 0, self.check()[1])

    def test_state_screens_are_not_held_to_home_floors(self):
        self.screens["screens"].append({"id": "home--empty", "title": "빈", "group": "모임", "kind": "home"})
        self.screens["desktop"][0]["merges"].append("home--empty")
        self.pages["screens/home--empty.html"] = page("<h1>아직 없어</h1>")
        self.save()
        self.assertEqual(self.check()[0], 0, self.check()[1])

    def test_desktop_only_section_fails(self):
        self.pages["screens/desktop/d-home.html"] = page('<h1>홈</h1><section><h2>이 대회는 이렇게 돌아가</h2></section>', up="../../")
        self.assertFlags("데스크톱에만 있는 구역 「이 대회는 이렇게 돌아가」")

    def test_section_on_both_widths_passes(self):
        self.pages["screens/detail.html"] = page('<h1>상세</h1><a data-back>뒤로</a><h2>이 대회는 이렇게 돌아가</h2>')
        self.pages["screens/desktop/d-home.html"] = page('<h1>홈</h1><section><h2>이 대회는 이렇게 돌아가</h2></section>', up="../../")
        self.save()
        self.assertEqual(self.check()[0], 0, self.check()[1])

    def test_marked_desktop_only_section_is_a_warning(self):
        self.pages["screens/desktop/d-home.html"] = page(
            '<h1>홈</h1><section data-desktop-only="단축키는 키보드에서만"><h2>단축키</h2></section>', up="../../")
        self.save()
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertTrue(any("단축키는 키보드에서만" in w for w in out["warnings"]), out)

    def test_photo_surface_without_photos_fails(self):
        self.screens["surface"] = "edge"
        self.save()
        self.project.run(SYNC, OUT)
        link = '<link rel="stylesheet" href="{up}theme.css">'
        for rel in list(self.pages):
            up = "../../" if "/desktop/" in rel else "../"
            self.pages[rel] = self.pages[rel].replace("<body>", link.format(up=up) + "<body>", 1)
        self.assertFlags("사진·썸네일이 주인공인 표면인데 사진이 있는 화면이 없다")

    def test_approved_mockup_is_not_remeasured(self):
        del self.screens["app"]
        self.project.write_json("workflow_design/01_brief/BRIEF_REQ-001.json", {"id": "REQ-001", "mockup": {"status": "approved"}})
        self.save()
        self.assertEqual(self.check()[0], 0, self.check()[1])

    def test_audit_measures_fold_fill_and_bundle_pills(self):
        audit = (STARTER / ".claude/skills/ui-mockup/scripts/audit.html").read_text(encoding="utf-8")
        for needle in ("fold_fill: 0.6", "bundle_pills: 1", "job.state", "[data-bundle]"):
            self.assertIn(needle, audit)


class KitSyncTest(MockupTestCase):
    """키트 부품 파일은 sync_kit 으로만 — 확정 전 시안이 키트와 다르면 위반 (시험 실행: 손 cp 로 빠뜨림)"""

    def test_sync_copies_and_records_version(self):
        out = self.project.run(SYNC, OUT)
        self.assertEqual(out.returncode, 0, out.stderr)
        rec = json.loads(self.project.path(f"{OUT}/kit.json").read_text())
        self.assertEqual(set(rec["files"]), {"components.css", "desktop.css", "palette.js", "theme.css"})
        self.assertEqual(rec["surface"], "card-stack")   # 표면을 정하지 않으면 키트 기본
        self.assertEqual(self.project.path(f"{OUT}/components.css").read_text(), (KIT / "components.css").read_text())

    def test_edited_copy_fails_check_while_draft(self):
        self.project.run(SYNC, OUT)
        self.project.write(f"{OUT}/components.css", (KIT / "components.css").read_text() + "\n.mine { color: red; }\n")
        self.assertFlags("components.css: 키트와 다르다")

    def test_approved_mockup_is_a_snapshot(self):
        self.project.run(SYNC, OUT)
        self.project.write(f"{OUT}/components.css", "/* 그 시점의 키트 */")
        self.project.write_json("workflow_design/01_brief/BRIEF_REQ-001.json", {"id": "REQ-001", "mockup": {"status": "approved"}})
        self.save()
        self.assertEqual(self.check()[0], 0)
        self.assertEqual(self.project.run(SYNC, OUT).returncode, 1)   # 확정된 시안에는 다시 복사하지 않는다


class AppCanvasTest(ProjectTestCase):
    """요청별 시안 → 화면마다 가장 최근 정본 하나 (시험 실행: 대체 대응표를 손으로 정리)"""

    def req(self, rid: str, screens: list[dict], status: str = "approved") -> None:
        self.project.write_json(f"{ROOT}/{rid}/screens.json", {"groups": ["예매"], "screens": screens})
        for s in screens:
            self.project.write(f"{ROOT}/{rid}/screens/{s['id']}.html", page(f"<h1>{rid} {s['id']}</h1>"))
        self.project.write_json(f"workflow_design/01_brief/BRIEF_{rid}.json", {"id": rid, "mockup": {"status": status}})

    def build(self, *args: str) -> dict:
        code, res = self.project.run_json(APP, ROOT, "--json", *args)
        self.assertEqual(code, 0, res)
        return res

    def app(self) -> dict:
        return json.loads(self.project.path(f"{ROOT}/app-screens.json").read_text())["screens"]

    def test_later_request_wins_and_drops_old_states(self):
        self.req("REQ-001", [{"id": "seat", "group": "예매"}, {"id": "seat--error", "group": "예매"}, {"id": "home", "group": "예매"}])
        self.req("REQ-002", [{"id": "seat", "group": "예매"}])
        res = self.build()
        self.assertEqual(res["mobile"], 2)
        app = self.app()
        self.assertEqual(app["seat"]["req"], "REQ-002")
        self.assertEqual(app["home"]["req"], "REQ-001")
        self.assertIn("REQ-001 → REQ-002", app["seat--error"]["replaced"][0])
        html = self.project.path(f"{ROOT}/index.html").read_text()
        self.assertIn("REQ-002/screens/seat.html", html)
        self.assertIn("REQ-001/screens/home.html", html)

    def test_replaces_drops_only_the_named_screen(self):
        self.req("REQ-001", [{"id": "checkout", "group": "예매"}, {"id": "checkout--error", "group": "예매"}])
        self.req("REQ-002", [{"id": "hold", "group": "예매", "replaces": ["REQ-001/checkout"]}])
        self.build()
        app = self.app()
        self.assertIn("replaced", app["checkout"])
        self.assertEqual(app["checkout--error"].get("req"), "REQ-001")   # 남겨야 할 상태 화면이 있을 수 있다

    def test_drafts_are_left_out_unless_asked(self):
        self.req("REQ-001", [{"id": "home", "group": "예매"}])
        self.req("REQ-002", [{"id": "home", "group": "예매"}], status="draft")
        self.assertEqual(self.app_req_after(), "REQ-001")
        self.build("--include-drafts")
        self.assertEqual(self.app()["home"]["req"], "REQ-002")

    def app_req_after(self) -> str:
        self.build()
        return self.app()["home"]["req"]

    def test_base_folder_is_the_bottom_layer(self):
        self.project.write_json("out/screens.json", {"screens": [{"id": "seat"}, {"id": "login"}]})
        for sid in ("seat", "login"):
            self.project.write(f"out/screens/{sid}.html", page(f"<h1>{sid}</h1>"))
        self.req("REQ-002", [{"id": "seats", "group": "예매", "replaces": ["out:seat"]}])
        res = self.build("--base", "out")
        self.assertEqual(res["mobile"], 2)
        self.assertIn("../../../out/screens/login.html", self.project.path(f"{ROOT}/index.html").read_text())

    def test_app_canvas_files_pass_path_rules(self):
        self.req("REQ-001", [{"id": "home", "group": "예매"}])
        self.build()
        out = self.project.run("hooks/check_artifact_paths.py", "--all")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)


class UiMapTest(MockupTestCase):
    """시안이 쓰는 키트 부품마다 프론트 부품 대응 (시험 실행: 새 부품을 태스크 설명에 손으로)"""

    MAP = "docs/product/ui-components.json"

    def setUp(self):
        super().setUp()
        self.pages["screens/home.html"] = page('<h1 class="title">홈</h1><a class="btn primary full" href="detail.html">예매</a>'
                                               '<div class="picker"><div class="picker-mini"></div><button class="seat is-picked">1</button></div>'
                                               '<ol class="timeline"><li class="tl-item"></li></ol>')
        self.save()

    def run_map(self, *args: str) -> tuple[int, dict]:
        return self.project.run_json(UIMAP, OUT, "--map", self.MAP, "--json", *args)

    def test_modifiers_and_sub_parts_are_not_parts(self):
        code, res = self.run_map()
        self.assertEqual(code, 1)
        parts = set(res["used"])
        self.assertTrue({"btn", "picker", "timeline", "title"} <= parts, parts)
        self.assertFalse(parts & {"primary", "full", "picker-mini", "seat", "tl-item", "is-picked"}, parts)

    def test_mapped_parts_pass_and_missing_files_fail(self):
        self.project.write("frontend/Button.tsx", "")
        self.project.write_json(self.MAP, {"parts": {"btn": "frontend/Button.tsx", "title": {"none": "theme 글자"},
                                                     "timeline": {"path": "frontend/Timeline.tsx"}, "picker": "frontend/SeatPicker.tsx"}})
        code, res = self.run_map()
        self.assertEqual(code, 1)
        self.assertEqual({b["part"] for b in res["broken"]}, {"timeline", "picker"})
        self.project.write("frontend/Timeline.tsx", "")
        self.project.write("frontend/SeatPicker.tsx", "")
        self.assertEqual(self.run_map()[0], 0)

    def test_init_adds_missing_parts_as_null(self):
        self.run_map("--init")
        parts = json.loads(self.project.path(self.MAP).read_text())["parts"]
        self.assertIn("picker", parts)
        self.assertIsNone(parts["picker"])


THEMES = KIT / "themes"


class SurfacePresetTest(MockupTestCase):
    """도메인 표면 프리셋 — 정해진 변수만, 바탕에 브랜드색 금지 (시험: 즉석 테마로 교육 앱이 보라로 덮였다)"""

    def setUp(self):
        super().setUp()
        self.screens["surface"] = "edge"
        self.pages["screens/home.html"] = self.pages["screens/home.html"].replace(
            "<h1>홈</h1>", '<h1>홈</h1><img class="photo" src="../assets/fluent/calendar.svg" alt="">', 1)   # edge 는 사진이 주인공
        link = '<link rel="stylesheet" href="{up}theme.css">'
        for rel in list(self.pages):
            up = "../../" if "/desktop/" in rel else "../"
            self.pages[rel] = self.pages[rel].replace("<body>", link.format(up=up) + "<body>", 1)
        self.save()
        self.project.run(SYNC, OUT)

    def test_every_kit_preset_is_valid(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("cm", STARTER / ".claude/skills/ui-mockup/scripts/check_mockup.py")
        cm = importlib.util.module_from_spec(spec); spec.loader.exec_module(cm)
        names = sorted(p.stem for p in THEMES.glob("*.css"))
        self.assertEqual(names, sorted(["card-stack", "flat-dense", "edge", "dark-media", "flat-banded", "chunky"]))
        for p in THEMES.glob("*.css"):
            self.assertEqual(cm.theme_problems(p.read_text()), [], p.name)

    def test_synced_preset_passes(self):
        self.assertEqual(self.check()[0], 0, self.check()[1])
        self.assertEqual(self.project.path(f"{OUT}/theme.css").read_text(), (THEMES / "edge.css").read_text())

    def test_unknown_surface_fails(self):
        self.screens["surface"] = "pastel"
        self.assertFlags("surface 가 프리셋이 아니다")

    def test_screen_without_theme_link_fails(self):
        self.pages["screens/detail.html"] = page("<h1>상세</h1>")
        self.assertFlags("theme.css 를 걸지 않았다")

    def test_brand_on_background_fails_even_if_synced(self):
        self.project.write(f"{OUT}/theme.css", ":root { --block-bg: var(--c-brand-tint); }")
        self.assertFlags("브랜드 계열 색")

    def test_theme_cannot_add_selectors(self):
        self.project.write(f"{OUT}/theme.css", ":root { --page-bg: #fff; }\n.btn { color: red; }")
        self.assertFlags(":root { 변수 } 하나만")

    def test_dark_media_needs_dark_tokens(self):
        self.screens["surface"] = "dark-media"
        self.save()
        self.project.run(SYNC, OUT)
        self.project.write(f"{OUT}/tokens.css", ":root { --c-bg: #F1F2F6; }")
        self.assertFlags("밝은 토큰")


class DarkTokensTest(MockupTestCase):
    def test_dark_mode_keeps_contrast(self):
        out = self.project.run(f"{UM}/../kit/derive.py", "--brand", "#7B3FF2", "--tone", "cool", "--mode", "dark", "-o", "tokens-dark.css")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)   # 대비 기준 미달이면 exit 1
        css = self.project.path("tokens-dark.css").read_text()
        self.assertIn("--mode dark", css)
        bg = re.search(r"--c-bg:\s*#([0-9A-F]{6})", css).group(1)
        self.assertLess(int(bg[:2], 16), 0x30)   # 어두운 바탕


class DomainPartsTest(unittest.TestCase):
    """도메인 부품은 키트 CSS 와 부품 문서에 함께 있어야 쓴다 (시험: 키트에 없어 글자로 때웠다)"""

    def test_parts_are_defined_and_documented(self):
        css = (KIT / "components.css").read_text()
        doc = (KIT / "COMPONENTS.md").read_text()
        for cls in ("photo-tag", "is-4x5", "react", "react-item", "row-amount", "week"):
            self.assertIn(f".{cls}", css, cls)
            self.assertIn(cls, doc, cls)
        self.assertIn("row-trail.is-inline", css)
