from __future__ import annotations

import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def send_signal(message: str) -> None:
    """Send a CPR signal to Telegram when configured; otherwise do nothing."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return

    payload = urlencode({"chat_id": chat_id, "text": message}).encode()
    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlopen(request, timeout=10) as response:
        if response.status >= 300:
            raise RuntimeError(f"Telegram send failed with HTTP {response.status}")


def format_signals(timestamp: str, calls: list[str], puts: list[str]) -> str:
    return (
        f"🚨 {timestamp} IST — CPR SIGNALS\n\n"
        f"🟢 CALL: {', '.join(calls) if calls else 'None'}\n"
        f"🔴 PUT: {', '.join(puts) if puts else 'None'}"
    )
