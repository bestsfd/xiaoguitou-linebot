"""Postgres／SQLite 選擇，以及群友直接打的日期、預算。"""
import os

import pytest

from bot.camp.logic import expand_command
from bot.camp.store import Store, backend, new_state
from bot.commands import dispatch
from bot.inbound import redact

LABELS = [
    "11/7(六)-11/8(日)",
    "11/21(六)-11/22(日)",
    "10/9(五)-10/11(日)國慶",
]
NAMES = {"U_org": "翔暉", "U_a": "阿明", "U_b": "小美"}
G = "Gpersist"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr("bot.camp.logic.next_month_labels", lambda today=None: list(LABELS))
    monkeypatch.setattr("bot.camp.catalog.next_month_labels", lambda today=None: list(LABELS))
    monkeypatch.setattr("bot.camp.ui.next_month_labels", lambda today=None: list(LABELS))
    store = Store(str(tmp_path / "camp.db"))

    def say(uid, text):
        from bot.camp.logic import Ctx
        ctx = Ctx(chat_id=G, user_id=uid, name_fn=lambda u: NAMES.get(u, u), store=store)
        return dispatch(text, uid, ctx), ctx
    return say, store


def test_backend_choice(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CAMP_DB", raising=False)
    assert backend() == "sqlite"
    monkeypatch.setenv("DATABASE_URL", "postgres://bot:secret@localhost/camp")
    assert backend() == "postgres"
    monkeypatch.setenv("CAMP_DB", "/tmp/camp.db")
    assert backend() == "sqlite"
    assert backend("/tmp/other.db") == "sqlite"


def test_path_and_camp_db_ignore_database_url(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "postgres://nope:nope@127.0.0.1:1/none")
    path = str(tmp_path / "camp.db")
    store = Store(path)
    pid = store.create("G1", new_state("秋天團", "U", "甲"))
    assert Store(path).active("G1") == (pid, store.active("G1")[1])
    monkeypatch.setenv("CAMP_DB", str(tmp_path / "forced.db"))
    other = Store()
    pid2 = other.create("G2", new_state("春天團", "U", "乙"))
    assert Store().active("G2")[0] == pid2
    assert Store().active("G2")[1]["name"] == "春天團"


def test_sqlite_survives_new_store(tmp_path):
    path = str(tmp_path / "camp.db")
    store = Store(path)
    state = new_state("秋天團", "U1", "翔暉")
    pid = store.create("G", state)
    state["members"]["U1"] = {"name": "翔暉", "attending": True, "guests": 0, "budget": 3000, "votes": []}
    state["area"] = "台中"
    store.save(pid, state)
    got_id, got = Store(path).active("G")
    assert got_id == pid
    assert got["name"] == "秋天團" and got["area"] == "台中"
    assert got["members"]["U1"]["budget"] == 3000


def test_expand_budget_and_stats():
    assert expand_command("預算3000") == "預算 3000"
    assert expand_command("預算 3,000元") == "預算 3000"
    assert expand_command("預算：3000") == "預算 3000"
    assert expand_command("看統計") == "統計"
    assert expand_command("參加+2") == "參加 +2"
    assert expand_command("大家好") == "大家好"
    assert expand_command("11/21去露營") == "11/21去露營"


def test_typed_weekend_and_short_date(env):
    say, store = env
    say("U_org", "露營開團 秋天團")
    text, _ctx = say("U_a", "11/21(六)-11/22(日)")
    assert "阿明" in text and "勾選" in text and "11/21(六)-11/22(日)" in text
    _pid, state = store.active(G)
    assert state["members"]["U_a"]["picks"]["date"] == ["11/21(六)-11/22(日)"]
    assert state["candidates"] == []
    assert state["members"]["U_a"].get("attending") in (None, False)
    text, _ctx = say("U_a", "11/21")
    assert "取消" in text and "11/21(六)-11/22(日)" in text
    text, _ctx = say("U_b", "11／21".replace("／", "/"))
    assert "小美" in text and "勾選" in text
    text, _ctx = say("U_a", "10/10")
    assert "勾選" in text and "國慶" in text
    text, _ctx = say("U_a", "12/1")
    assert "勾選" in text and "12/1" in text
    _pid, state = store.active(G)
    assert "12/1" in state["candidates"]
    assert state["members"]["U_a"]["attending"] is True


def test_several_dates_and_ambiguous_and_chatter(env, monkeypatch):
    say, store = env
    say("U_org", "露營開團")
    text, _ctx = say("U_a", "11/7(六)-11/8(日)、11/21")
    assert "都幫你勾上啦" in text and "勾選" in text
    _pid, state = store.active(G)
    assert set(state["members"]["U_a"]["picks"]["date"]) == {"11/7(六)-11/8(日)", "11/21(六)-11/22(日)"}
    monkeypatch.setattr("bot.camp.logic.next_month_labels", lambda today=None: [
        "11/20(五)-11/22(日)", "11/21(六)-11/23(一)",
    ])
    before = store.active(G)[1]["members"]["U_a"]["picks"]["date"]
    text, _ctx = say("U_b", "11/21")
    assert "好幾個" in text
    assert store.active(G)[1]["members"]["U_a"]["picks"]["date"] == before
    assert "U_b" not in store.active(G)[1]["members"]
    assert say("U_a", "好廢")[0] is None
    assert say("U_a", "11/21去露營")[0] is None
    assert say("U_a", "可以啊")[0] is None
    say("U_a", "參加")
    text, _ctx = say("U_a", "預算3000")
    assert "3000" in text and "阿明" in text
    assert store.active(G)[1]["members"]["U_a"]["budget"] == 3000
    text, _ctx = say("U_a", "看統計")
    assert text.startswith("📊") and "3000" in text


def test_redact_database_url(monkeypatch):
    url = "postgres://bot:supersecret@dpg-host/camp"
    monkeypatch.setenv("DATABASE_URL", url)
    assert "supersecret" not in redact("failed " + url)
    assert "supersecret" not in redact("postgres://bot:supersecret@other-host/db")


def test_postgres_roundtrip():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    import psycopg
    from bot.camp import store as store_mod
    with psycopg.connect(store_mod._pg_dsn(url), connect_timeout=10) as raw:
        raw.execute("DROP TABLE IF EXISTS chat_log")
        raw.execute("DROP TABLE IF EXISTS plans")
        raw.commit()
    monkey = pytest.MonkeyPatch()
    monkey.setenv("DATABASE_URL", url)
    monkey.delenv("CAMP_DB", raising=False)
    try:
        assert backend() == "postgres"
        store_mod.ensure_schema()
        store = Store()
        pid = store.create("Gpg", new_state("秋天團", "U1", "翔暉"))
        _pid, state = store.active("Gpg")
        state["area"] = "新竹"
        store.save(pid, state)
        again = Store()
        got_id, got = again.active("Gpg")
        assert got_id == pid and got["area"] == "新竹" and got["name"] == "秋天團"
        again.close(pid)
        assert again.active("Gpg") == (None, None)
        from bot.chatlog import add, recent
        add("Gpg", "user", "第1句")
        assert recent("Gpg")[-1]["content"] == "第1句"
    finally:
        monkey.undo()
