"""露營流程的 Flex 卡片、快速回覆與 postback。使用者看到的文字都是繁體中文。"""
import statistics
from urllib.parse import parse_qs

from linebot.v3.messaging import (DatetimePickerAction, FlexBox, FlexBubble, FlexButton,
                                  FlexMessage, FlexSeparator, FlexText, PostbackAction,
                                  QuickReply, QuickReplyItem)

from .logic import (NO_PLAN, add_candidate, cmd_join, cmd_leave, cmd_search, compute_stats,
                    iso_to_label, set_budget_amount, toggle_vote)

GREEN = "#1F6B4A"
AMBER = "#E65100"
BEST_BG = "#FFF4D6"
MUTED = "#666666"
NO_BOOK = "機器人不會代訂或付款"

# (按鈕文字, postback data)
MENU = (
    ("選日期", "c=dates"),
    ("報名", "c=signup"),
    ("填預算", "c=budget"),
    ("看統計", "c=stats"),
    ("找木屋", "c=search"),
)
BUDGETS = (
    (1000, False, "1000"),
    (2000, False, "2000"),
    (3000, False, "3000"),
    (5000, True, "5000 以上"),
)


def _clip(text, n=20):
    text = "" if text is None else str(text)
    return text if len(text) <= n else text[: n - 1] + "…"


def _post(label, data, display=None):
    shown = display or label
    return PostbackAction(label=_clip(label), data=data, display_text=_clip(shown, 300))


def _btn(label, data, *, style="primary", color=None, display=None):
    return FlexButton(style=style, height="sm", margin="sm", color=color,
                      action=_post(label, data, display))


def _qr(actions):
    items = [QuickReplyItem(action=a) for a in actions[:13]]
    return QuickReply(items=items) if items else None


def menu_actions():
    return [_post(label, data) for label, data in MENU]


def _bubble(header, body_contents, *, alt, quick=None, header_color=GREEN):
    bubble = FlexBubble(
        size="mega",
        header=FlexBox(
            layout="vertical", background_color=header_color, padding_all="16px",
            contents=[FlexText(text=header, weight="bold", size="lg", color="#FFFFFF", wrap=True)],
        ),
        body=FlexBox(layout="vertical", spacing="sm", padding_all="16px", contents=body_contents),
    )
    return FlexMessage(alt_text=_clip(alt, 400), contents=bubble, quick_reply=quick or _qr(menu_actions()))


def menu_card(state):
    body = [
        FlexText(text=f"主揪 {state.get('organizer_name') or '未定'}", size="sm", color=MUTED, wrap=True),
        FlexText(text=f"點按鈕即可，不用打字。{NO_BOOK}。", size="sm", color=MUTED, wrap=True, margin="sm"),
    ]
    colors = {"選日期": GREEN, "報名": "#2E7D32", "找木屋": "#455A64"}
    for label, data in MENU:
        body.append(_btn(label, data, color=colors.get(label, GREEN)))
    return _bubble(f"🏕️ {state.get('name') or '露營團'}", body, alt=f"露營選單：{state.get('name') or '露營團'}")


def date_start_card(state):
    picker = DatetimePickerAction(label="選開始日", data="c=date_start", mode="date")
    body = [
        FlexText(text="點「選開始日」就會加入候選。若是連續幾天，加入後再選結束日。", wrap=True, size="sm", color=MUTED),
        FlexText(text="也可以直接打「候選日期 10/31-11/1, 11/7-11/8」。", wrap=True, size="sm", color=MUTED, margin="sm"),
        FlexButton(style="primary", height="sm", margin="md", color=GREEN, action=picker),
    ]
    if state.get("candidates"):
        body.append(_btn("看目前日期並投票", "c=votes", style="secondary"))
    quick = _qr([picker] + menu_actions())
    return _bubble("📅 選候選日期", body, alt="請選擇露營開始日", quick=quick)


def date_end_card(state, start_iso, start_label):
    data = f"c=date_end&s={start_iso}"
    picker = DatetimePickerAction(label="選結束日", data=data, mode="date", initial=start_iso, min=start_iso)
    already = len(state.get("candidates") or [])
    hint = f"開始日 {start_label}。選結束日，或按「就這一天」。"
    if already:
        hint += f"目前已有 {already} 個候選。"
    body = [
        FlexText(text=hint, wrap=True, size="sm", color=MUTED),
        FlexButton(style="primary", height="sm", margin="md", color=GREEN, action=picker),
        _btn("就這一天", f"c=date_one&s={start_iso}", style="secondary"),
    ]
    quick = _qr([picker, _post("就這一天", f"c=date_one&s={start_iso}")] + menu_actions())
    return _bubble("📅 選結束日", body, alt=f"開始日 {start_label}，請選結束日或就這一天", quick=quick)


def _vote_bits(state, user_id):
    member = (state.get("members") or {}).get(user_id) or {}
    votes = set(member.get("votes") or [])
    per = {p["idx"]: p for p in compute_stats(state)["per_date"]}
    bits = []
    for i, date in enumerate(state.get("candidates") or [], 1):
        count = per.get(i, {}).get("count", 0)
        picked = i in votes
        label = f"{'✓ ' if picked else ''}{date}（{count}）"
        bits.append((i, date, label, picked))
    return bits


def vote_card(state, user_id="", extend_iso=None):
    bits = _vote_bits(state, user_id)
    body = [FlexText(text="點日期投票，再點一次取消。", size="sm", color=MUTED, wrap=True)]
    actions = []
    if extend_iso and user_id and user_id == state.get("organizer"):
        try:
            start_label = iso_to_label(extend_iso)
        except ValueError:
            start_label = ""
        picker = DatetimePickerAction(label="接結束日", data=f"c=date_end&s={extend_iso}", mode="date",
                                      initial=extend_iso, min=extend_iso)
        if start_label:
            body.append(FlexText(text=f"{start_label} 已加入。連續天數再點「接結束日」。",
                                 size="sm", color=MUTED, wrap=True, margin="md"))
        body.append(FlexButton(style="secondary", height="sm", margin="sm", action=picker))
        actions.append(picker)
    if not bits:
        body.append(FlexText(text="還沒有候選日期。", size="sm", margin="md", wrap=True))
    for i, date, label, picked in bits:
        body.append(_btn(label, f"c=vote&i={i}", display=date,
                         style="primary" if picked else "secondary",
                         color=GREEN if picked else "#546E7A"))
        actions.append(_post(label, f"c=vote&i={i}", display=date))
    if user_id and user_id == state.get("organizer"):
        body.append(_btn("再加日期", "c=dates", style="secondary"))
    actions.extend(menu_actions())
    title = state.get("name") or "露營"
    return _bubble(f"🗳️ {title} 日期投票", body, alt="點日期投票，再點一次取消", quick=_qr(actions))


def signup_card(state):
    body = [
        FlexText(text=f"「{state.get('name') or '露營'}」點選你的出席。攜伴請按 +1 或 +2。",
                 size="sm", color=MUTED, wrap=True),
        _btn("參加", "c=join&g=0", color=GREEN),
        _btn("參加+1", "c=join&g=1", color="#2E7D32"),
        _btn("參加+2", "c=join&g=2", color="#388E3C"),
        _btn("不參加", "c=leave", style="secondary", color="#B71C1C"),
    ]
    quick = _qr([
        _post("參加", "c=join&g=0"), _post("參加+1", "c=join&g=1"),
        _post("參加+2", "c=join&g=2"), _post("不參加", "c=leave"),
    ] + menu_actions())
    return _bubble("🙋 報名", body, alt="報名：參加、參加+1、參加+2、不參加", quick=quick)


def budget_card(state):
    body = [
        FlexText(text=f"「{state.get('name') or '露營'}」每人預算（台幣）。也可直接打「預算 3500」。",
                 size="sm", color=MUTED, wrap=True),
    ]
    actions = []
    for amount, plus, label in BUDGETS:
        data = f"c=bud&v={amount}" + ("&plus=1" if plus else "")
        body.append(_btn(label, data, color=GREEN))
        actions.append(_post(label, data))
    return _bubble("💰 填預算", body, alt="填每人預算：1000、2000、3000、5000 以上",
                   quick=_qr(actions + menu_actions()))


def _avg_text(state):
    att = [m for m in state.get("members", {}).values() if m.get("attending")]
    vals = [m["budget"] for m in att if m.get("budget") is not None]
    if not vals:
        return None
    return str(int(round(statistics.mean(vals))))


def _any_plus(state):
    return any(m.get("budget_plus") and m.get("attending") for m in state.get("members", {}).values())


def stats_card(state):
    s = compute_stats(state)
    best = {p["date"] for p in s["best"]}
    body = []
    if not s["per_date"]:
        body.append(FlexText(text="尚無候選日期", size="sm", color=MUTED, wrap=True))
    for p in s["per_date"]:
        hit = p["date"] in best
        names = "、".join(p["names"]) if p["names"] else "尚無"
        body.append(FlexBox(
            layout="vertical", margin="md", padding_all="10px", corner_radius="8px",
            background_color=BEST_BG if hit else "#F5F5F5",
            contents=[
                FlexText(text=("⭐ " if hit else "") + f"{p['date']}　{p['count']} 票",
                         weight="bold", size="md", wrap=True, color=AMBER if hit else "#333333"),
                FlexText(text=names, size="sm", color=MUTED, wrap=True, margin="sm"),
            ],
        ))
    body.append(FlexSeparator(margin="lg"))
    body.append(FlexText(text=f"👥 人數 {s['headcount']} 人（含攜伴）", weight="bold", margin="md", wrap=True))
    if s["budget"]:
        b = s["budget"]
        body.append(FlexText(
            text=f"💰 最低 {b['min']}／中位 {b['median']:g}／平均 {_avg_text(state)}",
            wrap=True, margin="sm"))
        if _any_plus(state):
            body.append(FlexText(text="「5000 以上」以 5000 元計入平均", size="xs", color="#888888", wrap=True))
    else:
        body.append(FlexText(text="💰 預算：尚無", margin="sm", wrap=True))
    if s["best"]:
        body.append(FlexText(text="⭐ 最佳：" + "、".join(p["date"] for p in s["best"]),
                             weight="bold", color=AMBER, margin="sm", wrap=True))
    body.append(FlexText(text=NO_BOOK, size="xs", color="#888888", margin="md", wrap=True))
    alt = "露營統計"
    if s["best"]:
        alt = "統計：最佳 " + "、".join(p["date"] for p in s["best"]) + f"，{s['headcount']} 人"
    return _bubble(f"📊 {state.get('name') or '露營'} 統計", body, alt=alt)


def cards_for_command(text, ctx, out):
    """打字指令成功後，附上對應的卡片。回傳 FlexMessage 清單。"""
    if not out:
        return []
    parts = text.strip().split()
    if not parts:
        return []
    key = parts[0]
    pid, state = ctx.store.active(ctx.chat_id)
    if not state:
        return []
    if key in ("露營開團", "開團") and ("開團！" in out or "已經有進行中" in out):
        return [menu_card(state)]
    if key == "候選日期" and out.startswith("📅"):
        return [vote_card(state, ctx.user_id)]
    if key in ("露營統計", "統計") and out.startswith("📊"):
        return [stats_card(state)]
    return []


def _qs(data):
    parsed = parse_qs(data or "", keep_blank_values=False)
    return {k: v[0] for k, v in parsed.items() if v}


def _active(ctx):
    return ctx.store.active(ctx.chat_id)


def _only_organizer(ctx, state):
    if ctx.user_id != state.get("organizer"):
        return f"只有主揪 {state.get('organizer_name') or ''} 可以設定候選日期"
    return None


def handle_postback(data, params, ctx):
    """處理按鈕 postback。回傳 (文字或 None, Flex 訊息清單)。"""
    q = _qs(data)
    action = q.get("c")
    if not action:
        return None, []
    params = params or {}
    if not ctx.user_id:
        return "讀不到你的 LINE 帳號，請更新 App 後再點一次", []

    pid, state = _active(ctx)
    if not pid:
        return NO_PLAN, []

    if action in ("dates", "date_start", "date_end", "date_one"):
        denied = _only_organizer(ctx, state)
        if denied:
            cards = [vote_card(state, ctx.user_id)] if state.get("candidates") else []
            return denied, cards

    if action == "dates":
        return "請選擇開始日期。", [date_start_card(state)]

    if action == "date_start":
        iso = params.get("date")
        try:
            label = iso_to_label(iso)
        except ValueError:
            return "沒有收到日期，請再點一次", [date_start_card(state)]
        text = add_candidate(ctx, label)
        _, state = _active(ctx)
        cards = [vote_card(state, ctx.user_id, extend_iso=iso)] if state and state.get("candidates") else []
        return text, cards

    if action == "date_one":
        try:
            label = iso_to_label(q.get("s"))
        except ValueError as e:
            return str(e), [date_start_card(state)]
        text = add_candidate(ctx, label)
        _, state = _active(ctx)
        cards = [vote_card(state, ctx.user_id)] if state and state.get("candidates") else []
        return text, cards

    if action == "date_end":
        end = params.get("date")
        start = q.get("s")
        if not end:
            try:
                return "沒有收到結束日，請再點一次", [date_end_card(state, start, iso_to_label(start))]
            except ValueError:
                return "沒有收到結束日，請再點一次", [date_start_card(state)]
        try:
            label = iso_to_label(start, end)
        except ValueError as e:
            try:
                card = date_end_card(state, start, iso_to_label(start))
            except ValueError:
                card = date_start_card(state)
            return str(e), [card]
        text = add_candidate(ctx, label, replace=iso_to_label(start))
        _, state = _active(ctx)
        cards = [vote_card(state, ctx.user_id)] if state and state.get("candidates") else []
        return text, cards

    if action == "votes":
        if not state.get("candidates"):
            return "主揪還沒設定候選日期", [date_start_card(state)] if ctx.user_id == state.get("organizer") else []
        return "點日期投票，再點一次取消。", [vote_card(state, ctx.user_id)]

    if action == "vote":
        try:
            index = int(q.get("i"))
        except (TypeError, ValueError):
            return "請點日期按鈕", [vote_card(state, ctx.user_id)] if state.get("candidates") else []
        text = toggle_vote(ctx, index)
        _, state = _active(ctx)
        cards = [vote_card(state, ctx.user_id)] if state and state.get("candidates") else []
        return text, cards

    if action == "signup":
        return "請點選是否參加。", [signup_card(state)]

    if action == "join":
        if q.get("g") not in {"0", "1", "2"}:
            return "請點參加、參加+1 或參加+2", [signup_card(state)]
        guests = int(q["g"])
        text = cmd_join([f"+{guests}"] if guests else [], ctx)
        return text, [signup_card(state)]

    if action == "leave":
        return cmd_leave([], ctx), [signup_card(state)]

    if action == "budget":
        return "請點每人預算，或輸入「預算 金額」。", [budget_card(state)]

    if action == "bud":
        allowed = {str(amount): (amount, plus) for amount, plus, _label in BUDGETS}
        picked = allowed.get(q.get("v"))
        if not picked:
            return "請點預算按鈕，或輸入「預算 金額」。", [budget_card(state)]
        amount, plus = picked
        if q.get("plus") == "1" and amount == 5000:
            plus = True
        text = set_budget_amount(ctx, amount, plus=plus)
        return text, [budget_card(state)]

    if action == "stats":
        return None, [stats_card(state)]

    if action == "search":
        text = cmd_search([], ctx)
        _, state = _active(ctx)
        cards = [menu_card(state)] if state else []
        if text and text.startswith("已整理好條件"):
            text += f"\n提醒：{NO_BOOK}，訂房由主揪確認。"
        return text, cards

    return None, []
