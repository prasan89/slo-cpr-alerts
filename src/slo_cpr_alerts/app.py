from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from pathlib import Path

from slo_cpr_alerts.cpr import calculate_cpr, classify_price
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
        self.previous_states: dict[str, str] = {}
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
            state = classify_price(price, cpr)
            previous = self.previous_states.get(symbol)
            alert = ""
            if previous and state != previous:
                if state == "ABOVE_TC":
                    alert = "BREAKOUT_ABOVE_TC"
                elif state == "BELOW_BC":
                    alert = "BREAKDOWN_BELOW_BC"
                elif state == "INSIDE_CPR":
                    alert = "RE_ENTRY_CPR"
            self.previous_states[symbol] = state
            width_pct = ((cpr.tc - cpr.bc) / cpr.pivot * 100.0) if cpr.pivot else 0.0
            append_snapshot(
                self.workbook,
                {
                    "timestamp_ist": now.isoformat(),
                    "symbol": symbol,
                    "ltp": price,
                    "pivot": cpr.pivot,
                    "bc": cpr.bc,
                    "tc": cpr.tc,
                    "cpr_width_pct": width_pct,
                    "state": state,
                    "alert": alert,
                    "previous_state": previous or "",
                },
            )
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
        "The CPR calculation, market window and Excel alert layers are ready."
    )
