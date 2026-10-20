# LINE 娛樂機器人

以 FastAPI + line-bot-sdk v3 打造，支援一對一與群組聊天。

## 指令
| 指令 | 說明 |
|---|---|
| 擲骰子 / 骰子 [顆數] | 擲 1～10 顆骰子，例：`擲骰子 3` |
| 抽籤 | 隨機籤詩（大吉～大凶） |
| 今日運勢 | 每人每天固定的運勢 |
| 吃什麼 [選項…] | 隨機台灣美食，或從給定選項中挑一個 |
| 猜拳 剪刀/石頭/布 | 和機器人猜拳 |
| 幫助 / 指令 | 顯示指令列表 |

群組中非指令訊息一律不回覆；一對一聊天會提示輸入「幫助」。

## 啟動
```bash
export LINE_CHANNEL_SECRET=你的Channel_secret
export LINE_CHANNEL_ACCESS_TOKEN=你的Channel_access_token
./run.sh
```
畫面會印出 `https://xxxx.trycloudflare.com`，Webhook URL 為 `<網址>/callback`。
注意：quick tunnel 每次重啟網址都會變，需要重新到 LINE Developers 更新 Webhook URL。

## 測試
```bash
.venv/bin/pytest -q
```

## 新增指令
1. 在 `bot/commands/` 新增模組，實作 `handle(args, user_id="") -> str`。
2. 在 `bot/commands/__init__.py` 的 `REGISTRY` 登記關鍵字。
3. 記得更新 `help.py` 的說明。

## LINE Developers 設定
1. 到 https://developers.line.biz/console/ 建立 Provider → 建立 Messaging API channel。
2. Basic settings → 複製 **Channel secret**。
3. Messaging API 分頁 → **Channel access token (long-lived)** → Issue 並複製。
4. 執行 `./run.sh`，將 `<網址>/callback` 填入 **Webhook URL** → Verify。
5. 開啟 **Use webhook**。
6. **Auto-reply messages** 點 Edit（LINE Official Account Manager）→ 關閉自動回應與歡迎訊息（可選）。
7. **Allow bot to join group chats** → Edit → 啟用。
8. 用 QR code 加機器人好友，再邀進群組。

## 🏕️ 露營規劃（每個群組一份，存在 `data/camp.db`）
| 指令 | 說明 |
|---|---|
| 露營開團 [名稱] ／ 露營取消 | 開團（每群組同時一團）／關閉 |
| 候選日期 10/31-11/1, 11/7-11/8 | 主揪設定候選日期（自動編號） |
| 可以 1 3 ／ 投票 1 3 | 投可出席日期（覆蓋上次，並視為參加） |
| 參加 [+N] ／ 不參加 ／ 人數 | 出席與攜伴 |
| 預算 3000 | 個人每人預算（台幣） |
| 地區 台中 ／ 需求 可帶狗 | 偏好地區、需求清單 |
| 露營統計 | 各日期票數與名單、最佳日期、人數、預算（建議＝最低者） |
| 找木屋 | 將條件寫到 `data/requests/<群組id>-<時間>.json` |
| 已選 2 | 投木屋候選 |
| 確定訂 [編號] | 記錄決定，由主揪翔暉確認訂房（機器人不訂房、不付款） |

貼木屋候選到群組：
```bash
.venv/bin/python post_options.py <群組id> options.json        # push_message
.venv/bin/python post_options.py <群組id> options.json --dry-run
```
`options.json` 格式：`[{"name":"…","price":"…","link":"…","note":"…"}]`
