from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from slo_cpr_alerts.cpr import calculate_cpr, classify_price, crossing_alert
from slo_cpr_alerts.excel import create_workbook, append_snapshot, append_signal
from slo_cpr_alerts.market_hours import is_market_open, now_ist
from slo_cpr_alerts.providers.fyers import FyersDataProvider
from slo_cpr_alerts.signal_log import append_text_signal
from slo_cpr_alerts.telegram import format_signals, send_signal


class DataProvider:
    """Interface for read-only market-data adapters."""
    def symbols(self) -> list[str]: raise NotImplementedError
    def previous_sessions(self, symbol: str, before_date: date, count: int = 2): raise NotImplementedError
    def ltp(self, symbol: str) -> float: raise NotImplementedError


class CPRMonitor:
    """Build CPR levels once at 09:15 IST, then monitor crossings every 5 minutes."""
    def __init__(self, provider: DataProvider, workbook: str | Path = "reports/cpr_alerts.xlsx", text_log: str | Path = "reports/cpr_signals.txt") -> None:
        self.provider = provider
        self.workbook = Path(workbook)
        self.text_log = Path(text_log)
        self.previous_prices: dict[str, float] = {}
        self.session_levels: dict[str, tuple[object, object, date, date]] = {}
        self.signaled_symbols: set[str] = set()
        self.levels_date: date | None = None
        create_workbook(self.workbook)

    def initialize_levels(self, trading_date: date | None = None) -> int:
        trading_date = trading_date or now_ist().date()
        self.session_levels.clear()
        self.previous_prices.clear()
        self.signaled_symbols.clear()
        count = 0
        symbols = self.provider.symbols()
        for symbol in symbols:
            sessions = self.provider.previous_sessions(symbol, trading_date, count=2)
            if len(sessions) < 2: continue
            current_session_date, current_ohlc = sessions[0]
            prior_session_date, prior_ohlc = sessions[1]
            levels = calculate_cpr(current_ohlc.high, current_ohlc.low, current_ohlc.close)
            prior_levels = calculate_cpr(prior_ohlc.high, prior_ohlc.low, prior_ohlc.close)
            self.session_levels[symbol] = (levels, prior_levels, current_session_date, prior_session_date)
            count += 1
        self.levels_date = trading_date
        print(f"CPR levels frozen at 09:15 IST for {count}/{len(symbols)} symbols")
        return count

    def check_once(self) -> int:
        now = now_ist()
        if not is_market_open(now): return 0
        if self.levels_date != now.date() or not self.session_levels: self.initialize_levels(now.date())
        count = 0; calls: list[str] = []; puts: list[str] = []; timestamp = now.strftime("%H:%M")
        for symbol in self.provider.symbols():
            frozen = self.session_levels.get(symbol)
            if frozen is None: continue
            levels, prior_levels, current_session_date, prior_session_date = frozen
            price = self.provider.ltp(symbol)
            if price <= 0: continue
            previous_price = self.previous_prices.get(symbol)
            state = classify_price(price, levels)
            alert = None if symbol in self.signaled_symbols else crossing_alert(previous_price, price, levels, prior_levels)
            self.previous_prices[symbol] = price
            width_pct = ((levels.tc - levels.bc) / levels.pivot * 100.0) if levels.pivot else 0.0
            append_snapshot(self.workbook, {"timestamp_ist": now.isoformat(), "symbol": symbol, "ltp": price, "r3": levels.r3, "r2": levels.r2, "r1": levels.r1, "tc": levels.tc, "pivot": levels.pivot, "bc": levels.bc, "s1": levels.s1, "s2": levels.s2, "s3": levels.s3, "yesterday_r1": prior_levels.r1, "yesterday_s1": prior_levels.s1, "r1_improving": levels.r1 > prior_levels.r1, "s1_improving": levels.s1 < prior_levels.s1, "cpr_width_pct": width_pct, "state": state, "alert": alert, "previous_ltp": previous_price or "", "reference_session": current_session_date.isoformat(), "prior_session": prior_session_date.isoformat()})
            if alert == "BUY_CALL_ABOVE_R1":
                calls.append(symbol); self.signaled_symbols.add(symbol); append_signal(self.workbook, timestamp, symbol, "BUY CALL", price, max(levels.r1, prior_levels.r1))
            elif alert == "BUY_PUT_BELOW_S1":
                puts.append(symbol); self.signaled_symbols.add(symbol); append_signal(self.workbook, timestamp, symbol, "BUY PUT", price, min(levels.s1, prior_levels.s1))
            count += 1
        append_text_signal(self.text_log, timestamp, calls, puts)
        if calls or puts:
            message = format_signals(timestamp, calls, puts)
            try: send_signal(message)
            except Exception as exc: print(f"Telegram notification error: {type(exc).__name__}: {exc}")
            print(f"\n===== CPR SIGNALS {timestamp} IST =====\nBUY CALL ({len(calls)}): {', '.join(calls) if calls else 'None'}\nBUY PUT  ({len(puts)}): {', '.join(puts) if puts else 'None'}\n" + "=" * 38)
        else: print(f"[{timestamp} IST] No new CALL/PUT signals")
        return count

    @staticmethod
    def _next_five_minute(now: datetime) -> datetime:
        base = now.replace(second=0, microsecond=0); minutes = base.minute - (base.minute % 5) + 5
        return base.replace(minute=0) + timedelta(hours=1) if minutes >= 60 else base.replace(minute=minutes)

    def run_forever(self) -> None:
        while True:
            now = now_ist()
            if now.time() < datetime.strptime("09:15", "%H:%M").time():
                target = now.replace(hour=9, minute=15, second=0, microsecond=0); time.sleep(max(0.0, (target - now).total_seconds())); continue
            if now.time() > datetime.strptime("15:30", "%H:%M").time(): return
            try:
                if self.levels_date != now.date(): self.initialize_levels(now.date())
                self.check_once()
            except Exception as exc: print(f"CPR monitor error: {type(exc).__name__}: {exc}")
            now = now_ist()
            if now.time() >= datetime.strptime("15:30", "%H:%M").time(): return
            target = self._next_five_minute(now); time.sleep(max(0.0, (target - now).total_seconds()))


def _symbols() -> list[str]:
    return [item.strip() for item in os.getenv("SLO_SYMBOLS", "NIFTY,BANKNIFTY").split(",") if item.strip()]


def main() -> None:
    if os.getenv("SLO_DATA_PROVIDER", "fyers").lower() != "fyers": raise SystemExit("Current CLI default is FYERS. Set SLO_DATA_PROVIDER=fyers.")
    app_id = os.getenv("FYERS_APP_ID"); access_token = os.getenv("FYERS_ACCESS_TOKEN")
    if not app_id or not access_token: raise SystemExit("Missing FYERS_APP_ID or FYERS_ACCESS_TOKEN. Run `fyers-auth` to generate a token locally.")
    symbols = _symbols(); provider = FyersDataProvider(app_id, access_token, symbols); monitor = CPRMonitor(provider)
    print(f"FYERS CPR monitor started for {len(symbols)} symbols; frozen levels=09:15 IST; interval=5m")
    print(f"Excel: {monitor.workbook} | Text: {monitor.text_log}")
    print("Telegram notifications: ENABLED" if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID") else "Telegram notifications: DISABLED (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)")
    monitor.run_forever()
