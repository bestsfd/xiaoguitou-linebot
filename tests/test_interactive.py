"""點選式露營流程：Flex 卡片、日期選擇、投票切換、報名、預算、統計。"""
import json

import pytest

from bot.camp.logic import Ctx, iso_to_label
from bot.camp.store import Store
from bot.camp.ui import (NO_BOOK, cards_for_command, handle_postback, stats_card)
from bot.commands import dispatch

NAMES = {"U_org": "翔暉", "U_a": "阿明", "U_b": "小美"}
G = "Ctap"


@pytest.fixture
def env(tmp_path):
    store = Store(str(tmp_path / "camp.db"))
    req = str(tmp_path / "req")

    def ctx(uid, chat=G):
        return Ctx(chat_id=chat, user_id=uid, name_fn=lambda u: NAMES.get(u, u[-4:]),
                   store=store, req_dir=req)

    def say(uid, text, chat=G):
        c = ctx(uid, chat)
        return dispatch(text, uid, c), c

    def tap(uid, data, params=None, chat=G):
        return handle_postback(data, params, ctx(uid, chat))

    return say, tap, store


def actions(msg):
    found = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") in ("postback", "datetimepicker", "message") and "label" in node:
                found.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(msg.to_dict())
    return found


def labels(msg):
    return [a["label"] for a in actions(msg)]


def test_iso_labels():
    assert iso_to_label("2026-10-31") == "10/31"
    assert iso_to_label("2026-11-07", "2026-11-08") == "11/7-8"
    assert iso_to_label("2026-10-31", "2026-11-01") == "10/31-11/1"
    with pytest.raises(ValueError, match="晚於"):
        iso_to_label("2026-11-02", "2026-11-01")
    with pytest.raises(ValueError):
        iso_to_label("明天")


def test_open_card_has_menu_and_typed_still_works(env):
    say, *_ = env
    out, ctx = say("U_org", "露營開團 秋天團")
    assert "秋天團" in out and "選日期" in out and "翔暉" in out
    cards = cards_for_command("露營開團 秋天團", ctx, out)
    assert len(cards) == 1 and cards[0].type == "flex"
    got = set(labels(cards[0]))
    assert {"選日期", "報名", "填預算", "看統計", "找木屋"} <= got
    datas = {a["data"] for a in actions(cards[0])}
    assert "c=dates" in datas and "c=signup" in datas and "c=stats" in datas
    assert NO_BOOK in json.dumps(cards[0].to_dict(), ensure_ascii=False)
    assert cards[0].quick_reply and len(cards[0].quick_reply.items) >= 5
    # 已有團時仍給選單，打字開團不會蓋掉
    again, ctx2 = say("U_a", "露營開團 另一團")
    assert "已經有" in again
    assert cards_for_command("露營開團 另一團", ctx2, again)


def test_date_picker_then_toggle_votes(env):
    say, tap, store = env
    say("U_org", "露營開團")
    text, cards = tap("U_org", "c=dates")
    assert "開始" in text
    picker = [a for a in actions(cards[0]) if a["type"] == "datetimepicker"]
    assert picker and picker[0]["mode"] == "date" and picker[0]["data"] == "c=date_start"

    text, cards = tap("U_org", "c=date_start", {"date": "2026-10-31"})
    assert "已加入 10/31" in text
    got = actions(cards[0])
    assert "c=vote&i=1" in {a["data"] for a in got}
    assert any(a["type"] == "datetimepicker" and a["label"] == "接結束日" for a in got)

    text, cards = tap("U_org", "c=date_start", {"date": "2026-11-07"})
    assert "已加入 11/7" in text
    text, cards = tap("U_org", "c=date_end&s=2026-11-07", {"date": "2026-11-08"})
    assert "已加入 11/7-8" in text
    _, st = store.active(G)
    assert st["candidates"] == ["10/31", "11/7-8"]
    vote_datas = {a["data"] for a in actions(cards[0])}
    assert "c=vote&i=1" in vote_datas and "c=vote&i=2" in vote_datas

    text, cards = tap("U_a", "c=vote&i=1")
    assert "阿明" in text and "勾選" in text and "10/31" in text
    text, cards = tap("U_a", "c=vote&i=2")
    assert "勾選" in text and "11/7-8" in text
    _, st = store.active(G)
    assert st["members"]["U_a"]["votes"] == [1, 2] and st["members"]["U_a"]["attending"]
    picked = [a for a in actions(cards[0]) if a["data"] == "c=vote&i=1"]
    assert picked and picked[0]["label"].startswith("✓")

    text, _cards = tap("U_a", "c=vote&i=1")
    assert "取消" in text and "10/31" in text
    _, st = store.active(G)
    assert st["members"]["U_a"]["votes"] == [2]

    # 打字投票仍是整組取代，不是切換
    say("U_a", "可以 1")
    _, st = store.active(G)
    assert st["members"]["U_a"]["votes"] == [1]


def test_non_organizer_cannot_pick_dates(env):
    say, tap, _store = env
    say("U_org", "露營開團")
    say("U_org", "候選日期 10/31")
    text, cards = tap("U_a", "c=dates")
    assert "只有主揪" in text and "翔暉" in text
    assert any(a["data"] == "c=vote&i=1" for a in actions(cards[0]))
    text, _cards = tap("U_a", "c=date_one&s=2026-12-01")
    assert "只有主揪" in text


def test_typed_dates_attach_vote_card(env):
    say, _tap, _store = env
    say("U_org", "露營開團")
    out, ctx = say("U_org", "候選日期 10/31-11/1, 11/7-11/8")
    assert "1. 10/31-11/1" in out
    cards = cards_for_command("候選日期 10/31-11/1, 11/7-11/8", ctx, out)
    datas = {a["data"] for a in actions(cards[0])}
    assert datas >= {"c=vote&i=1", "c=vote&i=2"}


def test_signup_buttons(env):
    say, tap, store = env
    say("U_org", "露營開團")
    text, cards = tap("U_a", "c=signup")
    assert "參加" in text
    assert {"參加", "參加+1", "參加+2", "不參加"} <= set(labels(cards[0]))
    text, _cards = tap("U_a", "c=join&g=2")
    assert "阿明" in text and "+2" in text and "4 人" in text  # 主揪 1 + 阿明與 2 位攜伴
    text, _cards = tap("U_b", "c=join&g=0")
    assert "小美" in text and "5 人" in text
    text, _cards = tap("U_a", "c=leave")
    assert "不參加" in text
    _, st = store.active(G)
    assert st["members"]["U_a"]["attending"] is False
    assert st["members"]["U_b"]["attending"] is True


def test_budget_presets_and_typed_custom(env):
    say, tap, store = env
    say("U_org", "露營開團")
    text, cards = tap("U_org", "c=budget")
    assert "預算" in text
    assert {"1000", "2000", "3000", "5000 以上"} <= set(labels(cards[0]))
    text, _cards = tap("U_org", "c=bud&v=5000&plus=1")
    assert "5000" in text and "以上" in text
    _, st = store.active(G)
    assert st["members"]["U_org"]["budget"] == 5000
    assert st["members"]["U_org"]["budget_plus"] is True
    out, _ctx = say("U_org", "預算 3500")
    assert "3500" in out and "以上" not in out
    _, st = store.active(G)
    assert st["members"]["U_org"]["budget"] == 3500
    assert "budget_plus" not in st["members"]["U_org"]
    text, _cards = tap("U_a", "c=bud&v=99999")
    assert "請點預算" in text
    _, st = store.active(G)
    assert "U_a" not in st["members"]


def test_stats_flex_highlights_best_and_budget(env):
    say, tap, _store = env
    say("U_org", "露營開團 秋天團")
    say("U_org", "候選日期 10/31-11/1, 11/7-11/8")
    say("U_org", "可以 1 2")
    say("U_a", "可以 2")
    say("U_b", "參加 +1")
    say("U_org", "預算 3000")
    say("U_a", "預算 2500")
    tap("U_b", "c=bud&v=5000&plus=1")
    text, cards = tap("U_a", "c=stats")
    assert text is None and len(cards) == 1
    raw = json.dumps(cards[0].to_dict(), ensure_ascii=False)
    assert "11/7-11/8" in raw and "10/31-11/1" in raw
    assert "翔暉" in raw and "阿明" in raw
    assert "⭐" in raw and "FFF4D6" in raw
    assert "人數 4 人" in raw
    assert "最低 2500" in raw and "中位 3000" in raw and "平均 3500" in raw
    assert "5000 以上" in raw and NO_BOOK in raw
    # 打字統計仍回文字，並附同一張卡
    out, ctx = say("U_a", "露營統計")
    assert "建議每人 2500" in out and "阿明" in out
    flex = cards_for_command("露營統計", ctx, out)[0]
    assert "平均" in json.dumps(flex.to_dict(), ensure_ascii=False)


def test_search_tap_does_not_book(env):
    say, tap, _store = env
    say("U_org", "露營開團")
    text, _cards = tap("U_org", "c=search")
    assert "還沒有人投票" in text
    say("U_org", "候選日期 10/31")
    say("U_org", "可以 1")
    typed, _ctx = say("U_org", "找木屋")
    assert typed == "已整理好條件，正在幫大家找木屋，找到會貼候選上來"
    text, cards = tap("U_a", "c=search")
    assert typed in text and "不會代訂或付款" in text
    assert NO_BOOK in json.dumps(cards[0].to_dict(), ensure_ascii=False)


def test_end_before_start_and_unknown_postback(env):
    say, tap, _store = env
    say("U_org", "露營開團")
    text, cards = tap("U_org", "c=date_end&s=2026-11-08", {"date": "2026-11-01"})
    assert "晚於" in text and cards
    assert tap("U_a", "c=not-a-button") == (None, [])
    assert tap("U_a", "hello") == (None, [])


def test_fun_commands_unchanged_when_plan_open(env):
    say, _tap, _store = env
    out, ctx = say("U_org", "露營開團")
    rolled, ctx2 = say("U_a", "骰子 1")
    assert "你擲出了" in rolled
    assert cards_for_command("骰子 1", ctx2, rolled) == []
    assert cards_for_command("露營開團", ctx, out)


def test_reply_sends_text_plus_flex(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "tok")
    from unittest.mock import patch
    from bot import line_api
    from bot.camp.ui import menu_card
    card = menu_card({"name": "秋天團", "organizer_name": "翔暉"})
    with patch("linebot.v3.messaging.MessagingApi.reply_message") as rm:
        line_api.reply("rtok", "開團了", extra=[card])
    req = rm.call_args.args[0]
    assert req.reply_token == "rtok"
    assert req.messages[0].text == "開團了" and req.messages[1].type == "flex"
    assert req.to_dict()["messages"][1]["contents"]["type"] == "carousel"
    with patch("linebot.v3.messaging.MessagingApi.reply_message") as rm:
        line_api.reply("rtok", "", extra=[card])
    assert rm.call_args.args[0].messages[0].type == "flex"


def test_stats_card_direct_shape():
    state = {
        "name": "團", "organizer_name": "翔暉", "candidates": ["10/31"],
        "area": "", "wishes": [],
        "members": {"U1": {"name": "翔暉", "attending": True, "guests": 0,
                           "budget": 1000, "votes": [1]}},
    }
    raw = json.dumps(stats_card(state).to_dict(), ensure_ascii=False)
    assert "最低 1000" in raw and "中位 1000" in raw and "平均 1000" in raw
    assert "翔暉" in raw and "⭐" in raw
