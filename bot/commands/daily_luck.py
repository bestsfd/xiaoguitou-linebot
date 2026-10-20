import datetime
import hashlib
import random

TZ = datetime.timezone(datetime.timedelta(hours=8))
LEVELS = ["大吉", "中吉", "小吉", "吉", "末吉", "凶", "大凶"]
COLORS = ["紅色", "橙色", "黃色", "綠色", "藍色", "紫色", "白色", "黑色", "粉紅色"]
GOOD = ["告白", "喝珍奶", "打電動", "運動", "加班", "買樂透", "睡午覺", "整理房間"]
BAD = ["熬夜", "吵架", "網購", "吃宵夜", "賴床", "借錢給朋友", "立 flag"]


def handle(args, user_id="", today=None):
    today = today or datetime.datetime.now(TZ).date()
    seed = hashlib.sha256(f"{user_id}|{today.isoformat()}".encode()).hexdigest()
    r = random.Random(seed)
    good, bad = r.sample(GOOD, 1)[0], r.sample(BAD, 1)[0]
    return (f"🔮 {today:%m/%d} 今日運勢：{r.choice(LEVELS)}\n"
            f"幸運數字：{r.randint(0, 99)}\n幸運色：{r.choice(COLORS)}\n"
            f"宜：{good}　忌：{bad}")
