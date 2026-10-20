"""SQLite 持久化：每個聊天室（群組/多人聊天/1:1）一份 plan，state 以 JSON 存。"""
import json
import os
import sqlite3
import time

BASE = os.path.join(os.path.dirname(__file__), "..", "..", "data")
DB_PATH = os.environ.get("CAMP_DB", os.path.abspath(os.path.join(BASE, "camp.db")))


def connect(path=None):
    path = path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    c = sqlite3.connect(path)
    c.execute("""CREATE TABLE IF NOT EXISTS plans(
        id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT NOT NULL,
        status TEXT NOT NULL, state TEXT NOT NULL, created REAL, updated REAL)""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_chat ON plans(chat_id, status)")
    return c


def new_state(name, organizer_id, organizer_name):
    return {"name": name, "organizer": organizer_id, "organizer_name": organizer_name,
            "candidates": [], "members": {}, "wishes": [], "area": "",
            "phase": "planning", "options": [], "option_votes": {}, "chosen": None}


class Store:
    def __init__(self, path=None):
        self.path = path

    def _c(self):
        return connect(self.path)

    def active(self, chat_id):
        with self._c() as c:
            r = c.execute("SELECT id, state FROM plans WHERE chat_id=? AND status='active' "
                          "ORDER BY id DESC LIMIT 1", (chat_id,)).fetchone()
        return (r[0], json.loads(r[1])) if r else (None, None)

    def create(self, chat_id, state):
        now = time.time()
        with self._c() as c:
            cur = c.execute("INSERT INTO plans(chat_id,status,state,created,updated) VALUES(?,?,?,?,?)",
                            (chat_id, "active", json.dumps(state, ensure_ascii=False), now, now))
            return cur.lastrowid

    def save(self, plan_id, state):
        with self._c() as c:
            c.execute("UPDATE plans SET state=?, updated=? WHERE id=?",
                      (json.dumps(state, ensure_ascii=False), time.time(), plan_id))

    def close(self, plan_id, status="closed"):
        with self._c() as c:
            c.execute("UPDATE plans SET status=?, updated=? WHERE id=?", (status, time.time(), plan_id))
