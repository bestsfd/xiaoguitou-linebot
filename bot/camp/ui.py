"""露營流程的 Flex 卡片、快速回覆與 postback。使用者看到的文字都是繁體中文。"""
import statistics
from urllib.parse import parse_qs, urlencode

from linebot.v3.messaging import (DatetimePickerAction, FlexBox, FlexBubble, FlexButton,
                                  FlexCarousel, FlexMessage, FlexSeparator, FlexText,
                                  MessageAction, PostbackAction, QuickReply, QuickReplyItem,
                                  URIAction)

from .catalog import CATEGORIES, choice_labels, next_month_labels, tops
from .flexcheck import clip
from .logic import (NO_PLAN, add_candidate, cmd_join, cmd_leave, cmd_search, compute_stats,
                    iso_to_label, search_winners, set_budget_amount, toggle_pick, toggle_vote)
from .places import ATTRACTIONS, attraction_entries, cabin_by_id, match_cabins, spots_for

GREEN = "#1F6B4A"
AMBER = "#E65100"
BEST_BG = "#FFF4D6"
MUTED = "#666666"
NO_BOOK = "我才不會代訂或付款咧"

MENU = (
    ("日期投票", "c=poll&k=date"),
    ("選日期", "c=dates"),
    ("地點投票", "c=poll&k=region"),
    ("住宿類型", "c=poll&k=stay"),
    ("需求/設施", "c=poll&k=facility"),
    ("天數", "c=poll&k=nights"),
    ("報名", "c=signup"),
    ("填預算", "c=budget"),
    ("看統計", "c=stats"),
    ("找木屋", "c=search"),
    ("找景點", "c=spots"),
)
BUDGETS = (
    (1000, False, "1000"),
    (2000, False, "2000"),
    (3000, False, "3000"),
    (5000, True, "5000 以上"),
)
POLL_INTRO = {
    "date": "點週末投票啦，再點一次就取消哦。這個月碰到的國定假日連假也會列出來。主揪仍可「選日期」耶。",
    "region": "可複選哦。台中～台北之間含新竹、苗栗、桃園山區、台中北部啦。",
    "stay": "想住哪一種咧？可複選啦。",
    "facility": "朋友帶小孩就點「親子」啦。可複選哦。",
    "nights": "預計住幾晚呀？點一下啦。",
}


def _clip(text, n=20):
    return clip(text, n)


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


def pick_data(cat, label):
    return urlencode([("c", "pick"), ("k", cat), ("v", label)])


def quick_for_names(names):
    actions = []
    menu = dict(MENU)
    for name in names or []:
        if name == "幫助":
            actions.append(MessageAction(label="幫助", text="幫助"))
        elif name in menu:
            actions.append(_post(name, menu[name]))
    return _qr(actions)


def _bubbles(title, components, *, color=GREEN):
    components = [item for item in components if item is not None]
    if not components:
        components = [FlexText(text="尚無", size="sm", wrap=True)]
    bubbles = []
    for index in range(0, len(components), 9):
        chunk = components[index:index + 9]
        bubbles.append(FlexBubble(
            size="mega",
            header=FlexBox(
                layout="vertical", background_color=color, padding_all="16px",
                contents=[FlexText(text=title, weight="bold", size="lg", color="#FFFFFF", wrap=True)],
            ),
            body=FlexBox(layout="vertical", spacing="sm", padding_all="16px", contents=chunk),
        ))
    return bubbles


def _flex(bubbles, *, alt, quick=None):
    bubbles = [item for item in bubbles if item][:12]
    if not bubbles:
        bubbles = _bubbles("露營", [FlexText(text=NO_BOOK, size="sm", wrap=True)])
    contents = bubbles[0] if len(bubbles) == 1 else FlexCarousel(contents=bubbles)
    return FlexMessage(alt_text=_clip(alt, 400), contents=contents,
                       quick_reply=quick or _qr(menu_actions()))


def _bubble(header, body_contents, *, alt, quick=None, header_color=GREEN):
    return _flex(_bubbles(header, body_contents, color=header_color), alt=alt, quick=quick)


def menu_card(state, user_id=""):
    state = state or {}
    bubbles = []
    hint = FlexText(text=f"主揪 {state.get('organizer_name') or '未定'} 哦。點按鈕就好啦，不用打字。{NO_BOOK}。",
                    size="sm", color=MUTED, wrap=True)
    buttons = [_btn(label, data) for label, data in MENU]
    bubbles.extend(_bubbles(f"🏕️ {state.get('name') or '露營團'}", [hint] + buttons))
    bubbles.extend(_date_bubbles(state, user_id))
    return _flex(bubbles, alt=f"露營選單：{state.get('name') or '露營團'}")


def _member_picks(state, user_id, cat):
    member = (state.get("members") or {}).get(user_id) or {}
    return set((member.get("picks") or {}).get(cat) or [])


def _date_specs(state, user_id):
    member = (state.get("members") or {}).get(user_id) or {}
    votes = set(member.get("votes") or [])
    picks = _member_picks(state, user_id, "date")
    candidates = list(state.get("candidates") or [])
    specs = []
    seen = set()
    for label in next_month_labels():
        seen.add(label)
        if label in candidates:
            index = candidates.index(label) + 1
            specs.append((label, f"c=vote&i={index}", index in votes))
        else:
            specs.append((label, pick_data("date", label), label in picks))
    for index, label in enumerate(candidates, 1):
        if label in seen:
            continue
        specs.append((label, f"c=vote&i={index}", index in votes))
    return specs


def _spec_buttons(specs):
    buttons = []
    actions = []
    for label, data, picked in specs:
        shown = f"{'✓ ' if picked else ''}{label}"
        buttons.append(_btn(shown, data, display=label,
                            style="primary" if picked else "secondary",
                            color=GREEN if picked else "#546E7A"))
        actions.append(_post(shown, data, display=label))
    return buttons, actions


def _date_bubbles(state, user_id):
    specs = _date_specs(state, user_id)
    intro = FlexText(text=POLL_INTRO["date"], size="sm", color=MUTED, wrap=True)
    buttons, _actions = _spec_buttons(specs)
    return _bubbles("📅 下個月的週末", [intro] + buttons)


def poll_card(state, user_id, cat):
    if cat == "date":
        buttons, actions = _spec_buttons(_date_specs(state, user_id))
        title = "📅 下個月的週末"
    else:
        chosen = _member_picks(state, user_id, cat)
        specs = [(label, pick_data(cat, label), label in chosen) for label in choice_labels(state, cat)]
        buttons, actions = _spec_buttons(specs)
        title = "🗳️ " + dict(CATEGORIES)[cat]
    intro = FlexText(text=POLL_INTRO[cat], size="sm", color=MUTED, wrap=True)
    return _flex(_bubbles(title, [intro] + buttons), alt=POLL_INTRO[cat], quick=_qr(actions + menu_actions()))


def date_start_card(state):
    picker = DatetimePickerAction(label="選開始日", data="c=date_start", mode="date")
    body = [
        FlexText(text="點「選開始日」就會加入候選啦。連續幾天的話，加入後再選結束日哦。", wrap=True, size="sm", color=MUTED),
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
    hint = f"開始日 {start_label} 哦。選結束日，或按「就這一天」啦。"
    if already:
        hint += f"目前已有 {already} 個候選。"
    body = [
        FlexText(text=hint, wrap=True, size="sm", color=MUTED),
        FlexButton(style="primary", height="sm", margin="md", color=GREEN, action=picker),
        _btn("就這一天", f"c=date_one&s={start_iso}", style="secondary"),
    ]
    quick = _qr([picker, _post("就這一天", f"c=date_one&s={start_iso}")] + menu_actions())
    return _bubble("📅 選結束日", body, alt=f"開始日 {start_label}，請選結束日或就這一天", quick=quick)


def vote_card(state, user_id="", extend_iso=None):
    member = (state.get("members") or {}).get(user_id) or {}
    votes = set(member.get("votes") or [])
    per = {p["idx"]: p for p in compute_stats(state)["per_date"]}
    body = [FlexText(text="點日期投票啦，再點一次取消哦。", size="sm", color=MUTED, wrap=True)]
    actions = []
    if extend_iso and user_id and user_id == state.get("organizer"):
        try:
            start_label = iso_to_label(extend_iso)
        except ValueError:
            start_label = ""
        picker = DatetimePickerAction(label="接結束日", data=f"c=date_end&s={extend_iso}", mode="date",
                                      initial=extend_iso, min=extend_iso)
        if start_label:
            body.append(FlexText(text=f"{start_label} 已加入啦。連續天數再點「接結束日」哦。",
                                 size="sm", color=MUTED, wrap=True, margin="md"))
        body.append(FlexButton(style="secondary", height="sm", margin="sm", action=picker))
        actions.append(picker)
    candidates = state.get("candidates") or []
    if not candidates:
        body.append(FlexText(text="還沒有候選日期耶。", size="sm", margin="md", wrap=True))
    for index, date in enumerate(candidates, 1):
        count = per.get(index, {}).get("count", 0)
        picked = index in votes
        label = f"{'✓ ' if picked else ''}{date}（{count}）"
        body.append(_btn(label, f"c=vote&i={index}", display=date,
                         style="primary" if picked else "secondary",
                         color=GREEN if picked else "#546E7A"))
        actions.append(_post(label, f"c=vote&i={index}", display=date))
    if user_id and user_id == state.get("organizer"):
        body.append(_btn("再加日期", "c=dates", style="secondary"))
    actions.extend(menu_actions())
    title = state.get("name") or "露營"
    return _flex(_bubbles(f"🗳️ {title} 日期投票", body), alt="點日期投票啦，再點一次取消", quick=_qr(actions))


def signup_card(state):
    body = [
        FlexText(text=f"「{state.get('name') or '露營'}」來報名啦。自己來按參加，有帶人就按 +1 或 +2 哦。",
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
        FlexText(text=f"「{state.get('name') or '露營'}」每人預算（台幣）哦。也可直接打「預算 3500」啦。",
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


def _choice_box(row, hit):
    names = "、".join(row["names"]) if row["names"] else "尚無"
    return FlexBox(
        layout="vertical", margin="md", padding_all="10px", corner_radius="8px",
        background_color=BEST_BG if hit else "#F5F5F5",
        contents=[
            FlexText(text=("⭐ " if hit else "") + f"{row['label']}　{row['count']} 票",
                     weight="bold", size="md", wrap=True, color=AMBER if hit else "#333333"),
            FlexText(text=names, size="sm", color=MUTED, wrap=True, margin="sm"),
        ],
    )


def stats_card(state):
    stats = compute_stats(state)
    bubbles = []
    for key, title in CATEGORIES:
        rows = stats["categories"][key]
        best = {row["label"] for row in tops(rows)}
        if not rows:
            body = [FlexText(text="尚無", size="sm", color=MUTED, wrap=True)]
        else:
            body = [_choice_box(row, row["label"] in best) for row in rows]
        bubbles.extend(_bubbles(f"📊 {title}", body))
    people = [FlexText(text=f"👥 人數 {stats['headcount']} 人（含攜伴）", weight="bold", margin="md", wrap=True)]
    if stats["budget"]:
        budget = stats["budget"]
        people.append(FlexText(
            text=f"💰 最低 {budget['min']}／中位 {budget['median']:g}／平均 {_avg_text(state)}",
            wrap=True, margin="sm"))
        if _any_plus(state):
            people.append(FlexText(text="「5000 以上」以 5000 元計入平均", size="xs", color="#888888", wrap=True))
    else:
        people.append(FlexText(text="💰 預算：尚無", margin="sm", wrap=True))
    date_best = tops(stats["categories"]["date"])
    if date_best:
        people.append(FlexText(text="⭐ 最佳：" + "、".join(row["label"] for row in date_best),
                               weight="bold", color=AMBER, margin="sm", wrap=True))
    people.append(FlexText(text=NO_BOOK, size="xs", color="#888888", margin="md", wrap=True))
    bubbles.extend(_bubbles(f"📊 {state.get('name') or '露營'} 人數與預算", people))
    alt = "露營統計"
    if date_best:
        alt = "統計：最佳 " + "、".join(row["label"] for row in date_best) + f"，{stats['headcount']} 人"
    return _flex(bubbles, alt=alt)


def _winner_line(state):
    winners = search_winners(state) if state else {}
    bits = []
    if winners.get("dates"):
        bits.append("日期 " + "、".join(winners["dates"]))
    if winners.get("regions"):
        bits.append("地區 " + "、".join(winners["regions"]))
    if winners.get("stay"):
        bits.append("住宿 " + winners["stay"])
    if winners.get("facilities"):
        bits.append("需求 " + "、".join(winners["facilities"]))
    if winners.get("nights"):
        bits.append(winners["nights"])
    if winners.get("budget") is not None:
        bits.append(f"預算 {winners['budget']} 元/人")
    if winners.get("headcount"):
        bits.append(f"{winners['headcount']} 人")
    return "、".join(bits)


def cabin_message(state):
    winners = search_winners(state) if state else {}
    cabins = match_cabins(winners)
    summary = _winner_line(state) or "還沒投地區，先列出台中到台北之間的親子木屋"
    if not cabins:
        body = [FlexText(text=f"{summary}。這組條件還沒有對上的木屋耶，改地點、房型或預算看看啦。{NO_BOOK}。",
                         size="sm", wrap=True)]
        return _flex(_bubbles("🏡 木屋", body), alt="沒有對上的木屋，不會代訂或付款")
    bubbles = _bubbles("🏡 對上的木屋", [
        FlexText(text=summary, size="sm", wrap=True),
        FlexText(text=f"以下是整理好的親子向住宿啦。點官方頁自己看哦，{NO_BOOK}。", size="sm", color=MUTED, wrap=True),
    ])
    for cabin in cabins[:10]:
        spots = "、".join(item["name"] for item in attraction_entries(cabin["attractions"]))
        bubbles.extend(_bubbles(cabin["name"], [
            FlexText(text=f"{cabin['county']}｜{'、'.join(cabin['stays'])}", size="sm", color=MUTED, wrap=True),
            FlexText(text=cabin["price"], size="sm", wrap=True),
            FlexText(text="親子：" + cabin["kid_facilities"], size="sm", wrap=True),
            FlexText(text="附近：" + spots, size="sm", wrap=True),
            FlexText(text=NO_BOOK, size="xs", color="#888888", wrap=True),
            FlexButton(style="link", height="sm", margin="sm",
                       action=URIAction(label="看官方頁", uri=cabin["url"])),
            _btn("附近景點", f"c=spots&id={cabin['id']}", style="secondary"),
        ]))
    names = "、".join(cabin["name"] for cabin in cabins[:4])
    return _flex(bubbles, alt=f"親子木屋：{names}。{NO_BOOK}")


def spots_message(state, cabin_id=None):
    from .places import CABINS
    focus = cabin_by_id(cabin_id) if cabin_id else None
    if focus:
        pairs = [(key, ATTRACTIONS[key]) for key in focus["attractions"] if key in ATTRACTIONS]
        pool = [focus]
        header = f"📍 {focus['name']} 附近"
    else:
        winners = search_winners(state) if state else {}
        pool = match_cabins(winners) if state else list(CABINS)
        pairs = spots_for(winners, pool if state else [])
        header = "📍 親子景點"
    if not pairs:
        body = [FlexText(text=f"目前沒有對上的景點耶。{NO_BOOK}。", size="sm", wrap=True)]
        return _flex(_bubbles(header, body), alt="沒有對上的景點")
    bubbles = []
    for key, spot in pairs:
        nearby = [item["name"] for item in pool if key in item["attractions"]]
        note = "、".join(nearby) if nearby else "這批木屋資料裡沒有同一帶的小木屋耶，可當順遊啦"
        bubbles.extend(_bubbles(spot["name"], [
            FlexText(text=f"{spot['county']}｜{spot['kind']}", size="sm", color=MUTED, wrap=True),
            FlexText(text=spot["blurb"], size="sm", wrap=True),
            FlexText(text="附近住宿：" + note, size="sm", wrap=True),
            FlexText(text=NO_BOOK, size="xs", color="#888888", wrap=True),
            FlexButton(style="link", height="sm", margin="sm",
                       action=URIAction(label="看官方頁", uri=spot["url"])),
        ]))
    return _flex(bubbles, alt="親子景點，不會代訂或付款")


def cards_for_command(text, ctx, out):
    """打字指令成功後，附上對應的卡片。回傳 FlexMessage 清單。"""
    if not out:
        return []
    parts = text.strip().split()
    if not parts:
        return []
    key = parts[0]
    pid, state = ctx.store.active(ctx.chat_id)
    if key == "找景點" and "景點" in out:
        return [spots_message(state)]
    if not state:
        return []
    if key in ("露營開團", "開團") and ("開團！" in out or "已經有進行中" in out):
        return [menu_card(state, ctx.user_id)]
    if key == "候選日期" and out.startswith("📅"):
        return [vote_card(state, ctx.user_id)]
    if key in ("露營統計", "統計") and out.startswith("📊"):
        return [stats_card(state)]
    if key == "找木屋" and out.startswith("已整理好條件"):
        return [cabin_message(state)]
    return []


def _qs(data):
    parsed = parse_qs(data or "", keep_blank_values=False)
    return {k: v[0] for k, v in parsed.items() if v}


def _active(ctx):
    return ctx.store.active(ctx.chat_id)


def _only_organizer(ctx, state):
    if ctx.user_id != state.get("organizer"):
        return f"只有主揪 {state.get('organizer_name') or ''} 可以設定候選日期啦"
    return None


def handle_postback(data, params, ctx):
    """處理按鈕 postback。回傳 (文字或 None, Flex 訊息清單)。"""
    query = _qs(data)
    action = query.get("c")
    if not action:
        return None, []
    params = params or {}
    if not ctx.user_id:
        return "讀不到你的 LINE 帳號耶，請更新 App 後再點一次啦", []

    if action == "spots":
        _pid, state = _active(ctx)
        return f"點官方頁自己看啦。{NO_BOOK}。", [spots_message(state, query.get("id"))]

    pid, state = _active(ctx)
    if not pid:
        return NO_PLAN, []

    if action in ("dates", "date_start", "date_end", "date_one"):
        denied = _only_organizer(ctx, state)
        if denied:
            cards = [vote_card(state, ctx.user_id)] if state.get("candidates") else []
            return denied, cards

    if action == "dates":
        return "請選擇開始日期啦。", [date_start_card(state)]

    if action == "date_start":
        iso = params.get("date")
        try:
            label = iso_to_label(iso)
        except ValueError:
            return "沒有收到日期耶，請再點一次啦", [date_start_card(state)]
        text = add_candidate(ctx, label)
        _, state = _active(ctx)
        cards = [vote_card(state, ctx.user_id, extend_iso=iso)] if state and state.get("candidates") else []
        return text, cards

    if action == "date_one":
        try:
            label = iso_to_label(query.get("s"))
        except ValueError as exc:
            return str(exc), [date_start_card(state)]
        text = add_candidate(ctx, label)
        _, state = _active(ctx)
        cards = [vote_card(state, ctx.user_id)] if state and state.get("candidates") else []
        return text, cards

    if action == "date_end":
        end = params.get("date")
        start = query.get("s")
        if not end:
            try:
                return "沒有收到結束日耶，請再點一次啦", [date_end_card(state, start, iso_to_label(start))]
            except ValueError:
                return "沒有收到結束日耶，請再點一次啦", [date_start_card(state)]
        try:
            label = iso_to_label(start, end)
        except ValueError as exc:
            try:
                card = date_end_card(state, start, iso_to_label(start))
            except ValueError:
                card = date_start_card(state)
            return str(exc), [card]
        text = add_candidate(ctx, label, replace=iso_to_label(start))
        _, state = _active(ctx)
        cards = [vote_card(state, ctx.user_id)] if state and state.get("candidates") else []
        return text, cards

    if action == "votes":
        if not state.get("candidates"):
            return "主揪還沒設定候選日期耶", [date_start_card(state)] if ctx.user_id == state.get("organizer") else []
        return "點日期投票啦，再點一次取消哦。", [vote_card(state, ctx.user_id)]

    if action == "vote":
        try:
            index = int(query.get("i"))
        except (TypeError, ValueError):
            return "請點日期按鈕啦", [vote_card(state, ctx.user_id)] if state.get("candidates") else []
        text = toggle_vote(ctx, index)
        _, state = _active(ctx)
        cards = [vote_card(state, ctx.user_id)] if state and state.get("candidates") else []
        return text, cards

    if action == "poll":
        cat = query.get("k")
        if cat not in dict(CATEGORIES):
            return "沒有這個選項耶", [menu_card(state, ctx.user_id)]
        return POLL_INTRO[cat], [poll_card(state, ctx.user_id, cat)]

    if action == "pick":
        text = toggle_pick(ctx, query.get("k"), query.get("v"))
        _, state = _active(ctx)
        cat = query.get("k")
        cards = [poll_card(state, ctx.user_id, cat)] if state and cat in dict(CATEGORIES) else []
        return text, cards

    if action == "signup":
        return "請點選是否參加啦。", [signup_card(state)]

    if action == "join":
        if query.get("g") not in {"0", "1", "2"}:
            return "請點參加、參加+1 或參加+2 啦", [signup_card(state)]
        guests = int(query["g"])
        text = cmd_join([f"+{guests}"] if guests else [], ctx)
        return text, [signup_card(state)]

    if action == "leave":
        return cmd_leave([], ctx), [signup_card(state)]

    if action == "budget":
        return "請點每人預算啦，或輸入「預算 金額」。", [budget_card(state)]

    if action == "bud":
        allowed = {str(amount): (amount, plus) for amount, plus, _label in BUDGETS}
        picked = allowed.get(query.get("v"))
        if not picked:
            return "請點預算按鈕啦，或輸入「預算 金額」。", [budget_card(state)]
        amount, plus = picked
        if query.get("plus") == "1" and amount == 5000:
            plus = True
        text = set_budget_amount(ctx, amount, plus=plus)
        return text, [budget_card(state)]

    if action == "stats":
        return None, [stats_card(state)]

    if action == "search":
        text = cmd_search([], ctx)
        _, state = _active(ctx)
        if text and text.startswith("已整理好條件"):
            text += f"\n提醒哦：{NO_BOOK}，訂房由主揪確認啦。"
            cards = [cabin_message(state)] if state else []
        else:
            cards = [menu_card(state, ctx.user_id)] if state else []
        return text, cards

    return None, []
