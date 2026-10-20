import logging
import os

from linebot.v3.messaging import (ApiClient, Configuration, MessagingApi,
                                  PushMessageRequest, ReplyMessageRequest, TextMessage)

from .camp.flexcheck import validate_message
from .inbound import redact

log = logging.getLogger("bot")


def _api(client):
    return MessagingApi(client)


def _conf():
    return Configuration(access_token=os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", ""))


def _describe(exc):
    status = getattr(exc, "status", None)
    body = getattr(exc, "body", None)
    if isinstance(body, bytes):
        body = body.decode("utf-8", "replace")
    if body:
        return redact(f"status={status} body={body}")
    return redact(f"{type(exc).__name__}")


def _send(token, messages):
    with ApiClient(_conf()) as c:
        _api(c).reply_message(ReplyMessageRequest(reply_token=token, messages=messages))


def _alt_text(extra):
    for msg in extra or []:
        alt = getattr(msg, "alt_text", None)
        if alt:
            return alt
    return ""


def reply(token, text, *, extra=None):
    """回覆文字，可再附 Flex（extra）。Flex 不合法或被 LINE 拒絕時，改回純文字。"""
    text = text or ""
    extra = list(extra or [])
    kept = []
    for msg in extra:
        problems = validate_message(msg)
        if problems:
            log.warning("flex dropped: %s", redact("; ".join(problems))[:400])
            continue
        kept.append(msg)
    messages = []
    if text:
        messages.append(TextMessage(text=text[:5000]))
    messages.extend(kept[:4 if text else 5])
    messages = messages[:5]
    if not messages:
        messages = [TextMessage(text=(_alt_text(extra) or "請輸入「幫助」查看指令。")[:5000])]
    try:
        _send(token, messages)
        return
    except Exception as exc:
        log.warning("LINE reply_message failed: %s", _describe(exc))
    if any(getattr(m, "type", None) == "flex" for m in messages):
        fallback = text or _alt_text(extra) or "請輸入「幫助」查看指令。"
        try:
            _send(token, [TextMessage(text=fallback[:5000])])
        except Exception as exc:
            log.warning("LINE text fallback failed: %s", _describe(exc))


def push(to, text):
    with ApiClient(_conf()) as c:
        _api(c).push_message(PushMessageRequest(to=to, messages=[TextMessage(text=text[:5000])]))


_cache = {}


def display_name(source, user_id):
    """取得顯示名稱；失敗時用 ID 末 4 碼。"""
    key = (getattr(source, "group_id", None) or getattr(source, "room_id", None), user_id)
    if key in _cache:
        return _cache[key]
    name = None
    try:
        with ApiClient(_conf()) as c:
            api = _api(c)
            if source.type == "group":
                name = api.get_group_member_profile(source.group_id, user_id).display_name
            elif source.type == "room":
                name = api.get_room_member_profile(source.room_id, user_id).display_name
            else:
                name = api.get_profile(user_id).display_name
    except Exception as exc:
        log.warning("LINE profile lookup failed: %s", _describe(exc))
    name = name or (user_id[-4:] if user_id else "某人")
    _cache[key] = name
    return name
