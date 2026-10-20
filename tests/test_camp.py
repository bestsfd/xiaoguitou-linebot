import json
from unittest.mock import MagicMock, patch

import pytest

from bot.camp import logic
from bot.camp.logic import Ctx, compute_stats, parse_dates, parse_guests, parse_nums
from bot.camp.store import Store
from bot.commands import dispatch

NAMES = {"U_org": "翔暉", "U_a": "阿明", "U_b": "小美", "U_c": "大雄"}
G = "Cgroup1"


@pytest.fixture
def env(tmp_path):
    store = Store(str(tmp_path / "camp.db"))
    req = str(tmp_path / "req")

    def say(uid, text, chat=G):
        ctx = Ctx(chat_id=chat, user_id=uid, name_fn=lambda u: NAMES.get(u, u[-4:]),
                  store=store, req_dir=req)
        return dispatch(text, uid, ctx)
    return say, store, req


def test_parsing():
    assert parse_dates(["10/31-11/1,", "11/7-11/8"]) == ["10/31-11/1", "11/7-11/8"]
    assert parse_dates(["10/31-11/1，11/7-8"]) == ["10/31-11/1", "11/7-8"]
    with pytest.raises(ValueError):
        parse_dates(["下週"])
    assert parse_nums(["1", "3"]) == [1, 3]
    assert parse_nums(["3,1,1"]) == [1, 3]
    assert parse_nums(["啊"]) is None and parse_nums([]) is None
    assert parse_guests(["+2"]) == 2 and parse_guests(["＋1"]) == 1 and parse_guests([]) == 0


def test_no_plan_and_single_active(env):
    say, *_ = env
    assert "沒有進行中" in say("U_a", "預算 3000")
    assert "開團" in say("U_org", "露營開團 秋天團")
    assert "已經有" in say("U_a", "露營開團 另一團")
    assert "已關閉" in say("U_org", "露營取消")
    assert "開團" in say("U_a", "露營開團 新團")


def test_only_organizer_sets_dates(env):
    say, *_ = env
    say("U_org", "露營開團")
    assert "只有主揪" in say("U_a", "候選日期 10/31-11/1")
    assert "1. 10/31-11/1" in say("U_org", "候選日期 10/31-11/1, 11/7-11/8")
    assert "看不懂" in say("U_org", "候選日期 明天")


def test_voting_replaces_and_validates(env):
    say, store, _ = env
    say("U_org", "露營開團")
    say("U_org", "候選日期 10/31-11/1 11/7-11/8 11/14-11/15")
    assert say("U_a", "可以啊") is None
    assert "沒有第 9" in say("U_a", "可以 9")
    say("U_a", "可以 1 3")
    say("U_a", "投票 2")  # 取代
    _, st = store.active(G)
    assert st["members"]["U_a"]["votes"] == [2] and st["members"]["U_a"]["attending"]


def test_stats_and_request_file(env):
    say, store, req = env
    say("U_org", "露營開團 秋天團")
    say("U_org", "候選日期 10/31-11/1, 11/7-11/8")
    say("U_org", "可以 1 2"); say("U_a", "可以 2"); say("U_b", "可以 1 2")
    say("U_c", "參加 +2"); say("U_c", "不參加"); say("U_b", "參加 +1")
    say("U_org", "預算 3000"); say("U_a", "預算 2500"); say("U_b", "預算 4,000")
    say("U_a", "需求 可帶狗"); say("U_b", "需求 有冷氣"); say("U_org", "地區 台中2小時內")
    s = compute_stats(store.active(G)[1])
    assert [p["count"] for p in s["per_date"]] == [2, 3]
    assert [p["date"] for p in s["best"]] == ["11/7-11/8"]
    assert s["headcount"] == 4  # 3 人 + 小美攜 1
    assert s["budget"] == {"min": 2500, "median": 3000, "max": 4000, "suggested": 2500}
    out = say("U_a", "露營統計")
    assert "11/7-11/8" in out and "建議每人 2500" in out and "可帶狗" in out and "阿明" in out
    assert "4 人" in say("U_a", "人數")

    msg = say("U_org", "找木屋")
    assert msg == "已整理好條件，正在幫大家找木屋，找到會貼候選上來"
    import os
    files = os.listdir(req)
    assert len(files) == 1 and files[0].startswith(G + "-")
    data = json.load(open(os.path.join(req, files[0]), encoding="utf-8"))
    assert data["best_date"] == "11/7-11/8" and data["headcount"] == 4
    assert data["budget_per_person"] == 2500 and data["budget_total"] == 10000
    assert data["area"] == "台中2小時內" and data["wishes"] == ["可帶狗", "有冷氣"]


def test_search_requires_votes(env):
    say, *_ = env
    say("U_org", "露營開團")
    assert "還沒有人投票" in say("U_org", "找木屋")


def test_options_pick_confirm(env, tmp_path):
    say, store, _ = env
    say("U_org", "露營開團")
    assert "還沒有木屋" in say("U_a", "已選 1")
    opts = [{"name": "森林木屋A", "price": "NT$8000/晚", "link": "https://a", "note": "可帶狗"},
            {"name": "湖畔木屋B", "price": "NT$9500/晚", "link": "https://b", "note": "有烤肉區"}]
    f = tmp_path / "o.json"; f.write_text(json.dumps(opts, ensure_ascii=False), encoding="utf-8")
    import post_options
    push = MagicMock()
    assert post_options.main([G, str(f)], store=store, push=push) == 0
    to, text = push.call_args.args
    assert to == G and "1. 森林木屋A" in text and "https://b" in text and "已選" in text
    assert "請回" in say("U_a", "已選 5")
    say("U_a", "已選 2"); say("U_b", "已選 2"); say("U_org", "已選 1")
    out = say("U_org", "確定訂")
    assert "湖畔木屋B" in out and "翔暉" in out and "不會代訂" in out
    assert store.active(G)[1]["chosen"] == 2


def test_post_options_uses_push_message(env, tmp_path, monkeypatch):
    say, store, _ = env
    say("U_org", "露營開團")
    f = tmp_path / "o.json"; f.write_text('{"options":[{"name":"X","price":"1"}]}', encoding="utf-8")
    import post_options
    with patch("linebot.v3.messaging.MessagingApi.push_message") as pm:
        post_options.main([G, str(f)], store=store)
    req = pm.call_args.args[0]
    assert req.to == G and "X" in req.messages[0].text


def test_display_name_fallback():
    from bot import line_api
    src = MagicMock(type="group", group_id="G9")
    with patch("linebot.v3.messaging.MessagingApi.get_group_member_profile",
               return_value=MagicMock(display_name="阿華")):
        assert line_api.display_name(src, "U_x1") == "阿華"
    with patch("linebot.v3.messaging.MessagingApi.get_group_member_profile",
               side_effect=Exception("403")):
        assert line_api.display_name(src, "Uabcd1234") == "1234"


def test_one_to_one_keyed_by_user(env):
    say, store, _ = env
    say("U_a", "露營開團 個人", chat="U_a")
    assert store.active("U_a")[0] and not store.active(G)[0]
