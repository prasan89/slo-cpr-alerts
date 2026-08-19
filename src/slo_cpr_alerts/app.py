from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

from slo_cpr_alerts.cpr import calculate_cpr, classify_price, crossing_alert
from slo_cpr_alerts.excel import create_workbook, append_snapshot
from slo_cpr_alerts.market_hours import is_market_open, now_ist


class DataProvider:
    """Interface placeholder for Upstox/FYERS/Groww adapters."""

    def symbols(self) -> list[str]:
        raise NotImplementedError

    def previous_ohlc(self, symbol: str, session_date: date):
        """Return OHLC for the specified trading session, or None."""
        raise NotImplementedError

    def previous_trading_ohlc(self, symbol: str, before_date: date):
        """Return the most recent OHLC session strictly before before_date."""
        raise NotImplementedError

    def ltp(self, symbol: str) -> float:
        raise NotImplementedError


class CPRMonitor:
    def __init__(self, provider: DataProvider, workbook: str | Path = "reports/cpr_alerts.xlsx") -> None:
        self.provider = provider
        self.workbook = Path(workbook)
        self.previous_prices: dict[str, float] = {}
        create_workbook(self.workbook)

    def check_once(self) -> int:
        now = now_ist()
        if not is_market_open(now):
            return 0

        session_date = now.date()
        # Current levels come from the latest completed trading session.
        current_ohlc_date = session_date - timedelta(days=1)
        count = 0

        for symbol in self.provider.symbols():
            current_ohlc = self.provider.previous_ohlc(symbol, current_ohlc_date)
            if not current_ohlc:
                continue

            # Prior levels are calculated from the trading session immediately
            # before the session used for today's levels. This handles weekends
            # and exchange holidays through the provider implementation.
            prior_ohlc = self.provider.previous_trading_ohlc(symbol, current_ohlc_date)
            if not prior_ohlc:
                continue

            price = self.provider.ltp(symbol)
            if price <= 0:
                continue

            levels = calculate_cpr(current_ohlc.high, current_ohlc.low, current_ohlc.close)
            prior_levels = calculate_cpr(prior_ohlc.high, prior_ohlc.low, prior_ohlc.close)
            previous_price = self.previous_prices.get(symbol)
            state = classify_price(price, levels)
            alert = crossing_alert(previous_price, price, levels, prior_levels)
            self.previous_prices[symbol] = price

            width_pct = ((levels.tc - levels.bc) / levels.pivot * 100.0) if levels.pivot else 0.0
            append_snapshot(
                self.workbook,
                {
                    "timestamp_ist": now.isoformat(),
                    "symbol": symbol,
                    "ltp": price,
                    "r3": levels.r3,
                    "r2": levels.r2,
                    "r1": levels.r1,
                    "tc": levels.tc,
                    "pivot": levels.pivot,
                    "bc": levels.bc,
                    "s1": levels.s1,
                    "s2": levels.s2,
                    "s3": levels.s3,
                    "yesterday_r1": prior_levels.r1,
                    "yesterday_s1": prior_levels.s1,
                    "r1_improving": levels.r1 > prior_levels.r1,
                    "s1_improving": levels.s1 < prior_levels.s1,
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
        "The monitor polls every 5 minutes and alerts only when price crosses R1/S1 "
        "and today's level improves versus the prior trading day's level."
    )
