"""現成可點的露營選項。週末與國定假日依 Asia/Taipei 動態計算。"""
import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Taipei")
WEEKDAY = "一二三四五六日"

CATEGORIES = (
    ("date", "日期"),
    ("region", "地點"),
    ("stay", "住宿類型"),
    ("facility", "需求/設施"),
    ("nights", "天數"),
)

REGIONS = (
    "北部", "中部", "南部", "東部", "台中～台北之間",
    "新竹", "苗栗", "台中", "南投", "宜蘭", "花蓮", "嘉義", "屏東",
)
STAYS = ("木屋", "豪華露營", "自搭帳", "都可以")
FACILITIES = ("可烤肉", "親子", "寵物友善", "溪邊", "有雲海/山景", "獨立衛浴", "提供早餐")
NIGHTS = ("一泊二日", "二泊三日")
CHOICES = {
    "region": REGIONS,
    "stay": STAYS,
    "facility": FACILITIES,
    "nights": NIGHTS,
}

# 合併連假時，較適合出遊的名稱優先，避免按鈕超過 20 字。
_NAME_RANK = ("春節", "清明", "中秋", "國慶", "端午", "光復", "行憲", "勞動", "和平", "元旦", "教師", "兒童")


def taipei_today(now=None):
    if now is None:
        now = datetime.datetime.now(TZ)
    if isinstance(now, datetime.datetime):
        if now.tzinfo is None:
            now = now.replace(tzinfo=TZ)
        else:
            now = now.astimezone(TZ)
        return now.date()
    return now


def next_month(today):
    if today.month == 12:
        return today.year + 1, 1
    return today.year, today.month + 1


def _qingming(year):
    """2000–2099 清明日期的常用近似。"""
    y = year % 100
    day = int(y * 0.2422 + 4.81) - int(y // 4)
    return datetime.date(year, 4, day)


def _expand(day, name):
    wd = day.weekday()
    if wd == 4:  # 五 → 五到日
        return day, day + datetime.timedelta(days=2), name
    if wd == 5:  # 六逢假，前一個工作日補假 → 五到日
        return day - datetime.timedelta(days=1), day + datetime.timedelta(days=1), name
    if wd in (6, 0):  # 日或一 → 六到一
        shift = 1 if wd == 6 else 2
        return day - datetime.timedelta(days=shift), day + datetime.timedelta(days=(1 if wd == 6 else 0)), name
    return day, day, name


def _holidays(year):
    spans = []
    fixed = (
        (datetime.date(year, 1, 1), "元旦"),
        (datetime.date(year, 2, 28), "和平"),
        (datetime.date(year, 4, 4), "兒童"),
        (_qingming(year), "清明"),
        (datetime.date(year, 5, 1), "勞動"),
        (datetime.date(year, 9, 28), "教師"),
        (datetime.date(year, 10, 10), "國慶"),
        (datetime.date(year, 10, 25), "光復"),
        (datetime.date(year, 12, 25), "行憲"),
    )
    for day, name in fixed:
        spans.append(_expand(day, name))
    if year == 2026:
        # 行政院核定的 115 年春節連假（2/14–2/22）。端午、中秋由上面的規則展開。
        spans.append((datetime.date(2026, 2, 14), datetime.date(2026, 2, 22), "春節"))
        spans.append(_expand(datetime.date(2026, 6, 19), "端午"))
        spans.append(_expand(datetime.date(2026, 9, 25), "中秋"))
    return _merge(spans)


def _merge(spans):
    ordered = sorted(spans, key=lambda item: (item[0], item[1]))
    merged = []
    for start, end, name in ordered:
        if merged and start <= merged[-1][1] + datetime.timedelta(days=1):
            merged[-1][1] = max(merged[-1][1], end)
            merged[-1][2].append(name)
        else:
            merged.append([start, end, [name]])
    out = []
    for start, end, names in merged:
        picked = names[0]
        for name in _NAME_RANK:
            if name in names:
                picked = name
                break
        out.append((start, end, picked))
    return out


def _bit(day):
    return f"{day.month}/{day.day}({WEEKDAY[day.weekday()]})"


def span_label(start, end, name=""):
    """按鈕還要加「✓ 」，所以有名稱時整段最多 18 個字。"""
    core = _bit(start) if start == end else f"{_bit(start)}-{_bit(end)}"
    if name and len(core) + len(name) <= 18:
        return core + name
    if name and start != end and start.month == end.month:
        compact = f"{_bit(start)}-{end.day}({WEEKDAY[end.weekday()]})"
        if len(compact) + len(name) <= 18:
            return compact + name
    return core


def _saturdays(year, month):
    day = datetime.date(year, month, 1)
    day += datetime.timedelta(days=(5 - day.weekday()) % 7)
    found = []
    while day.month == month and day.year == year:
        found.append(day)
        day += datetime.timedelta(days=7)
    return found


def _month_bounds(year, month):
    first = datetime.date(year, month, 1)
    if month == 12:
        last = datetime.date(year, 12, 31)
    else:
        last = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
    return first, last


def next_month_labels(today=None):
    """下一個月每個週六週日，以及該月碰到的國定假日連假。"""
    today = taipei_today(today)
    year, month = next_month(today)
    first, last = _month_bounds(year, month)
    covered = set()
    labeled = []
    for start, end, name in _holidays(year) + _holidays(year + 1) + _holidays(year - 1):
        if end < first or start > last:
            continue
        labeled.append((start, span_label(start, end, name)))
        day = start
        while day <= end:
            if day.weekday() == 5 and day.year == year and day.month == month:
                covered.add(day)
            day += datetime.timedelta(days=1)
    for saturday in _saturdays(year, month):
        if saturday in covered:
            continue
        sunday = saturday + datetime.timedelta(days=1)
        labeled.append((saturday, span_label(saturday, sunday)))
    labeled.sort(key=lambda item: item[0])
    seen = set()
    out = []
    for _start, label in labeled:
        if label not in seen:
            seen.add(label)
            out.append(label)
    return out


def choice_labels(state, cat, today=None):
    if cat == "date":
        labels = list(next_month_labels(today))
        for label in (state or {}).get("candidates") or []:
            if label not in labels:
                labels.append(label)
        return labels
    return list(CHOICES[cat])


def pick_rows(state, cat, labels):
    rows = []
    members = (state or {}).get("members") or {}
    for label in labels:
        names = []
        for member in members.values():
            chosen = ((member.get("picks") or {}).get(cat) or [])
            if label in chosen:
                names.append(member.get("name") or "某人")
        rows.append({"label": label, "count": len(names), "names": names})
    return rows


def tops(rows):
    top = max((row["count"] for row in rows), default=0)
    return [row for row in rows if top and row["count"] == top]
