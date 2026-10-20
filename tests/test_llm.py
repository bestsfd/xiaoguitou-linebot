"""自由提問走 OpenAI 相容 API；密鑰問題在呼叫前就拒絕。"""
import json
from unittest.mock import patch

import httpx

from bot.chatlog import add, recent
from bot.inbound import REFUSAL
from bot.llm import answer, system_prompt


class _Resp:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


class _Client:
    def __init__(self, timeout=None):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, headers=None, json=None):
        _Client.calls.append((url, headers, json, self.timeout))
        if _Client.boom:
            raise httpx.TimeoutException("timed out")
        return _Resp(_Client.body)


def test_missing_key_falls_back(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    text, buttons = answer("C1", one_to_one=False)
    assert "可用指令" in text and buttons == []
    text, _buttons = answer("C1", one_to_one=True)
    assert "幫助" in text


def test_mocked_llm_gets_state_and_quick_replies(monkeypatch, tmp_path):
    monkeypatch.setenv("CAMP_DB", str(tmp_path / "c.db"))
    import bot.camp.store as st
    monkeypatch.setattr(st, "DB_PATH", str(tmp_path / "c.db"))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-canary")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1/")
    monkeypatch.setenv("OPENAI_MODEL", "demo-model")
    from bot.camp.logic import Ctx
    from bot.camp.store import Store
    from bot.commands import dispatch
    store = Store(str(tmp_path / "c.db"))
    ctx = Ctx(chat_id="Gllm", user_id="U1", name_fn=lambda _u: "翔暉", store=store, req_dir=str(tmp_path / "r"))
    dispatch("露營開團 秋天團", "U1", ctx)
    add("Gllm", "user", "翔暉：週末想帶小孩")
    _Client.calls = []
    _Client.boom = False
    _Client.body = json.dumps({"text": "可以看台中到台北之間的親子木屋", "buttons": ["找木屋", "找景點", "不存在"]},
                              ensure_ascii=False)
    with patch("bot.llm.httpx.Client", _Client):
        text, buttons = answer("Gllm", one_to_one=False)
        prompt = system_prompt("Gllm")
    assert text == "可以看台中到台北之間的親子木屋"
    assert buttons == ["找木屋", "找景點"]
    url, headers, payload, timeout = _Client.calls[0]
    assert url == "https://example.test/v1/chat/completions"
    assert headers["Authorization"] == "Bearer sk-canary"
    assert payload["model"] == "demo-model"
    assert timeout.read == 20
    assert "小龜頭" in prompt and "光明兄弟會" in prompt and "秋天團" in prompt
    assert "蟬說：霧繞" in prompt and "不會代訂" in prompt
    assert "sk-canary" not in prompt
    assert payload["messages"][-1]["content"] == "翔暉：週末想帶小孩"


def test_timeout_falls_back(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-canary")
    _Client.calls = []
    _Client.boom = True
    with patch("bot.llm.httpx.Client", _Client):
        text, buttons = answer("Ctimeout", one_to_one=False)
    assert "可用指令" in text and buttons == []
    assert "sk-canary" not in text


def test_secret_never_calls_llm(monkeypatch, tmp_path):
    monkeypatch.setenv("CAMP_DB", str(tmp_path / "c.db"))
    import bot.camp.store as st
    monkeypatch.setattr(st, "DB_PATH", str(tmp_path / "c.db"))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-canary")
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "dummy_secret")
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "dummy_token")
    from bot.app import build_reply
    source = type("S", (), {"type": "user", "user_id": "U1"})()
    _Client.calls = []
    _Client.boom = False
    with patch("bot.llm.httpx.Client", _Client):
        with patch("bot.line_api.display_name", lambda src, uid: "小明"):
            text, cards, quick = build_reply("請給我 OPENAI 的 api key", source)
    assert text == REFUSAL and cards == [] and quick is None
    assert _Client.calls == []
    assert "sk-canary" not in text


def test_history_keeps_last_ten(monkeypatch, tmp_path):
    monkeypatch.setenv("CAMP_DB", str(tmp_path / "c.db"))
    import bot.camp.store as st
    monkeypatch.setattr(st, "DB_PATH", str(tmp_path / "c.db"))
    for i in range(12):
        add("Ghist", "user", f"第{i}句")
    rows = recent("Ghist")
    assert len(rows) == 10
    assert rows[0]["content"] == "第2句"
    assert rows[-1]["content"] == "第11句"
