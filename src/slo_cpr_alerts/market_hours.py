from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
OPEN = time(9, 15)
CLOSE = time(15, 30)


def now_ist() -> datetime:
    return datetime.now(IST)


def is_market_open(value: datetime | None = None) -> bool:
    current = (value or now_ist()).astimezone(IST).time()
    return OPEN <= current < CLOSE
