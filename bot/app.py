import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, PostbackEvent, TextMessageContent

from . import line_api
from .camp.logic import Ctx, expand_command
from .camp.store import Store, ensure_schema
from . import chatlog
from .camp.ui import cards_for_command, handle_postback, quick_for_names
from .commands import dispatch
from .inbound import is_secret_request, prepare_message, redact, REFUSAL
from .llm import answer as llm_answer, probe as llm_probe

log = logging.getLogger("bot")


@asynccontextmanager
async def lifespan(_app):
    kind = ensure_schema()
    log.warning("database ready backend=%s", kind)
    yield


app = FastAPI(lifespan=lifespan)


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
    command = expand_command(command)
    one_to_one = getattr(source, "type", None) == "user"
    log.warning("inbound type=message source=%s mentioned=%s raw=%s cmd=%s",
                getattr(source, "type", ""), mentioned,
                redact(text or "")[:200], redact(command)[:200])
    if is_secret_request(text) or is_secret_request(command):
        return REFUSAL, [], None
    uid, ctx = make_ctx(source)
    out = dispatch(command, uid, ctx)
    quick = None
    cards = []
    if out is None and not (mentioned or one_to_one):
        if command:
            chatlog.add(ctx.chat_id, "user", "群友：" + redact(command)[:500])
        return None, [], None
    if out is None:
        chatlog.add(ctx.chat_id, "user", f"{ctx.name()}：{redact(command)[:500]}")
        out, names = llm_answer(ctx.chat_id, one_to_one=one_to_one and not mentioned)
        quick = quick_for_names(names)
    else:
        chatlog.add(ctx.chat_id, "user", f"{ctx.name()}：{redact(command)[:500]}")
        cards = cards_for_command(command, ctx, out)
    chatlog.add(ctx.chat_id, "assistant", redact(out)[:1000])
    return out, cards, quick


@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/health/llm")
def health_llm():
    return llm_probe()


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
        out, cards, quick = build_reply(ev.message.text, ev.source, mentionees, destination)
        if out:
            line_api.reply(ev.reply_token, out, extra=cards or None, quick=quick)
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
