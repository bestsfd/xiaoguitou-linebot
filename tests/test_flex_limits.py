import logging
from unittest.mock import patch

from linebot.v3.messaging.exceptions import ApiException

from bot.camp.flexcheck import validate_message, validate_reply
from bot.camp.store import new_state
from bot.camp.ui import (budget_card, date_end_card, date_start_card, menu_card,
                         signup_card, stats_card, vote_card)


def _state():
    st = new_state("秋天團", "U_org", "翔暉")
    st["candidates"] = ["10/31-11/1", "11/7-11/8"]
    st["members"] = {
        "U_org": {"name": "翔暉", "attending": True, "guests": 0, "budget": 3000, "votes": [1, 2]},
        "U_a": {"name": "阿明", "attending": True, "guests": 1, "budget": 2500, "votes": [2]},
    }
    return st


def test_generated_cards_meet_line_limits():
    st = _state()
    cards = [
        menu_card(st), date_start_card(st), date_end_card(st, "2026-10-31", "10/31"),
        vote_card(st, "U_org", extend_iso="2026-10-31"),
        signup_card(st), budget_card(st), stats_card(st),
    ]
    many = _state()
    many["candidates"] = [f"1/{day}" for day in range(1, 16)]
    cards.append(vote_card(many, "U_org"))
    for card in cards:
        errors = validate_message(card)
        assert errors == [], errors
        bundle = [{"type": "text", "text": "🏕️ 開團了"}, card.to_dict()]
        assert validate_reply(bundle) == []
        raw = card.to_dict()
        assert len(raw["quickReply"]["items"]) <= 13
        assert len(raw["altText"]) <= 400


def test_validator_flags_label_quick_reply_and_message_count():
    msg = {
        "type": "flex",
        "altText": "x",
        "contents": {"type": "bubble", "body": {
            "type": "box", "layout": "vertical",
            "contents": [{"type": "button", "action": {
                "type": "postback", "label": "標" * 21, "data": "c=1",
            }}],
        }},
        "quickReply": {"items": [
            {"action": {"type": "postback", "label": str(i), "data": "c=1"}}
            for i in range(14)
        ]},
    }
    errors = validate_message(msg)
    assert any("label" in err for err in errors)
    assert any("quickReply" in err for err in errors)
    assert validate_reply([{"type": "text", "text": "a"}] * 6)


class _BadFlex:
    type = "flex"
    alt_text = "壞掉的卡片"

    def to_dict(self):
        return {"type": "flex", "altText": "壞掉的卡片", "contents": {"type": "bubble", "body": {
            "type": "box", "layout": "vertical",
            "contents": [{"type": "button", "action": {
                "type": "postback", "label": "標" * 21, "data": "c=x",
            }}],
        }}}


def test_invalid_flex_is_not_sent(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "tok")
    from bot import line_api
    with patch("linebot.v3.messaging.MessagingApi.reply_message") as rm:
        line_api.reply("rtok", "還在", extra=[_BadFlex()])
    req = rm.call_args.args[0]
    assert len(req.messages) == 1 and req.messages[0].text == "還在"


def test_line_rejects_flex_then_text_fallback(monkeypatch, caplog):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "CANARY-ACCESS-TOKEN")
    from bot import line_api
    card = menu_card({"name": "秋天團", "organizer_name": "翔暉"})
    calls = []

    def side(req):
        calls.append(req)
        if any(getattr(m, "type", None) == "flex" for m in req.messages):
            err = ApiException(status=400, reason="Bad Request")
            err.body = "invalid flex CANARY-ACCESS-TOKEN"
            raise err

    with caplog.at_level(logging.WARNING, logger="bot"):
        with patch("linebot.v3.messaging.MessagingApi.reply_message", side_effect=side):
            line_api.reply("rtok", "🏕️開團了", extra=[card])
    assert len(calls) == 2
    assert calls[1].messages[0].type == "text" and "開團了" in calls[1].messages[0].text
    assert "CANARY-ACCESS-TOKEN" not in caplog.text
    assert "LINE reply_message failed" in caplog.text
