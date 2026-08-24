from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .providers.fyers import FyersDataProvider

IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class JFTLevels:
    open: float
    adr5: float
    adr10: float
    # Original JFT/DZones identities.
    h1: float   # DailyH1 = Open + ADR10/2
    h2: float   # DailyH2 = Open + ADR5/2
    l1: float   # DailyL1 = Open - ADR10/2
    l2: float   # DailyL2 = Open - ADR5/2
    # Positional trading names used by the scanner.
    r1: float   # lower of the two resistance boundaries
    r2: float   # higher of the two resistance boundaries
    s1: float   # higher of the two support boundaries
    s2: float   # lower of the two support boundaries


def calculate_jft(today_open: float, ranges: list[float]) -> JFTLevels:
    """Calculate the JFT/DZones daily boundaries.

    Exact JFT mathematics:

      ADR5  = average of the previous 5 daily High-Low ranges
      ADR10 = average of the previous 10 daily High-Low ranges

      DailyH1 = Open + ADR10/2
      DailyH2 = Open + ADR5/2
      DailyL1 = Open - ADR10/2
      DailyL2 = Open - ADR5/2

    The original H1/H2/L1/L2 identities are retained. For trading/scanning,
    R1/R2/S1/S2 are positional aliases so that the ordering is always:

      R2 > R1 > Open > S1 > S2

    ``ranges`` must be ordered newest-first: D-1 ... D-10.
    """
    if today_open <= 0 or len(ranges) < 10:
        raise ValueError("JFT requires today's daily open and 10 prior daily ranges")

    adr5 = sum(float(r) for r in ranges[:5]) / 5.0
    adr10 = sum(float(r) for r in ranges[:10]) / 10.0

    h1 = today_open + adr10 / 2.0
    h2 = today_open + adr5 / 2.0
    l1 = today_open - adr10 / 2.0
    l2 = today_open - adr5 / 2.0

    # R/S names are positional, not tied to ADR5/ADR10. This matters when
    # ADR10 is larger than ADR5 (or vice versa).
    r1 = min(h1, h2)
    r2 = max(h1, h2)
    s1 = max(l1, l2)
    s2 = min(l1, l2)

    return JFTLevels(
        open=today_open,
        adr5=adr5,
        adr10=adr10,
        h1=h1,
        h2=h2,
        l1=l1,
        l2=l2,
        r1=r1,
        r2=r2,
        s1=s1,
        s2=s2,
    )


def jft_signal(
    cmp: float,
    levels: JFTLevels,
    volume_ratio: float,
    min_volume_ratio: float = 1.2,
) -> str:
    """Return a JFT breakout signal only with volume confirmation."""
    if volume_ratio < min_volume_ratio:
        return ""
    if cmp > levels.r2:
        return "BUY CALL"
    if cmp < levels.s2:
        return "SELL"
    return ""


def build_levels(
    provider: FyersDataProvider,
    symbol: str,
    trading_date: date,
) -> JFTLevels | None:
    """Build JFT levels from FYERS daily OHLC.

    Today's actual daily OPEN is used together with the previous 10 completed
    daily High-Low ranges. Daily ranges are never reconstructed from 5-minute
    candles, which avoids intraday/session-boundary discrepancies.
    """
    bars = provider.daily_bars(symbol, trading_date, count=11)
    if len(bars) < 11:
        return None

    today = next((b for b in bars if b.session_date == trading_date), None)
    if today is None:
        return None

    previous = [b for b in bars if b.session_date < trading_date][:10]
    if len(previous) < 10:
        return None

    ranges = [b.high - b.low for b in previous]
    return calculate_jft(today.open, ranges)


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
        self.levels.clear()
        self.signaled.clear()
        count = 0
        symbols = self.provider.symbols()
        for symbol in symbols:
            try:
                level = build_levels(self.provider, symbol, trading_date)
                if level:
                    self.levels[symbol] = level
                    count += 1
            except Exception as exc:
                print(f"[JFT ERROR] {symbol}: {exc}")
        self.levels_date = trading_date
        print(f"JFT levels initialized: {count}/{len(symbols)}")
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
                alerts.append({
                    "symbol": symbol,
                    "signal": signal,
                    "cmp": cmp,
                    "open": levels.open,
                    "r1": levels.r1,
                    "r2": levels.r2,
                    "s1": levels.s1,
                    "s2": levels.s2,
                    "h1": levels.h1,
                    "h2": levels.h2,
                    "l1": levels.l1,
                    "l2": levels.l2,
                    "adr5": levels.adr5,
                    "adr10": levels.adr10,
                    "volume_ratio": ratio,
                    "time": now.isoformat(),
                })
            except Exception as exc:
                print(f"[JFT ERROR] {symbol}: {exc}")

        for a in alerts:
            print(
                f"🚨 JFT {a['signal']} {a['symbol']} | "
                f"CMP={a['cmp']:.2f} R2={a['r2']:.2f} S2={a['s2']:.2f} "
                f"volume={a['volume_ratio']:.2f}x"
            )
        return alerts

    def run_forever(self) -> None:
        import time

        while True:
            now = datetime.now(IST)
            if now.time().hour < 9 or (
                now.time().hour == 9 and now.time().minute < 15
            ):
                time.sleep(30)
                continue
            if now.time().hour > 15 or (
                now.time().hour == 15 and now.time().minute >= 31
            ):
                return

            self.scan_once()

            next_minute = ((now.minute // 5) + 1) * 5
            target = now.replace(second=0, microsecond=0)
            if next_minute >= 60:
                target = target.replace(minute=0) + timedelta(hours=1)
            else:
                target = target.replace(minute=next_minute)
            time.sleep(max(1, (target - datetime.now(IST)).total_seconds()))
