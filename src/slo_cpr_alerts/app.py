from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from pathlib import Path

from slo_cpr_alerts.cpr import calculate_cpr, classify_price, crossing_alert
from slo_cpr_alerts.excel import create_workbook, append_snapshot
from slo_cpr_alerts.market_hours import is_market_open, now_ist


class DataProvider:
    """Interface placeholder for Upstox/FYERS/Groww adapters."""

    def symbols(self) -> list[str]:
        raise NotImplementedError

    def previous_ohlc(self, symbol: str, session_date: date):
        raise NotImplementedError

    def ltp(self, symbol: str) -> float:
        raise NotImplementedError


class CPRMonitor:
    def __init__(self, provider: DataProvider, workbook: str | Path = "reports/cpr_alerts.xlsx") -> None:
        self.provider = provider
        self.workbook = Path(workbook)
        # Keep the last observed price so alerts mean an actual crossing,
        # rather than merely being above R1/below S1 on every 5-minute poll.
        self.previous_prices: dict[str, float] = {}
        create_workbook(self.workbook)

    def check_once(self) -> int:
        now = now_ist()
        if not is_market_open(now):
            return 0

        session_date = now.date()
        previous_session = session_date - timedelta(days=1)
        count = 0
        for symbol in self.provider.symbols():
            ohlc = self.provider.previous_ohlc(symbol, previous_session)
            if not ohlc:
                continue
            price = self.provider.ltp(symbol)
            if price <= 0:
                continue

            cpr = calculate_cpr(ohlc.high, ohlc.low, ohlc.close)
            previous_price = self.previous_prices.get(symbol)
            state = classify_price(price, cpr)
            alert = crossing_alert(previous_price, price, cpr)
            self.previous_prices[symbol] = price

            width_pct = ((cpr.tc - cpr.bc) / cpr.pivot * 100.0) if cpr.pivot else 0.0
            append_snapshot(
                self.workbook,
                {
                    "timestamp_ist": now.isoformat(),
                    "symbol": symbol,
                    "ltp": price,
                    "r3": cpr.r3,
                    "r2": cpr.r2,
                    "r1": cpr.r1,
                    "tc": cpr.tc,
                    "pivot": cpr.pivot,
                    "bc": cpr.bc,
                    "s1": cpr.s1,
                    "s2": cpr.s2,
                    "s3": cpr.s3,
                    "cpr_width_pct": width_pct,
                    "state": state,
                    "alert": alert,
                    "previous_ltp": previous_price or "",
                },
            )
            if alert:
                print(f"[{now.isoformat()}] {symbol}: {alert} LTP={price:.2f}")
            count += 1
        return count

    def run_forever(self, interval_seconds: int = 300) -> None:
        while True:
            try:
                self.check_once()
            except Exception as exc:
                print(f"CPR monitor error: {type(exc).__name__}: {exc}")
            time.sleep(interval_seconds)


def main() -> None:
    raise SystemExit(
        "Connect a real read-only DataProvider adapter before running. "
        "The monitor will poll every 5 minutes and alert only on upward R1 or downward S1 crossings."
    )
