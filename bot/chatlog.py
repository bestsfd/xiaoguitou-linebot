"""每個聊天室保留最近幾則對話，供自由問答當上下文。跟露營計畫同一個資料庫。"""
from .camp.store import connect

KEEP = 10


def _db():
    return connect()


def add(chat_id, role, content):
    text = (content or "").strip()
    if not chat_id or not text:
        return
    with _db() as conn:
        conn.execute("INSERT INTO chat_log(chat_id, role, content) VALUES(?,?,?)",
                     (chat_id, role, text[:1000]))
        conn.execute(
            """DELETE FROM chat_log WHERE chat_id=? AND id NOT IN (
                   SELECT id FROM chat_log WHERE chat_id=? ORDER BY id DESC LIMIT ?)""",
            (chat_id, chat_id, KEEP),
        )


def recent(chat_id, limit=KEEP):
    with _db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM chat_log WHERE chat_id=? ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
    rows.reverse()
    return [{"role": role, "content": content} for role, content in rows]
