import logging
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
from .commands.help import HELP
from .inbound import is_secret_request, prepare_message, redact, REFUSAL

log = logging.getLogger("bot")

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


def build_reply(text, source, mentionees=None, destination=None):
    command, mentioned = prepare_message(text, mentionees, destination)
    log.warning("inbound type=message source=%s mentioned=%s raw=%s cmd=%s",
                getattr(source, "type", ""), mentioned,
                redact(text or "")[:200], redact(command)[:200])
    if is_secret_request(text) or is_secret_request(command):
        return REFUSAL, []
    uid, ctx = make_ctx(source)
    out = dispatch(command, uid, ctx)
    if out is None and mentioned:
        out = HELP
    elif out is None and getattr(source, "type", None) == "user":
        out = HINT
    cards = cards_for_command(command, ctx, out) if out else []
    return out, cards


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode()
    try:
        parsed = get_parser().parse(body, signature, as_payload=True)
    except InvalidSignatureError:
        raise HTTPException(400, "Invalid signature")
    destination = getattr(parsed, "destination", None)
    for ev in parsed.events:
        try:
            _handle_event(ev, destination)
        except Exception as exc:
            log.warning("event failed type=%s err=%s", getattr(ev, "type", "?"),
                        redact(line_api._describe(exc))[:400])
    return "OK"


def _handle_event(ev, destination):
    if isinstance(ev, MessageEvent) and isinstance(ev.message, TextMessageContent):
        mention = getattr(ev.message, "mention", None)
        mentionees = list(getattr(mention, "mentionees", None) or [])
        out, cards = build_reply(ev.message.text, ev.source, mentionees, destination)
        if out:
            line_api.reply(ev.reply_token, out, extra=cards or None)
        return
    if isinstance(ev, PostbackEvent):
        data = ev.postback.data
        log.warning("inbound type=postback source=%s data=%s",
                    getattr(ev.source, "type", ""), redact(data)[:200])
        _uid, ctx = make_ctx(ev.source)
        params = getattr(ev.postback, "params", None) or {}
        text, cards = handle_postback(data, params, ctx)
        if text or cards:
            line_api.reply(ev.reply_token, text or "", extra=cards or None)
        return
    log.warning("inbound type=%s source=%s", getattr(ev, "type", "?"),
                getattr(getattr(ev, "source", None), "type", ""))
