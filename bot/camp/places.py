"""台中到台北之間的親子木屋與附近景點。只列有官方或訂房頁、且內文核對過的地點。"""

# 網址皆於 2026-10 核對過頁面內容。房價只寫頁面上有的數字。
ATTRACTIONS = {
    "guanwu": {
        "name": "觀霧國家森林遊樂區",
        "kind": "步道",
        "county": "新竹",
        "blurb": "新竹五峰與苗栗泰安交界。檜山巨木群步道、春季霧社山櫻，適合慢慢走。",
        "url": "https://www.forest.gov.tw/0000179",
    },
    "lala": {
        "name": "拉拉山國家森林遊樂區",
        "kind": "步道",
        "county": "桃園",
        "blurb": "桃園復興上巴陵。神木步道約 1 公里，檜木林，適合親子慢慢走。",
        "url": "https://recreation.forest.gov.tw/forest/RA?typ_id=0200005",
    },
    "dongyan": {
        "name": "東眼山國家森林遊樂區",
        "kind": "步道",
        "county": "桃園",
        "blurb": "桃園復興。柳杉林、親子峰步道，登頂可看桃園到台北。",
        "url": "https://www.forest.gov.tw/0000180",
    },
    "baxian": {
        "name": "八仙山國家森林遊樂區",
        "kind": "步道",
        "county": "台中",
        "blurb": "台中和平谷關。短途步道，十文溪親水區可坐着泡腳。",
        "url": "https://recreation.forest.gov.tw/Forest/RA?typ_id=0300002",
    },
    "wuling": {
        "name": "武陵國家森林遊樂區",
        "kind": "步道",
        "county": "台中",
        "blurb": "台中和平。桃山瀑布步道、七家灣溪，園區有台灣獼猴，請勿餵食。",
        "url": "https://www.forest.gov.tw/0000187",
    },
}

CABINS = (
    {
        "id": "woorao",
        "name": "蟬說：霧繞（好冬小屋）",
        "county": "新竹",
        "stays": ("木屋", "豪華露營"),
        "facilities": ("親子", "有雲海/山景", "獨立衛浴", "提供早餐"),
        "kid_facilities": "森林躲貓貓、孩童優惠；好冬小屋 2–4 人、獨立衛浴、一泊二食",
        "price": "一泊二食，官網未標固定房價",
        "price_min": None,
        "max_people": 4,
        "url": "https://www.chanshuo.tw/woorao/",
        "attractions": ("guanwu",),
    },
    {
        "id": "tianhu",
        "name": "愛上天湖露營區",
        "county": "新竹",
        "stays": ("木屋", "豪華露營"),
        "facilities": ("親子", "有雲海/山景"),
        "kid_facilities": "滑草、戲水、玩沙、大草皮、季節採果（孩童需家長陪同）",
        "price": "官網未標房價，請看官方頁",
        "price_min": None,
        "max_people": None,
        "url": "https://aishangtianhu.com/",
        "attractions": ("guanwu",),
    },
    {
        "id": "sheipa",
        "name": "雪霸休閒農場（花園木屋）",
        "county": "新竹",
        "stays": ("木屋",),
        "facilities": ("親子", "有雲海/山景", "獨立衛浴"),
        "kid_facilities": "花園木屋看雲海；旁邊是觀霧步道（巨木、櫻花），不是室內遊戲區",
        "price": "官網未標房價，訂房專線 (03)585-6192",
        "price_min": None,
        "max_people": None,
        "url": "https://www.sheipa.com.tw/",
        "attractions": ("guanwu",),
    },
    {
        "id": "fonen",
        "name": "鳳櫻山莊",
        "county": "苗栗",
        "stays": ("木屋",),
        "facilities": ("親子", "可烤肉", "溪邊", "有雲海/山景"),
        "kid_facilities": "全木作包棟約 10–12 人、戶外野炊，蓬萊溪邊可散步",
        "price": "官網未標房價，請看官方頁",
        "price_min": None,
        "max_people": 12,
        "url": "https://fonen.com.tw/",
        "attractions": ("guanwu",),
    },
    {
        "id": "daguan",
        "name": "拉拉山達觀農場",
        "county": "桃園",
        "stays": ("木屋",),
        "facilities": ("親子", "可烤肉", "有雲海/山景", "提供早餐"),
        "kid_facilities": "搗麻糬、甲蟲 DIY、採果、竹林步道",
        "price": "非假日二人房 2,100 元起，假日一泊二食八人房 10,400 元（皆含早餐）",
        "price_min": 2100,
        "max_people": None,
        "url": "https://www.dkhotel.com.tw/",
        "attractions": ("lala", "dongyan"),
    },
    {
        "id": "fuyam",
        "name": "福緣山莊",
        "county": "桃園",
        "stays": ("木屋",),
        "facilities": ("親子", "溪邊", "有雲海/山景"),
        "kid_facilities": "溪谷旁木屋（梨園、歐風、親水居），可順遊拉拉山神木步道",
        "price": "官網未標房價，請看官方頁",
        "price_min": None,
        "max_people": None,
        "url": "https://www.fu-yam.com.tw/",
        "attractions": ("lala", "dongyan"),
    },
    {
        "id": "yunzhuang",
        "name": "拉拉山雲莊",
        "county": "桃園",
        "stays": ("木屋",),
        "facilities": ("親子", "可烤肉", "有雲海/山景"),
        "kid_facilities": "獨棟木屋、烤肉區、森林步道，園內有蝴蝶與鍬形蟲",
        "price": "官網未標房價，請看官方頁",
        "price_min": None,
        "max_people": None,
        "url": "https://lalasun.tw/",
        "attractions": ("lala",),
    },
)

CORRIDOR = "台中～台北之間"
CORRIDOR_COUNTIES = {"新竹", "苗栗", "桃園", "台中"}
REGION_COUNTIES = {
    "北部": {"新竹", "桃園", "宜蘭"},
    "中部": {"苗栗", "台中", "南投"},
    "南部": {"嘉義", "屏東"},
    "東部": {"花蓮"},
    CORRIDOR: set(CORRIDOR_COUNTIES),
    "新竹": {"新竹"},
    "苗栗": {"苗栗"},
    "台中": {"台中"},
    "桃園": {"桃園"},
    "南投": {"南投"},
    "宜蘭": {"宜蘭"},
    "花蓮": {"花蓮"},
    "嘉義": {"嘉義"},
    "屏東": {"屏東"},
}


def cabin_by_id(cabin_id):
    for cabin in CABINS:
        if cabin["id"] == cabin_id:
            return cabin
    return None


def _counties_for(region_labels):
    counties = set()
    for label in region_labels or []:
        counties |= REGION_COUNTIES.get(label, set())
    return counties


def match_cabins(winners):
    """依贏的地區、房型、設施、預算、人數過濾。沒投地區就給整條走廊。"""
    winners = winners or {}
    counties = _counties_for(winners.get("regions") or [])
    stay = winners.get("stay")
    facilities = list(winners.get("facilities") or [])
    budget = winners.get("budget")
    headcount = winners.get("headcount") or 0
    found = []
    for cabin in CABINS:
        if counties and cabin["county"] not in counties:
            continue
        if stay and stay != "都可以" and stay not in cabin["stays"]:
            continue
        if facilities and not any(item in cabin["facilities"] for item in facilities):
            continue
        if budget is not None and cabin["price_min"] is not None and cabin["price_min"] > budget:
            continue
        if headcount and cabin["max_people"] and headcount > cabin["max_people"]:
            continue
        found.append(cabin)
    return found


def attraction_entries(keys):
    return [ATTRACTIONS[key] for key in keys if key in ATTRACTIONS]


def spots_for(winners, cabins):
    """贏的條件底下，每間木屋的附近景點；走廊或台中也帶上谷關、武陵。"""
    keys = []
    for cabin in cabins:
        for key in cabin["attractions"]:
            if key not in keys:
                keys.append(key)
    counties = _counties_for((winners or {}).get("regions") or [])
    if not cabins and not counties:
        return [(key, ATTRACTIONS[key]) for key in ATTRACTIONS]
    show_taichung = not counties or "台中" in counties or bool(counties & CORRIDOR_COUNTIES)
    if show_taichung:
        for key in ("baxian", "wuling"):
            if key not in keys:
                keys.append(key)
    return [(key, ATTRACTIONS[key]) for key in keys]


def brief():
    lines = []
    for cabin in CABINS:
        spots = "、".join(ATTRACTIONS[key]["name"] for key in cabin["attractions"])
        lines.append(
            f"{cabin['name']}（{cabin['county']}，{'/'.join(cabin['stays'])}）"
            f"{cabin['price']}。親子：{cabin['kid_facilities']}。附近：{spots}。網址：{cabin['url']}"
        )
    for key in ("baxian", "wuling"):
        spot = ATTRACTIONS[key]
        lines.append(f"景點 {spot['name']}（{spot['county']}{spot['kind']}）{spot['blurb']} 網址：{spot['url']}")
    return "\n".join(lines)
