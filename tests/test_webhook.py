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
        post(client, payload("候選日期 10/31-11/1", GROUP))
        post(client, payload("可以 1", GROUP))
        assert "小明 可以" in m.call_args.args[1]
        post(client, payload("可以啊", GROUP))  # 日常用語不回
        assert m.call_count == 3
