import random

ALIASES = {"剪刀": "剪刀", "✌️": "剪刀", "石頭": "石頭", "✊": "石頭", "布": "布", "✋": "布"}
EMOJI = {"剪刀": "✌️", "石頭": "✊", "布": "✋"}
BEATS = {"剪刀": "布", "石頭": "剪刀", "布": "石頭"}


def handle(args, user_id="", rng=random):
    if not args or args[0] not in ALIASES:
        return "請出拳啦：猜拳 剪刀 / 猜拳 石頭 / 猜拳 布"
    me = ALIASES[args[0]]
    bot = rng.choice(list(BEATS))
    if me == bot:
        result = "平手啦！再來一局？"
    elif BEATS[me] == bot:
        result = "你贏了耶！🎉"
    else:
        result = "你輸了咧～哈哈 😜"
    return f"你出 {EMOJI[me]}{me}，我出 {EMOJI[bot]}{bot}\n{result}"
