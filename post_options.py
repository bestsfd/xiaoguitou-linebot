#!/usr/bin/env python3
"""把木屋候選貼到群組：
  python post_options.py <groupid> options.json [--dry-run]
options.json：[{"name":..., "price":..., "link":..., "note":...}, ...]
需要環境變數 LINE_CHANNEL_ACCESS_TOKEN（--dry-run 不需要）。"""
import json
import sys

from bot import line_api
from bot.camp.logic import set_options
from bot.camp.store import Store


def main(argv, store=None, push=None):
    if len(argv) < 2:
        print(__doc__)
        return 2
    chat_id, path = argv[0], argv[1]
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    options = data["options"] if isinstance(data, dict) else data
    text = set_options(store or Store(), chat_id, options)
    if "--dry-run" in argv:
        print(text)
    else:
        (push or line_api.push)(chat_id, text)
        print("已推送到", chat_id)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
