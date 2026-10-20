import random

FOODS = ["滷肉飯", "牛肉麵", "雞排", "蚵仔煎", "鹽酥雞", "臭豆腐", "小籠包", "鍋貼", "水餃",
         "便當", "麻辣鍋", "火鍋", "肉圓", "大腸包小腸", "割包", "蚵仔麵線", "炒飯", "鹹酥雞",
         "胡椒餅", "雞肉飯", "擔仔麵", "肉粽", "米糕", "鐵板燒", "拉麵", "咖哩飯", "排骨飯"]


def handle(args, user_id="", rng=random):
    if args:
        return f"🍽️ 在 {'、'.join(args)} 之中……就決定是「{rng.choice(args)}」！"
    return f"🍽️ 今天就吃「{rng.choice(FOODS)}」吧！"
