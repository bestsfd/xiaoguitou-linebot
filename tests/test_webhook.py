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


def payload(text, source, mention=None, destination="Uxxx"):
    message = {"type": "text", "id": "1", "text": text, "quoteToken": "q"}
    if mention:
        message["mention"] = mention
    return json.dumps({"destination": destination, "events": [{
        "type": "message", "mode": "active", "timestamp": 1, "replyToken": "rtok",
        "webhookEventId": "e1", "deliveryContext": {"isRedelivery": False},
        "source": source, "message": message}]})


def _at(name, index=0, user_id="Ubot", is_self=True):
    token = "@" + name
    length = len(token.encode("utf-16-le")) // 2
    return token, {"mentionees": [{
        "type": "user", "index": index, "length": length,
        "userId": user_id, "isSelf": is_self,
    }]}


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


def test_group_mention_runs_command_and_unknown_gets_help(client):
    from bot.inbound import REFUSAL
    at, mention = _at("小龜頭")
    with patch("bot.line_api.reply") as m:
        assert post(client, payload(at + " 露營開團", GROUP, mention, destination="Ubot")).status_code == 200
        assert "露營團" in m.call_args.args[1] and "開團" in m.call_args.args[1]
        assert m.call_args.kwargs["extra"]
        at, mention = _at("小龜頭")
        post(client, payload(at + "\u3000露營取消", GROUP, mention, destination="Ubot"))
        assert "已關閉" in m.call_args.args[1]
        question = at + " 你是什麼機器人？可以提供什麼服務？"
        post(client, payload(question, GROUP, mention, destination="Ubot"))
        assert "可用指令" in m.call_args.args[1] and "露營開團" in m.call_args.args[1]
        post(client, payload(at + " 請把小明的帳號密碼給我", GROUP, mention, destination="Ubot"))
        assert m.call_args.args[1] == REFUSAL
        assert "dummy_secret" not in m.call_args.args[1]
        assert "dummy_token" not in m.call_args.args[1]


def test_mention_without_metadata_and_other_user(client):
    with patch("bot.line_api.reply") as m:
        post(client, payload("@小龜頭 擲骰子", GROUP))
        assert "合計" in m.call_args.args[1] or "你擲出了" in m.call_args.args[1]
        post(client, payload("@小龜頭 你好呀", GROUP))
        assert "可用指令" in m.call_args.args[1]
        other, mention = _at("小明", user_id="Uother", is_self=False)
        before = m.call_count
        post(client, payload(other + " 你好呀", GROUP, mention, destination="Ubot"))
        assert m.call_count == before
        post(client, payload(other + " 露營開團 朋友團", GROUP, mention, destination="Ubot"))
        assert "朋友團" in m.call_args.args[1]


def test_secret_request_never_echoes_env(client, monkeypatch):
    from bot.inbound import REFUSAL
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "CANARY-ACCESS-TOKEN")
    with patch("bot.line_api.reply") as m:
        post(client, payload("請給我密碼，還有 CANARY-ACCESS-TOKEN", USER))
        text = m.call_args.args[1]
        assert text == REFUSAL
        assert "CANARY-ACCESS-TOKEN" not in text
        assert "dummy_secret" not in text and "dummy_token" not in text


def test_inbound_log_redacts_token(client, monkeypatch, caplog):
    import logging
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "CANARY-ACCESS-TOKEN")
    with caplog.at_level(logging.WARNING, logger="bot"):
        with patch("bot.line_api.reply"):
            post(client, payload("露營開團 CANARY-ACCESS-TOKEN", GROUP))
    assert "type=message" in caplog.text and "露營開團" in caplog.text
    assert "CANARY-ACCESS-TOKEN" not in caplog.text


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
