from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .providers.fyers import FyersDataProvider, OHLC, VolumeSnapshot

IST = ZoneInfo("Asia/Kolkata")

@dataclass(frozen=True)
class JFTLevels:
    open: float
    adr5: float
    adr10: float
    r1: float
    r2: float
    s1: float
    s2: float


def calculate_jft(today_open: float, ranges: list[float]) -> JFTLevels:
    if today_open <= 0 or len(ranges) < 10:
        raise ValueError("JFT requires today's open and at least 10 prior daily ranges")
    adr5 = sum(ranges[:5]) / 5.0
    adr10 = sum(ranges[:10]) / 10.0
    # JFT/DZones: inner boundary uses ADR10/2, outer boundary uses ADR5/2.
    r1 = today_open + adr10 / 2.0
    r2 = today_open + adr5 / 2.0
    s1 = today_open - adr10 / 2.0
    s2 = today_open - adr5 / 2.0
    return JFTLevels(today_open, adr5, adr10, r1, r2, s1, s2)


def jft_signal(cmp: float, levels: JFTLevels, volume_ratio: float, min_volume_ratio: float = 1.2) -> str:
    if volume_ratio < min_volume_ratio:
        return ""
    if cmp > levels.r2:
        return "BUY CALL"
    if cmp < levels.s2:
        return "SELL"
    return ""


def _daily_ranges(provider: FyersDataProvider, symbol: str, before_date: date) -> list[float]:
    sessions = provider.previous_sessions(symbol, before_date, count=10)
    if len(sessions) < 10:
        return []
    return [ohlc.high - ohlc.low for _, ohlc in sessions[:10]]


def build_levels(provider: FyersDataProvider, symbol: str, trading_date: date) -> JFTLevels | None:
    # Use today's opening price from the first completed/current 5m candle.
    # The prior 10 completed trading sessions supply ADR5/ADR10.
    now = datetime.now(IST)
    if trading_date == now.date():
        start = now.replace(hour=9, minute=15, second=0, microsecond=0)
        response = provider.client.history(data={
            "symbol": provider._fyers_symbol(symbol), "resolution": "5", "date_format": "0",
            "range_from": int(start.timestamp()), "range_to": int(now.timestamp()), "cont_flag": "1"
        })
        candles = response.get("candles", []) if isinstance(response, dict) and response.get("s") == "ok" else []
        if not candles:
            return None
        today_open = float(candles[0][1])
    else:
        return None
    ranges = _daily_ranges(provider, symbol, trading_date)
    return calculate_jft(today_open, ranges) if len(ranges) >= 10 else None


class JFTScanner:
    """Five-minute all-symbol JFT R2/S2 + volume scanner."""
    def __init__(self, provider: FyersDataProvider, min_volume_ratio: float = 1.2):
        self.provider = provider
        self.min_volume_ratio = min_volume_ratio
        self.levels: dict[str, JFTLevels] = {}
        self.signaled: set[tuple[str, str]] = set()
        self.levels_date: date | None = None

    def initialize(self, trading_date: date | None = None) -> int:
        trading_date = trading_date or datetime.now(IST).date()
        self.levels.clear(); self.signaled.clear(); count = 0
        for symbol in self.provider.symbols():
            try:
                level = build_levels(self.provider, symbol, trading_date)
                if level:
                    self.levels[symbol] = level; count += 1
            except Exception as exc:
                print(f"[JFT ERROR] {symbol}: {exc}")
        self.levels_date = trading_date
        print(f"JFT levels initialized: {count}/{len(self.provider.symbols())}")
        return count

    def scan_once(self) -> list[dict]:
        now = datetime.now(IST)
        if self.levels_date != now.date() or not self.levels:
            self.initialize(now.date())
        alerts = []
        for symbol, levels in self.levels.items():
            try:
                cmp = self.provider.ltp(symbol)
                volume = self.provider.volume_snapshot(symbol)
                ratio = volume.ratio if volume else 0.0
                signal = jft_signal(cmp, levels, ratio, self.min_volume_ratio)
                if not signal or (symbol, signal) in self.signaled:
                    continue
                self.signaled.add((symbol, signal))
                alerts.append({"symbol": symbol, "signal": signal, "cmp": cmp, "r1": levels.r1, "r2": levels.r2, "s1": levels.s1, "s2": levels.s2, "volume_ratio": ratio, "time": now.isoformat()})
            except Exception as exc:
                print(f"[JFT ERROR] {symbol}: {exc}")
        for a in alerts:
            print(f"🚨 JFT {a['signal']} {a['symbol']} | CMP={a['cmp']:.2f} R2={a['r2']:.2f} S2={a['s2']:.2f} volume={a['volume_ratio']:.2f}x")
        return alerts

    def run_forever(self) -> None:
        import time
        while True:
            now = datetime.now(IST)
            if now.time().hour < 9 or (now.time().hour == 9 and now.time().minute < 15):
                time.sleep(30); continue
            if now.time().hour > 15 or (now.time().hour == 15 and now.time().minute >= 31):
                return
            self.scan_once()
            next_minute = ((now.minute // 5) + 1) * 5
            target = now.replace(second=0, microsecond=0)
            if next_minute >= 60:
                target = target.replace(minute=0) + timedelta(hours=1)
            else:
                target = target.replace(minute=next_minute)
            time.sleep(max(1, (target - datetime.now(IST)).total_seconds()))
