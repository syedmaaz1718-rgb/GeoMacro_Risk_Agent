"""Telegram delivery with 3 attempts (spec sections 10 and 23)."""
import logging
import time

import httpx

from ..config import cfg, env

log = logging.getLogger("geomacro.alerts")


def telegram_ready():
    return cfg()["alerts"]["telegram_enabled"] and bool(env("TELEGRAM_BOT_TOKEN")) and bool(env("TELEGRAM_CHAT_ID"))


def deliver(text, attempts=3, wait=2.0):
    """Returns (status, sent_to). Tries up to 3 times, then the alert is stored as 'failed' (spec section 23)."""
    if not telegram_ready():
        return "logged", "dashboard"
    chat = env("TELEGRAM_CHAT_ID")
    for i in range(1, attempts + 1):
        try:
            r = httpx.post(f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/sendMessage",
                           json={"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True}, timeout=20)
            r.raise_for_status()
            return "sent", f"telegram:{chat}"
        except Exception as e:  # noqa: BLE001
            log.warning("telegram send failed (attempt %d/%d): %s", i, attempts, str(e).replace(env("TELEGRAM_BOT_TOKEN"), "***"))
            if i < attempts:
                time.sleep(wait * i)
    return "failed", f"telegram:{chat}"
