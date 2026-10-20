import random

FACES = "⚀⚁⚂⚃⚄⚅"
MAX_DICE = 10


def handle(args, user_id="", rng=random):
    n = 1
    if args:
        try:
            n = int(args[0])
        except ValueError:
            return "請輸入數字，例如：擲骰子 3"
    if not 1 <= n <= MAX_DICE:
        return f"骰子數量請介於 1 到 {MAX_DICE} 顆 🎲"
    rolls = [rng.randint(1, 6) for _ in range(n)]
    shown = " ".join(f"{FACES[r-1]}{r}" for r in rolls)
    if n == 1:
        return f"🎲 你擲出了：{shown}"
    return f"🎲 擲出 {n} 顆骰子：{shown}\n合計：{sum(rolls)} 點"
