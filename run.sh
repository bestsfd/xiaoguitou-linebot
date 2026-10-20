#!/usr/bin/env bash
# 啟動 LINE bot 並以 cloudflared quick tunnel 對外公開
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8000}"
: "${LINE_CHANNEL_SECRET:?請先設定環境變數 LINE_CHANNEL_SECRET}"
: "${LINE_CHANNEL_ACCESS_TOKEN:?請先設定環境變數 LINE_CHANNEL_ACCESS_TOKEN}"

[ -d .venv ] || { python3 -m venv .venv; .venv/bin/pip install -q -r requirements.txt; }

if ! command -v cloudflared >/dev/null; then
  echo "安裝 cloudflared..."
  ARCH=$(uname -m); case "$ARCH" in x86_64) A=amd64;; aarch64|arm64) A=arm64;; *) A=$ARCH;; esac
  mkdir -p "$HOME/.local/bin"
  curl -fsSL -o "$HOME/.local/bin/cloudflared" \
    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$A"
  chmod +x "$HOME/.local/bin/cloudflared"; export PATH="$HOME/.local/bin:$PATH"
fi

.venv/bin/uvicorn bot.app:app --host 127.0.0.1 --port "$PORT" > server.log 2>&1 &
SERVER_PID=$!
cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" > tunnel.log 2>&1 &
TUNNEL_PID=$!
trap 'kill $SERVER_PID $TUNNEL_PID 2>/dev/null' EXIT INT TERM

for _ in $(seq 1 60); do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' tunnel.log | head -1 || true)
  [ -n "$URL" ] && break; sleep 1
done
[ -n "${URL:-}" ] || { echo "取得 tunnel URL 失敗，請看 tunnel.log"; exit 1; }
echo "公開網址：$URL"
echo "Webhook URL：$URL/callback   （貼到 LINE Developers → Messaging API → Webhook URL）"
echo "按 Ctrl+C 停止。"
wait
