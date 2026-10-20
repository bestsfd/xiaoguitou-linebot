"""下個月週末、多選投票、走廊親子木屋與景點。"""
import json
from datetime import date, datetime, timezone

from bot.camp.catalog import next_month_labels
from bot.camp.flexcheck import validate_message
from bot.camp.logic import Ctx, build_request, compute_stats
from bot.camp.places import CABINS, match_cabins
from bot.camp.store import Store
from bot.camp.ui import cards_for_command, handle_postback
from bot.commands import dispatch

NAMES = {"U_org": "翔暉", "U_a": "阿明", "U_b": "小美"}
G = "Copt"


def _env(tmp_path):
    store = Store(str(tmp_path / "camp.db"))

    def ctx(uid):
        return Ctx(chat_id=G, user_id=uid, name_fn=lambda u: NAMES.get(u, u[-4:]),
                   store=store, req_dir=str(tmp_path / "req"))

    def say(uid, text):
        c = ctx(uid)
        return dispatch(text, uid, c), c

    def tap(uid, data, params=None):
        return handle_postback(data, params, ctx(uid))

    return say, tap, store


def _labels(msg):
    found = []

    def walk(node):
        if isinstance(node, dict):
            if "label" in node and node.get("type") in ("postback", "uri", "message", "datetimepicker"):
                found.append(node["label"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(msg.to_dict())
    return found


def test_next_month_weekends_and_holidays():
    assert next_month_labels(date(2026, 10, 20)) == [
        "11/7(六)-11/8(日)", "11/14(六)-11/15(日)",
        "11/21(六)-11/22(日)", "11/28(六)-11/29(日)",
    ]
    october = next_month_labels(date(2026, 9, 15))
    assert "10/9(五)-10/11(日)國慶" in october
    assert "10/24(六)-26(一)光復" in october
    assert "10/10(六)-10/11(日)" not in october
    december = next_month_labels(datetime(2026, 10, 31, 16, 30, tzinfo=timezone.utc))
    assert "12/25(五)-27(日)行憲" in december
    assert all(len(label) <= 18 for label in october + december)


def test_weekend_toggle_does_not_change_headcount(tmp_path):
    say, tap, store = _env(tmp_path)
    say("U_org", "露營開團 秋天團")
    text, cards = tap("U_a", "c=poll&k=date")
    assert "11/7(六)-11/8(日)" in _labels(cards[0])
    assert validate_message(cards[0]) == []
    data = next(a["data"] for a in _actions(cards[0]) if a.get("label") == "11/7(六)-11/8(日)")
    text, cards = tap("U_a", data)
    assert "阿明" in text and "勾選" in text and "11/7(六)-11/8(日)" in text
    _, state = store.active(G)
    assert state["candidates"] == []
    assert state["members"]["U_a"]["picks"]["date"] == ["11/7(六)-11/8(日)"]
    assert compute_stats(state)["headcount"] == 1
    text, _cards = tap("U_a", data)
    assert "取消" in text
    _, state = store.active(G)
    assert state["members"]["U_a"]["picks"]["date"] == []


def test_region_stay_kids_nights_and_stats(tmp_path):
    say, tap, store = _env(tmp_path)
    say("U_org", "露營開團")
    text, cards = tap("U_org", "c=poll&k=region")
    assert "台中～台北之間" in _labels(cards[0])
    assert {"北部", "新竹", "花蓮"} <= set(_labels(cards[0]))
    region = next(a["data"] for a in _actions(cards[0]) if a["label"] == "台中～台北之間")
    text, _cards = tap("U_org", region)
    assert "勾選" in text and "台中～台北之間" in text
    text, _cards = tap("U_a", region)
    assert "阿明" in text
    _, cards = tap("U_a", "c=poll&k=facility")
    assert "親子" in _labels(cards[0])
    kid = next(a["data"] for a in _actions(cards[0]) if a["label"] == "親子")
    tap("U_a", kid)
    _, cards = tap("U_org", "c=poll&k=stay")
    assert {"木屋", "豪華露營", "自搭帳", "都可以"} <= set(_labels(cards[0]))
    stay = next(a["data"] for a in _actions(cards[0]) if a["label"] == "木屋")
    tap("U_org", stay)
    _, cards = tap("U_b", "c=poll&k=nights")
    assert {"一泊二日", "二泊三日"} <= set(_labels(cards[0]))
    nights = next(a["data"] for a in _actions(cards[0]) if a["label"] == "一泊二日")
    tap("U_b", nights)
    say("U_org", "可以")  # 不是數字，不理
    _text, cards = tap("U_a", "c=stats")
    raw = json.dumps(cards[0].to_dict(), ensure_ascii=False)
    assert "台中～台北之間" in raw and "翔暉" in raw and "阿明" in raw
    assert "親子" in raw and "木屋" in raw and "一泊二日" in raw
    assert "⭐" in raw and "FFF4D6" in raw
    assert validate_message(cards[0]) == []
    _, state = store.active(G)
    winners = compute_stats(state)["categories"]
    assert winners["region"][4]["label"] == "台中～台北之間"
    assert winners["region"][4]["count"] == 2


def test_cabin_and_spots_use_winning_filters(tmp_path):
    say, tap, store = _env(tmp_path)
    say("U_org", "露營開團")
    say("U_org", "候選日期 11/7-11/8")
    say("U_org", "可以 1")
    say("U_a", "參加")
    say("U_org", "預算 3000")
    region = "c=pick&k=region&v=" + __import__("urllib.parse").parse.quote("台中～台北之間")
    tap("U_org", region)
    tap("U_a", "c=pick&k=facility&v=" + __import__("urllib.parse").parse.quote("親子"))
    tap("U_org", "c=pick&k=stay&v=" + __import__("urllib.parse").parse.quote("木屋"))
    typed, ctx = say("U_org", "找木屋")
    assert typed == "已整理好條件，正在幫大家找木屋，找到會貼候選上來"
    cards = cards_for_command("找木屋", ctx, typed)
    raw = json.dumps(cards[0].to_dict(), ensure_ascii=False)
    assert "蟬說：霧繞" in raw and "拉拉山達觀農場" in raw
    assert "https://www.chanshuo.tw/woorao/" in raw
    assert "https://www.dkhotel.com.tw/" in raw
    assert "觀霧" in raw and "不會代訂或付款" in raw
    assert validate_message(cards[0]) == []
    text, spot_cards = tap("U_a", "c=spots")
    spot_raw = json.dumps(spot_cards[0].to_dict(), ensure_ascii=False)
    assert "觀霧" in spot_raw and "八仙山" in spot_raw and "武陵" in spot_raw
    assert "https://www.forest.gov.tw/0000179" in spot_raw
    assert "不會代訂" in text
    assert validate_message(spot_cards[0]) == []
    _, state = store.active(G)
    data = build_request(G, state)
    assert data["best_date"] == "11/7-11/8"
    assert data["region"] == "台中～台北之間"
    assert "親子" in data["facilities"]
    assert data["accommodation"] == "木屋"
    assert data["headcount"] == 2
    assert data["budget_per_person"] == 3000
    assert any("達觀" in name for name in data["cabins"])
    assert all(url.startswith("https://") for url in (cabin["url"] for cabin in CABINS))


def test_region_outside_corridor_has_no_fake_cabins():
    cabins = match_cabins({"regions": ["花蓮"], "stay": None, "facilities": [], "budget": None, "headcount": 0})
    assert cabins == []
    kids = match_cabins({"regions": ["台中～台北之間"], "stay": "豪華露營", "facilities": ["親子"],
                         "budget": 1000, "headcount": 2})
    assert kids and all(cabin["county"] in {"新竹", "苗栗", "桃園", "台中"} for cabin in kids)
    assert all("豪華露營" in cabin["stays"] for cabin in kids)
    assert all("達觀" not in cabin["name"] for cabin in kids)


def _actions(msg):
    found = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") in ("postback", "uri", "datetimepicker", "message") and "label" in node:
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(msg.to_dict())
    return found
