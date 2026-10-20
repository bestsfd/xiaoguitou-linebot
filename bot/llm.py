"""群組裡 @機器人，或一對一的自由提問。已知指令不走這裡。"""
import json
import os
import re

import httpx

from .camp.catalog import CATEGORIES, tops
from .camp.logic import compute_stats
from .camp.places import brief
from .camp.store import Store
from .chatlog import recent
from .commands.help import HELP
from .inbound import redact

HINT = "我聽不懂這句話耶 🤔 輸入「幫助」查看可用指令。"
DEFAULT_BUTTONS = ("日期投票", "地點投票", "找木屋", "找景點", "看統計")
BUTTONS = (
    "日期投票", "選日期", "地點投票", "住宿類型", "需求/設施", "天數",
    "報名", "填預算", "看統計", "找木屋", "找景點", "幫助",
)


def _api_key():
    return (os.environ.get("OPENAI_API_KEY") or "").strip()


def enabled():
    return bool(_api_key())


def _short_error(exc, key):
    response = getattr(exc, "response", None)
    if response is not None:
        snippet = ""
        try:
            snippet = response.text or ""
        except Exception:
            snippet = ""
        text = f"status={getattr(response, 'status_code', '')} {snippet}"
    else:
        text = str(exc)
    text = redact(text)
    if key:
        text = text.replace(key, "[redacted]")
    text = " ".join(text.split())[:120]
    return text or "llm call failed"


def probe():
    """打一則 1-token 完成，確認金鑰是否可用。不回傳金鑰本身。"""
    key = _api_key()
    report = {
        "key_present": bool(key),
        "key_length": len(key),
        "key_prefix_ok": key.startswith("sk-"),
        "call_ok": False,
        "error": None,
    }
    if not key:
        report["error"] = "missing OPENAI_API_KEY"
        return report
    base = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = (os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini"
    try:
        with httpx.Client(timeout=httpx.Timeout(20.0)) as client:
            response = client.post(
                base + "/chat/completions",
                headers={"Authorization": "Bearer " + key},
                json={
                    "model": model,
                    "max_tokens": 1,
                    "temperature": 0,
                    "messages": [{"role": "user", "content": "ping"}],
                },
            )
            response.raise_for_status()
    except Exception as exc:
        report["error"] = _short_error(exc, key)
        return report
    report["call_ok"] = True
    return report


def poll_snapshot(chat_id):
    _pid, state = Store().active(chat_id)
    if not state:
        return "目前沒有進行中的露營團。"
    stats = compute_stats(state)
    lines = [f"團名：{state.get('name') or '露營團'}，主揪：{state.get('organizer_name') or '未定'}，"
             f"人數 {stats['headcount']}（含攜伴）"]
    categories = stats.get("categories") or {}
    for key, title in CATEGORIES:
        rows = categories.get(key) or []
        voted = [row for row in rows if row["count"]]
        if not voted:
            lines.append(f"{title}：尚無")
            continue
        best = {row["label"] for row in tops(rows)}
        bits = []
        for row in voted:
            mark = "★" if row["label"] in best else ""
            who = "、".join(row["names"])
            bits.append(f"{mark}{row['label']} {row['count']}票（{who}）")
        lines.append(f"{title}：" + "；".join(bits))
    if stats["budget"]:
        budget = stats["budget"]
        lines.append(f"預算最低 {budget['min']}、中位 {budget['median']:g}、最高 {budget['max']}")
    else:
        lines.append("預算：尚無")
    if state.get("area"):
        lines.append(f"打字設定的地區：{state['area']}")
    return "\n".join(lines)


def system_prompt(chat_id):
    return (
        "你是小龜頭，光明兄弟會的露營揪團小幫手。只用繁體中文，語氣像群裡的朋友，回覆短、口語。"
        "你不會代訂、不會付款、不收信用卡。別人問密碼、金鑰、權杖、環境變數，就說你不能提供。"
        "只能根據下面的開團狀態，以及整理好的木屋與景點來建議。沒有列出來的店名、價格、網址不要編。"
        "建議去處時提醒：連結給大家自己看，你不會代訂或付款。"
        "回覆必須是 JSON，不要加其他文字："
        '{"text":"給群友看的話","buttons":["日期投票","找木屋"]}。'
        "buttons 最多 5 個，名稱只能從：" + "、".join(BUTTONS) + "。\n\n"
        "目前開團狀態：\n" + poll_snapshot(chat_id) + "\n\n"
        "整理好的木屋與景點：\n" + brief()
    )


def _parse(content):
    text = (content or "").strip()
    fenced = re.sub(r"^```(?:json)?\s*", "", text)
    fenced = re.sub(r"\s*```$", "", fenced).strip()
    try:
        data = json.loads(fenced)
    except json.JSONDecodeError:
        return text, list(DEFAULT_BUTTONS)
    if not isinstance(data, dict):
        return text, list(DEFAULT_BUTTONS)
    reply = str(data.get("text") or "").strip()
    buttons = data.get("buttons") if isinstance(data.get("buttons"), list) else []
    names = [str(item).strip() for item in buttons if str(item).strip() in BUTTONS]
    return (reply or text), (names or list(DEFAULT_BUTTONS))[:5]


def complete(chat_id):
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    base = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = (os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini"
    messages = [{"role": "system", "content": system_prompt(chat_id)}]
    messages.extend(recent(chat_id))
    with httpx.Client(timeout=httpx.Timeout(20.0)) as client:
        response = client.post(
            base + "/chat/completions",
            headers={"Authorization": "Bearer " + key},
            json={"model": model, "temperature": 0.4, "messages": messages},
        )
        response.raise_for_status()
        payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    return _parse(content)


def answer(chat_id, *, one_to_one):
    """回傳 (文字, 按鈕名稱清單)。沒有金鑰或呼叫失敗時用原本的說明。"""
    fallback = HINT if one_to_one else HELP
    if not enabled():
        return fallback, []
    try:
        text, buttons = complete(chat_id)
    except Exception as exc:
        import logging
        logging.getLogger("bot").warning("llm failed: %s", redact(str(exc))[:300])
        return fallback, []
    text = redact(text).strip()
    if not text:
        return fallback, []
    return text[:1000], buttons
