"""露營規劃指令。handler(args, ctx) -> str | None"""
import json
import os
import re
import statistics
import time
from dataclasses import dataclass, field
from typing import Callable

from .store import BASE, Store, new_state

ORGANIZER_NAME = "翔暉"
REQ_DIR = os.path.abspath(os.path.join(BASE, "requests"))
DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}(-(\d{1,2}/)?\d{1,2})?$")


@dataclass
class Ctx:
    chat_id: str
    user_id: str
    name_fn: Callable[[str], str] = lambda uid: uid[-4:] or "某人"
    store: Store = field(default_factory=Store)
    req_dir: str = REQ_DIR

    def name(self):
        return self.name_fn(self.user_id)


NO_PLAN = "目前沒有進行中的露營團，輸入「露營開團 名稱」開始 🏕️"


def parse_dates(args):
    """'10/31-11/1, 11/7-11/8' -> ['10/31-11/1', '11/7-11/8']；格式錯誤 raise ValueError"""
    tokens = [t for t in re.split(r"[,，、\s]+", " ".join(args)) if t]
    for t in tokens:
        if not DATE_RE.match(t):
            raise ValueError(t)
    return tokens


def parse_nums(args):
    """['1','3'] 或 ['1,3'] -> [1,3]；非數字回傳 None"""
    tokens = [t for t in re.split(r"[,，、\s]+", " ".join(args)) if t]
    if not tokens or not all(t.isdigit() for t in tokens):
        return None
    return sorted(set(int(t) for t in tokens))


def parse_guests(args):
    for a in args:
        m = re.fullmatch(r"[+＋](\d+)", a)
        if m:
            return int(m.group(1))
    return 0


def _member(state, ctx):
    m = state["members"].setdefault(ctx.user_id, {"name": ctx.name(), "attending": None,
                                                  "guests": 0, "budget": None, "votes": []})
    m["name"] = ctx.name()
    return m


def _with_plan(fn):
    def wrapper(args, ctx):
        pid, state = ctx.store.active(ctx.chat_id)
        if not pid:
            return NO_PLAN
        out = fn(args, ctx, state)
        ctx.store.save(pid, state)
        return out
    return wrapper


# ---------- 開團 / 取消 ----------
def cmd_open(args, ctx):
    pid, state = ctx.store.active(ctx.chat_id)
    if pid:
        return f"已經有進行中的團「{state['name']}」，要重開請先「露營取消」"
    name = " ".join(args) or "露營團"
    st = new_state(name, ctx.user_id, ctx.name())
    st["members"][ctx.user_id] = {"name": ctx.name(), "attending": True, "guests": 0,
                                  "budget": None, "votes": []}
    ctx.store.create(ctx.chat_id, st)
    return (f"🏕️「{name}」開團！主揪：{ctx.name()}\n"
            "下一步：候選日期 10/31-11/1, 11/7-11/8")


def cmd_cancel(args, ctx):
    pid, state = ctx.store.active(ctx.chat_id)
    if not pid:
        return NO_PLAN
    ctx.store.close(pid)
    return f"已關閉「{state['name']}」"


# ---------- 規劃 ----------
@_with_plan
def cmd_dates(args, ctx, state):
    if ctx.user_id != state["organizer"]:
        return f"只有主揪 {state['organizer_name']} 可以設定候選日期"
    try:
        new = parse_dates(args)
    except ValueError as e:
        return f"看不懂日期「{e}」，格式例：候選日期 10/31-11/1, 11/7-11/8"
    if not new:
        return "格式例：候選日期 10/31-11/1, 11/7-11/8"
    for d in new:
        if d not in state["candidates"]:
            state["candidates"].append(d)
    lines = [f"{i}. {d}" for i, d in enumerate(state["candidates"], 1)]
    return "📅 候選日期：\n" + "\n".join(lines) + "\n請回「可以 1 3」投票"


def cmd_vote(args, ctx):
    nums = parse_nums(args)
    if nums is None:
        return None  # 「可以」是日常用語，非數字就不理
    return _vote(args, ctx)


@_with_plan
def _vote(args, ctx, state):
    nums = parse_nums(args)
    n = len(state["candidates"])
    if not n:
        return "主揪還沒設定候選日期"
    bad = [x for x in nums if not 1 <= x <= n]
    if bad:
        return f"沒有第 {bad[0]} 個選項（共 {n} 個）"
    m = _member(state, ctx)
    m["votes"], m["attending"] = nums, True
    return f"✅ {m['name']} 可以：" + "、".join(state["candidates"][i - 1] for i in nums)


@_with_plan
def cmd_budget(args, ctx, state):
    try:
        v = int(re.sub(r"[,元$NT]", "", args[0]))
        assert v >= 0
    except Exception:
        return "格式例：預算 3000（每人台幣）"
    m = _member(state, ctx)
    m["budget"] = v
    return f"💰 {m['name']} 預算 {v} 元/人"


@_with_plan
def cmd_join(args, ctx, state):
    m = _member(state, ctx)
    m["attending"] = True
    m["guests"] = parse_guests(args)
    extra = f"（+{m['guests']}）" if m["guests"] else ""
    return f"🙋 {m['name']} 參加{extra}，目前 {_headcount(state)} 人"


@_with_plan
def cmd_leave(args, ctx, state):
    m = _member(state, ctx)
    m.update(attending=False, guests=0, votes=[])
    return f"😢 {m['name']} 不參加，目前 {_headcount(state)} 人"


@_with_plan
def cmd_count(args, ctx, state):
    names = [f"{m['name']}" + (f"+{m['guests']}" if m["guests"] else "")
             for m in state["members"].values() if m["attending"]]
    return f"👥 {_headcount(state)} 人：" + ("、".join(names) or "尚無")


@_with_plan
def cmd_wish(args, ctx, state):
    text = " ".join(args).strip()
    if not text:
        return "格式例：需求 可帶狗"
    state["wishes"].append({"by": ctx.name(), "text": text})
    return f"📝 已記下需求：{text}"


@_with_plan
def cmd_area(args, ctx, state):
    text = " ".join(args).strip()
    if not text:
        return f"目前地區：{state['area'] or '未定'}（設定：地區 台中）"
    state["area"] = text
    return f"📍 地區：{text}"


# ---------- 統計 ----------
def _headcount(state):
    return sum(1 + m["guests"] for m in state["members"].values() if m["attending"])


def compute_stats(state):
    att = [m for m in state["members"].values() if m["attending"]]
    per = []
    for i, d in enumerate(state["candidates"], 1):
        voters = [m for m in att if i in m["votes"]]
        per.append({"idx": i, "date": d, "count": len(voters),
                    "people": sum(1 + m["guests"] for m in voters),
                    "names": [m["name"] for m in voters]})
    top = max((p["count"] for p in per), default=0)
    best = [p for p in per if p["count"] == top and top > 0]
    budgets = [m["budget"] for m in att if m["budget"] is not None]
    b = None
    if budgets:
        b = {"min": min(budgets), "median": statistics.median(budgets),
             "max": max(budgets), "suggested": min(budgets)}
    return {"per_date": per, "best": best, "headcount": _headcount(state),
            "members": len(att), "budget": b, "area": state["area"],
            "wishes": [w["text"] for w in state["wishes"]]}


@_with_plan
def cmd_stats(args, ctx, state):
    s = compute_stats(state)
    L = [f"📊「{state['name']}」統計"]
    for p in s["per_date"]:
        L.append(f"{p['idx']}. {p['date']}：{p['count']} 票 " + ("、".join(p["names"]) or "-"))
    if s["best"]:
        L.append("⭐ 最佳：" + "、".join(p["date"] for p in s["best"]))
    L.append(f"👥 人數：{s['headcount']}（含攜伴）")
    if s["budget"]:
        b = s["budget"]
        L.append(f"💰 預算 最低{b['min']}／中位{b['median']:g}／最高{b['max']}，建議每人 {b['suggested']}")
    else:
        L.append("💰 預算：尚無")
    L.append(f"📍 地區：{s['area'] or '未定'}")
    if s["wishes"]:
        L.append("📝 需求：" + "、".join(s["wishes"]))
    if state["options"]:
        L.append(_options_tally(state))
    return "\n".join(L)


# ---------- 找木屋 ----------
def build_request(chat_id, state):
    s = compute_stats(state)
    best = s["best"][0]["date"] if s["best"] else None
    per = s["budget"]["suggested"] if s["budget"] else None
    return {"chat_id": chat_id, "plan": state["name"], "best_date": best,
            "all_best_dates": [p["date"] for p in s["best"]], "headcount": s["headcount"],
            "budget_per_person": per,
            "budget_total": per * s["headcount"] if per is not None else None,
            "area": s["area"], "wishes": s["wishes"], "accommodation": "木屋",
            "created": time.strftime("%Y-%m-%dT%H:%M:%S%z")}


@_with_plan
def cmd_search(args, ctx, state):
    req = build_request(ctx.chat_id, state)
    if not req["best_date"]:
        return "還沒有人投票日期，先「候選日期」+「可以 1 2」"
    os.makedirs(ctx.req_dir, exist_ok=True)
    path = os.path.join(ctx.req_dir, f"{ctx.chat_id}-{int(time.time())}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(req, f, ensure_ascii=False, indent=2)
    state["phase"] = "searching"
    state["last_request"] = path
    return "已整理好條件，正在幫大家找木屋，找到會貼候選上來"


# ---------- 木屋候選 ----------
def format_options(options):
    L = ["🏡 木屋候選："]
    for i, o in enumerate(options, 1):
        L.append(f"{i}. {o.get('name','?')}｜{o.get('price','?')}")
        if o.get("note"):
            L.append(f"   {o['note']}")
        if o.get("link"):
            L.append(f"   {o['link']}")
    L.append("喜歡哪間請回「已選 編號」")
    return "\n".join(L)


def _options_tally(state):
    cnt = {}
    for v in state["option_votes"].values():
        cnt[v] = cnt.get(v, 0) + 1
    parts = [f"{i}.{o.get('name','?')} {cnt.get(i,0)}票" for i, o in enumerate(state["options"], 1)]
    return "🏡 木屋票數：" + "、".join(parts)


@_with_plan
def cmd_pick(args, ctx, state):
    if not state["options"]:
        return "還沒有木屋候選喔"
    nums = parse_nums(args)
    if not nums or len(nums) != 1 or not 1 <= nums[0] <= len(state["options"]):
        return f"請回「已選 1」～「已選 {len(state['options'])}」"
    state["option_votes"][ctx.user_id] = nums[0]
    _member(state, ctx)
    return f"👍 {ctx.name()} 選 {nums[0]}. {state['options'][nums[0]-1].get('name')}\n{_options_tally(state)}"


@_with_plan
def cmd_confirm(args, ctx, state):
    if not state["options"]:
        return "還沒有木屋候選喔"
    nums = parse_nums(args)
    if nums:
        idx = nums[0]
    else:
        cnt = {}
        for v in state["option_votes"].values():
            cnt[v] = cnt.get(v, 0) + 1
        if not cnt:
            return "還沒人投票，請先「已選 編號」或「確定訂 編號」"
        idx = max(cnt, key=lambda k: (cnt[k], -k))
    if not 1 <= idx <= len(state["options"]):
        return "沒有這個編號"
    state["chosen"] = idx
    state["phase"] = "chosen"
    o = state["options"][idx - 1]
    return f"✅ 決定：{idx}. {o.get('name')}（{o.get('price','')}）\n將由主揪 {ORGANIZER_NAME} 確認訂房，機器人不會代訂或付款"


def set_options(store, chat_id, options):
    pid, state = store.active(chat_id)
    if not pid:
        raise RuntimeError("no active plan for " + chat_id)
    state["options"], state["option_votes"], state["phase"] = options, {}, "options"
    store.save(pid, state)
    return format_options(options)


CAMP_REGISTRY = {
    "露營開團": cmd_open, "開團": cmd_open, "露營取消": cmd_cancel,
    "候選日期": cmd_dates, "可以": cmd_vote, "投票": cmd_vote,
    "預算": cmd_budget, "人數": cmd_count, "參加": cmd_join, "不參加": cmd_leave,
    "需求": cmd_wish, "地區": cmd_area, "露營統計": cmd_stats, "統計": cmd_stats,
    "找木屋": cmd_search, "已選": cmd_pick, "確定訂": cmd_confirm,
}
