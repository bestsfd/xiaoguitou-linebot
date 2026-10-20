import os

from fastapi import FastAPI, HTTPException, Request
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, PostbackEvent, TextMessageContent

from . import line_api
from .camp.logic import Ctx
from .camp.store import Store
from .camp.ui import cards_for_command, handle_postback
from .commands import dispatch

HINT = "我聽不懂這句話耶 🤔 輸入「幫助」查看可用指令。"
app = FastAPI()


def get_parser():
    secret = os.environ.get("LINE_CHANNEL_SECRET")
    if not secret:
        raise HTTPException(500, "LINE_CHANNEL_SECRET not set")
    return WebhookParser(secret)


def chat_id_of(src):
    return getattr(src, "group_id", None) or getattr(src, "room_id", None) or src.user_id


def make_ctx(source):
    uid = getattr(source, "user_id", "") or ""
    ctx = Ctx(chat_id=chat_id_of(source), user_id=uid,
              name_fn=lambda u: line_api.display_name(source, u), store=Store())
    return uid, ctx


def build_reply(text, source):
    uid, ctx = make_ctx(source)
    out = dispatch(text, uid, ctx)
    if out is None and source.type == "user":
        out = HINT
    cards = cards_for_command(text, ctx, out) if out else []
    return out, cards


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode()
    try:
        events = get_parser().parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(400, "Invalid signature")
    for ev in events:
        if isinstance(ev, MessageEvent) and isinstance(ev.message, TextMessageContent):
            out, cards = build_reply(ev.message.text, ev.source)
            if out:
                line_api.reply(ev.reply_token, out, extra=cards or None)
        elif isinstance(ev, PostbackEvent):
            _uid, ctx = make_ctx(ev.source)
            params = getattr(ev.postback, "params", None) or {}
            text, cards = handle_postback(ev.postback.data, params, ctx)
            if text or cards:
                line_api.reply(ev.reply_token, text or "", extra=cards or None)
    return "OK"
