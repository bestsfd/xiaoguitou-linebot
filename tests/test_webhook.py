import base64, hashlib, hmac, json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

SECRET = "dummy_secret"


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("CAMP_DB", str(tmp_path / "c.db"))
    import bot.camp.store as st
    monkeypatch.setattr(st, "DB_PATH", str(tmp_path / "c.db"))
    import bot.line_api as la
    monkeypatch.setattr(la, "display_name", lambda src, uid: "小明")
    monkeypatch.setenv("LINE_CHANNEL_SECRET", SECRET)
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "dummy_token")
    from bot.app import app
    return TestClient(app)


def payload(text, source):
    return json.dumps({"destination": "Uxxx", "events": [{
        "type": "message", "mode": "active", "timestamp": 1, "replyToken": "rtok",
        "webhookEventId": "e1", "deliveryContext": {"isRedelivery": False},
        "source": source,
        "message": {"type": "text", "id": "1", "text": text, "quoteToken": "q"}}]})


def sign(body):
    return base64.b64encode(hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest()).decode()


USER = {"type": "user", "userId": "U123"}
GROUP = {"type": "group", "groupId": "G1", "userId": "U123"}


def post(client, body, sig=None):
    return client.post("/callback", content=body,
                       headers={"X-Line-Signature": sig or sign(body), "Content-Type": "application/json"})


def test_bad_signature(client):
    assert post(client, payload("骰子", USER), sig="bad").status_code == 400


@pytest.mark.parametrize("text,src,expect", [
    ("擲骰子 3", USER, "合計"), ("抽籤", GROUP, "籤"), ("今日運勢", GROUP, "今日運勢"),
    ("哈囉", USER, "幫助"),
])
def test_replies(client, text, src, expect):
    with patch("bot.line_api.reply") as m:
        body = payload(text, src)
        assert post(client, body).status_code == 200
        token, text = m.call_args.args
        assert token == "rtok" and expect in text


def test_group_ignores_chatter(client):
    with patch("bot.line_api.reply") as m:
        assert post(client, payload("大家好", GROUP)).status_code == 200
        m.assert_not_called()


def test_camp_flow_via_webhook(client):
    with patch("bot.line_api.reply") as m:
        post(client, payload("露營開團 秋天團", GROUP))
        assert "秋天團" in m.call_args.args[1] and "小明" in m.call_args.args[1]
        card = m.call_args.kwargs["extra"][0]
        labels = _labels(card)
        assert {"選日期", "報名", "填預算", "看統計", "找木屋"} <= set(labels)
        post(client, payload("候選日期 10/31-11/1", GROUP))
        assert any(a.get("data") == "c=vote&i=1" for a in _actions(m.call_args.kwargs["extra"][0]))
        post(client, payload("可以 1", GROUP))
        assert "小明 可以" in m.call_args.args[1]
        post(client, payload("可以啊", GROUP))  # 日常用語不回
        assert m.call_count == 3


def postback_payload(data, source, params=None):
    pb = {"data": data}
    if params is not None:
        pb["params"] = params
    return json.dumps({"destination": "Uxxx", "events": [{
        "type": "postback", "mode": "active", "timestamp": 1, "replyToken": "rtok",
        "webhookEventId": "e1", "deliveryContext": {"isRedelivery": False},
        "source": source, "postback": pb}]})


def _actions(msg):
    found = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") in ("postback", "datetimepicker") and "label" in node:
                found.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(msg.to_dict())
    return found


def _labels(msg):
    return [a["label"] for a in _actions(msg)]


def test_postback_flow_via_webhook(client):
    with patch("bot.line_api.reply") as m:
        post(client, payload("露營開團 秋天團", GROUP))
        post(client, postback_payload("c=dates", GROUP))
        assert any(a["type"] == "datetimepicker" and a["mode"] == "date"
                   for a in _actions(m.call_args.kwargs["extra"][0]))
        post(client, postback_payload("c=date_start", GROUP, {"date": "2026-10-31"}))
        assert "已加入 10/31" in m.call_args.args[1]
        assert any(a.get("data") == "c=vote&i=1" for a in _actions(m.call_args.kwargs["extra"][0]))
        post(client, postback_payload("c=vote&i=1", GROUP))
        assert "小明" in m.call_args.args[1] and "勾選" in m.call_args.args[1]
        post(client, postback_payload("c=vote&i=1", GROUP))
        assert "取消" in m.call_args.args[1]
        post(client, postback_payload("c=signup", GROUP))
        assert {"參加", "參加+1", "參加+2", "不參加"} <= set(_labels(m.call_args.kwargs["extra"][0]))
        post(client, postback_payload("c=join&g=1", GROUP))
        assert "+1" in m.call_args.args[1]
        post(client, postback_payload("c=budget", GROUP))
        assert "5000 以上" in _labels(m.call_args.kwargs["extra"][0])
        post(client, postback_payload("c=bud&v=2000", GROUP))
        assert "2000" in m.call_args.args[1]
        post(client, postback_payload("c=stats", GROUP))
        stat = m.call_args.kwargs["extra"][0]
        raw = stat.to_dict()
        blob = json.dumps(raw, ensure_ascii=False)
        assert "10/31" in blob and "平均" in blob and "人數" in blob and stat.alt_text
        post(client, postback_payload("nope", GROUP))
        # 不認識的 postback 不回覆，次數停在上一則
        assert m.call_count == 10


def test_postback_resolves_group_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("CAMP_DB", str(tmp_path / "c.db"))
    monkeypatch.setenv("LINE_CHANNEL_SECRET", SECRET)
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "dummy_token")
    import bot.camp.store as st
    import bot.line_api as la
    from unittest.mock import MagicMock
    monkeypatch.setattr(st, "DB_PATH", str(tmp_path / "c.db"))
    la._cache.clear()
    from bot.app import app
    c = TestClient(app)
    org = {"type": "group", "groupId": "Gprof", "userId": "Uorganizer1"}
    voter = {"type": "group", "groupId": "Gprof", "userId": "Uvoter9999"}
    names = {"Uorganizer1": "主揪甲", "Uvoter9999": "阿華"}

    def profile(*args):
        return MagicMock(display_name=names[args[-1]])

    with patch("bot.line_api.reply") as reply, \
         patch("linebot.v3.messaging.MessagingApi.get_group_member_profile", side_effect=profile):
        assert post(c, payload("露營開團", org)).status_code == 200
        assert post(c, payload("候選日期 10/31", org)).status_code == 200
        assert post(c, postback_payload("c=vote&i=1", voter)).status_code == 200
        assert "阿華" in reply.call_args.args[1] and "勾選" in reply.call_args.args[1]


def test_postback_profile_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("CAMP_DB", str(tmp_path / "c2.db"))
    monkeypatch.setenv("LINE_CHANNEL_SECRET", SECRET)
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "dummy_token")
    import bot.camp.store as st
    import bot.line_api as la
    monkeypatch.setattr(st, "DB_PATH", str(tmp_path / "c2.db"))
    la._cache.clear()
    from bot.app import app
    c = TestClient(app)
    org = {"type": "group", "groupId": "Gfall", "userId": "Uorgfall01"}
    voter = {"type": "group", "groupId": "Gfall", "userId": "Uabcd9999"}
    with patch("bot.line_api.reply") as reply, \
         patch("linebot.v3.messaging.MessagingApi.get_group_member_profile",
               side_effect=Exception("403")):
        post(c, payload("露營開團", org))
        post(c, payload("候選日期 10/31", org))
        post(c, postback_payload("c=vote&i=1", voter))
        assert "9999" in reply.call_args.args[1]
