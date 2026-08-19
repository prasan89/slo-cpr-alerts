from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from growwapi import GrowwAPI


@dataclass(frozen=True)
class OHLC:
    high: float
    low: float
    close: float


class GrowwDataProvider:
    """Read-only Groww adapter for CPR monitoring.

    No order APIs are used. The adapter uses Groww historical candles for
    previous-session levels and the live LTP API for current prices.
    """

    def __init__(self, access_token: str, symbols: list[str]) -> None:
        if not access_token:
            raise ValueError("Groww access token is required")
        self.client = GrowwAPI(access_token)
        self._symbols = tuple(dict.fromkeys(symbols))

    def symbols(self) -> list[str]:
        return list(self._symbols)

    @staticmethod
    def _session_bounds(session_date: date) -> tuple[str, str]:
        start = datetime.combine(session_date, time(9, 15))
        end = datetime.combine(session_date, time(15, 30))
        return start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")

    def _daily_ohlc(self, symbol: str, session_date: date) -> OHLC | None:
        start, end = self._session_bounds(session_date)
        response = self.client.get_historical_candles(
            exchange=self.client.EXCHANGE_NSE,
            segment=self.client.SEGMENT_CASH,
            groww_symbol=f"NSE-{symbol}",
            start_time=start,
            end_time=end,
            candle_interval=self.client.CANDLE_INTERVAL_MIN_5,
        )
        candles = response.get("candles", [])
        if not candles:
            return None
        highs = [float(c[2]) for c in candles]
        lows = [float(c[3]) for c in candles]
        close = float(candles[-1][4])
        return OHLC(max(highs), min(lows), close)

    def previous_ohlc(self, symbol: str, session_date: date) -> OHLC | None:
        return self._daily_ohlc(symbol, session_date)

    def previous_trading_ohlc(self, symbol: str, before_date: date) -> OHLC | None:
        # The provider is intentionally conservative: walk back until a
        # session with candles exists, covering weekends and exchange holidays.
        candidate = before_date - timedelta(days=1)
        for _ in range(10):
            result = self._daily_ohlc(symbol, candidate)
            if result is not None:
                return result
            candidate -= timedelta(days=1)
        return None

    def ltp(self, symbol: str) -> float:
        response = self.client.get_ltp(
            segment=self.client.SEGMENT_CASH,
            exchange_trading_symbols=(f"NSE_{symbol}",),
        )
        values = response.get("ltp", response)
        if isinstance(values, dict):
            value = values.get(f"NSE_{symbol}")
            if value is None:
                value = values.get("ltp")
        else:
            value = values
        return float(value)
