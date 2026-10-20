import datetime
import random

from bot.commands import dispatch, REGISTRY
from bot.commands import dice, fortune_stick, daily_luck, food, rps


def test_dice_single_and_multi():
    assert "你擲出了" in dice.handle([])
    out = dice.handle(["3"], rng=random.Random(1))
    assert "3 顆" in out and "合計" in out
    assert "介於" in dice.handle(["0"]) and "介於" in dice.handle(["99"])
    assert "請輸入數字" in dice.handle(["abc"])


def test_fortune():
    out = fortune_stick.handle([])
    assert any(f"【{k}】" in out for k in fortune_stick.WEIGHTS)


def test_daily_luck_deterministic():
    d = datetime.date(2026, 10, 20)
    assert daily_luck.handle([], "U1", today=d) == daily_luck.handle([], "U1", today=d)
    outs = {daily_luck.handle([], f"U{i}", today=d) for i in range(20)}
    assert len(outs) > 1


def test_food():
    assert food.handle([]).count("「") == 1
    out = food.handle(["A", "B"])
    assert "「A」" in out or "「B」" in out


def test_rps():
    assert "請出拳" in rps.handle([])
    out = rps.handle(["石頭"])
    assert any(k in out for k in ["平手", "贏", "輸"])


def test_dispatch():
    assert dispatch("哈囉") is None
    assert "可用指令" in dispatch("幫助") and "可用指令" in dispatch("指令")
    assert "骰子" in dispatch("骰子 2")
    assert set(REGISTRY) >= {"擲骰子", "骰子", "抽籤", "今日運勢", "吃什麼", "猜拳", "幫助", "指令"}
