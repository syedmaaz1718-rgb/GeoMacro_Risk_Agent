"""Find your Telegram chat id: send any message to your bot first, then run
   python scripts/telegram_chat_id.py   (reads TELEGRAM_BOT_TOKEN from the environment or .env)"""
import os, sys
import httpx

token = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not token and os.path.exists(".env"):
    for line in open(".env", encoding="utf-8"):
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            token = line.split("=", 1)[1].strip()
if not token:
    sys.exit("Set TELEGRAM_BOT_TOKEN first (env var or .env file).")
r = httpx.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20).json()
chats = {}
for u in r.get("result", []):
    m = u.get("message") or u.get("channel_post") or {}
    c = m.get("chat")
    if c:
        chats[c["id"]] = c.get("first_name") or c.get("title") or ""
if not chats:
    sys.exit("No messages found. Open your bot in Telegram, press Start, send 'hi', then run this again.")
for cid, name in chats.items():
    print(f"TELEGRAM_CHAT_ID={cid}   ({name})")
