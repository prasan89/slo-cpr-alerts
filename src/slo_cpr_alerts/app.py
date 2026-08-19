from __future__ import annotations

import os
import time
from datetime import date, timedelta
from pathlib import Path

from slo_cpr_alerts.cpr import calculate_cpr, classify_price, crossing_alert
from slo_cpr_alerts.excel import create_workbook, append_snapshot
from slo_cpr_alerts.market_hours import is_market_open, now_ist
from slo_cpr_alerts.providers.fyers import FyersDataProvider


class DataProvider:
    """Interface for read-only market-data adapters."""

    def symbols(self) -> list[str]:
        raise NotImplementedError

    def previous_ohlc(self, symbol: str, session_date: date):
        raise NotImplementedError

    def previous_trading_ohlc(self, symbol: str, before_date: date):
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
        count = 0

        for symbol in self.provider.symbols():
            # Latest completed trading session becomes today's CPR reference.
            current_ohlc = self.provider.previous_trading_ohlc(symbol, session_date)
            if not current_ohlc:
                continue

            # The adapter walks backwards across weekends/holidays.
            current_reference_date = session_date - timedelta(days=1)
            prior_ohlc = self.provider.previous_trading_ohlc(symbol, current_reference_date)
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


def _symbols() -> list[str]:
    raw = os.getenv("SLO_SYMBOLS", "NIFTY,BANKNIFTY").strip()
    return [item.strip() for item in raw.split(",") if item.strip()]


def main() -> None:
    provider_name = os.getenv("SLO_DATA_PROVIDER", "fyers").lower()
    symbols = _symbols()

    if provider_name != "fyers":
        raise SystemExit("Current CLI default is FYERS. Set SLO_DATA_PROVIDER=fyers.")

    app_id = os.getenv("FYERS_APP_ID")
    access_token = os.getenv("FYERS_ACCESS_TOKEN")
    if not app_id or not access_token:
        raise SystemExit(
            "Missing FYERS_APP_ID or FYERS_ACCESS_TOKEN. "
            "Run `fyers-auth` to generate a token locally."
        )

    provider = FyersDataProvider(app_id, access_token, symbols)
    monitor = CPRMonitor(provider)
    print(f"FYERS CPR monitor started for {len(symbols)} symbols; interval=300s")
    monitor.run_forever(interval_seconds=300)
