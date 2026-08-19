from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fyers_apiv3 import fyersModel


IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class OHLC:
    high: float
    low: float
    close: float


class FyersDataProvider:
    """Read-only FYERS v3 market-data adapter for CPR monitoring."""

    def __init__(self, app_id: str, access_token: str, symbols: list[str]) -> None:
        if not app_id or not access_token:
            raise ValueError("FYERS app ID and access token are required")
        self._symbols = tuple(dict.fromkeys(symbols))
        self.client = fyersModel.FyersModel(
            client_id=app_id,
            token=access_token,
            is_async=False,
            log_path="",
        )

    def symbols(self) -> list[str]:
        return list(self._symbols)

    @staticmethod
    def _fyers_symbol(symbol: str) -> str:
        if symbol.startswith("NSE:"):
            return symbol
        if symbol in {"NIFTY", "NIFTY50"}:
            return "NSE:NIFTY50-INDEX"
        if symbol in {"BANKNIFTY", "NIFTYBANK"}:
            return "NSE:NIFTYBANK-INDEX"
        return f"NSE:{symbol}-EQ"

    @staticmethod
    def _epoch_seconds(value: datetime) -> int:
        return int(value.timestamp())

    def _history(self, symbol: str, session_date: date) -> OHLC | None:
        start = datetime(session_date.year, session_date.month, session_date.day, 9, 15, tzinfo=IST)
        end = datetime(session_date.year, session_date.month, session_date.day, 15, 30, tzinfo=IST)
        response = self.client.history(
            data={
                "symbol": self._fyers_symbol(symbol),
                "resolution": "5",
                "date_format": "0",
                "range_from": self._epoch_seconds(start),
                "range_to": self._epoch_seconds(end),
                "cont_flag": "1",
            }
        )
        if not isinstance(response, dict) or response.get("s") != "ok":
            return None
        candles = response.get("candles") or []
        if not candles:
            return None
        highs = [float(c[2]) for c in candles]
        lows = [float(c[3]) for c in candles]
        close = float(candles[-1][4])
        return OHLC(high=max(highs), low=min(lows), close=close)

    def previous_sessions(self, symbol: str, before_date: date, count: int = 2) -> list[tuple[date, OHLC]]:
        """Return the most recent completed sessions before a date, newest first."""
        sessions: list[tuple[date, OHLC]] = []
        candidate = before_date - timedelta(days=1)
        for _ in range(15):
            result = self._history(symbol, candidate)
            if result is not None:
                sessions.append((candidate, result))
                if len(sessions) >= count:
                    break
            candidate -= timedelta(days=1)
        return sessions

    def previous_ohlc(self, symbol: str, session_date: date) -> OHLC | None:
        sessions = self.previous_sessions(symbol, session_date + timedelta(days=1), count=1)
        return sessions[0][1] if sessions else None

    def previous_trading_ohlc(self, symbol: str, before_date: date) -> OHLC | None:
        sessions = self.previous_sessions(symbol, before_date, count=1)
        return sessions[0][1] if sessions else None

    def ltp(self, symbol: str) -> float:
        response = self.client.quotes(data={"symbols": self._fyers_symbol(symbol)})
        if not isinstance(response, dict) or response.get("s") != "ok":
            raise RuntimeError(f"FYERS quotes failed for {symbol}: {response}")
        d = response.get("d") or []
        if not d:
            raise RuntimeError(f"FYERS returned no quote for {symbol}")
        values: Any = d[0].get("v", {})
        value = values.get("lp")
        if value is None:
            raise RuntimeError(f"FYERS quote has no LTP for {symbol}: {response}")
        return float(value)

    def profile(self) -> dict[str, Any]:
        response = self.client.get_profile()
        if not isinstance(response, dict):
            raise RuntimeError(f"Unexpected FYERS profile response: {response}")
        return response
