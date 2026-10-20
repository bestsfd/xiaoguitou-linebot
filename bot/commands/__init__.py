"""指令註冊表：新增指令＝新增一個模組並在 REGISTRY 登記關鍵字。
REGISTRY: 娛樂指令 handler(args, user_id) -> str
CAMP_REGISTRY: 露營指令 handler(args, ctx) -> str | None（需要聊天室狀態）"""
from . import dice, fortune_stick, daily_luck, food, rps, help as help_cmd
from ..camp.logic import CAMP_REGISTRY, Ctx

REGISTRY = {
    "擲骰子": dice.handle, "骰子": dice.handle,
    "抽籤": fortune_stick.handle,
    "今日運勢": daily_luck.handle,
    "吃什麼": food.handle,
    "猜拳": rps.handle,
    "幫助": help_cmd.handle, "指令": help_cmd.handle,
}


def dispatch(text: str, user_id: str = "", ctx: "Ctx | None" = None):
    """回傳回覆字串；非指令回傳 None。"""
    parts = text.strip().split()
    if not parts:
        return None
    key, args = parts[0], parts[1:]
    if key in REGISTRY:
        return REGISTRY[key](args, user_id)
    if key in CAMP_REGISTRY:
        ctx = ctx or Ctx(chat_id=user_id, user_id=user_id)
        return CAMP_REGISTRY[key](args, ctx)
    return None
