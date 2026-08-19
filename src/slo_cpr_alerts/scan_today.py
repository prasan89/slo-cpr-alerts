from __future__ import annotations

import os
from datetime import date

from slo_cpr_alerts.cpr import calculate_cpr
from slo_cpr_alerts.providers.fyers import FyersDataProvider

# NSE F&O stocks + indices (source: NSE master-quote API)
FNO_SYMBOLS = [
    "NIFTY", "BANKNIFTY",
    "360ONE", "ABB", "ABCAPITAL", "ADANIENSOL", "ADANIENT", "ADANIGREEN",
    "ADANIPORTS", "ADANIPOWER", "ALKEM", "AMBER", "AMBUJACEM", "ANGELONE",
    "APLAPOLLO", "APOLLOHOSP", "ASHOKLEY", "ASIANPAINT", "ASTRAL", "AUBANK",
    "AUROPHARMA", "AXISBANK", "BAJAJ-AUTO", "BAJAJFINSV", "BAJAJHLDNG",
    "BAJFINANCE", "BANDHANBNK", "BANKBARODA", "BANKINDIA", "BDL", "BEL",
    "BHARATFORG", "BHARTIARTL", "BHEL", "BIOCON", "BLUESTARCO", "BOSCHLTD",
    "BPCL", "BRITANNIA", "BSE", "CAMS", "CANBK", "CDSL", "CGPOWER",
    "CHOLAFIN", "CIPLA", "COALINDIA", "COCHINSHIP", "COFORGE", "COLPAL",
    "CONCOR", "CROMPTON", "CUMMINSIND", "DABUR", "DALBHARAT", "DELHIVERY",
    "DIVISLAB", "DIXON", "DLF", "DMART", "DRREDDY", "EICHERMOT", "ETERNAL",
    "FEDERALBNK", "FORCEMOT", "FORTIS", "GAIL", "GLENMARK", "GMRAIRPORT",
    "GODFRYPHLP", "GODREJCP", "GODREJPROP", "GRASIM", "GVT&D", "HAL",
    "HAVELLS", "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDPETRO", "HINDUNILVR", "HINDZINC", "HYUNDAI", "ICICIBANK",
    "ICICIGI", "ICICIPRULI", "IDEA", "IDFCFIRSTB", "IEX", "INDHOTEL",
    "INDIANB", "INDIGO", "INDUSINDBK", "INDUSTOWER", "INFY", "INOXWIND",
    "IOC", "IREDA", "IRFC", "ITC", "JINDALSTEL", "JIOFIN", "JSWENERGY",
    "JSWSTEEL", "JUBLFOOD", "KALYANKJIL", "KAYNES", "KEI", "KFINTECH",
    "KOTAKBANK", "KPITTECH", "LAURUSLABS", "LICHSGFIN", "LICI", "LODHA",
    "LT", "LTF", "LTM", "LUPIN", "M&M", "MANAPPURAM", "MANKIND", "MARICO",
    "MARUTI", "MAXHEALTH", "MAZDOCK", "MCX", "MFSL", "MOTHERSON",
    "MOTILALOFS", "MPHASIS", "MUTHOOTFIN", "NAM-INDIA", "NATIONALUM",
    "NAUKRI", "NBCC", "NESTLEIND", "NHPC", "NMDC", "NTPC", "NYKAA",
    "OBEROIRLTY", "OFSS", "OIL", "ONGC", "PAGEIND", "PATANJALI", "PAYTM",
    "PERSISTENT", "PETRONET", "PFC", "PGEL", "PHOENIXLTD", "PIDILITIND",
    "PIIND", "PNB", "PNBHOUSING", "POLICYBZR", "POLYCAB", "POWERGRID",
    "POWERINDIA", "PREMIERENE", "PRESTIGE", "RADICO", "RBLBANK", "RECLTD",
    "RELIANCE", "RVNL", "SAIL", "SBICARD", "SBILIFE", "SBIN", "SHREECEM",
    "SHRIRAMFIN", "SIEMENS", "SOLARINDS", "SONACOMS", "SRF", "SUNPHARMA",
    "SUPREMEIND", "SUZLON", "SWIGGY", "TATACONSUM", "TATAELXSI", "TATAPOWER",
    "TATASTEEL", "TCS", "TECHM", "TIINDIA", "TITAN", "TMPV", "TORNTPHARM",
    "TRENT", "TVSMOTOR", "ULTRACEMCO", "UNIONBANK", "UNITDSPR", "UNOMINDA",
    "UPL", "VBL", "VEDL", "VMM", "VOLTAS", "WAAREEENER", "WIPRO", "YESBANK",
    "ZYDUSLIFE",
]


def _provider() -> FyersDataProvider:
    app_id = os.getenv("FYERS_APP_ID")
    access_token = os.getenv("FYERS_ACCESS_TOKEN")
    symbols = os.getenv("SLO_SYMBOLS", "")
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()] if symbols else FNO_SYMBOLS
    if not app_id or not access_token:
        raise SystemExit("Missing FYERS_APP_ID or FYERS_ACCESS_TOKEN")
    return FyersDataProvider(app_id, access_token, symbol_list)


def main() -> None:
    provider = _provider()
    today = date.today()

    buy_calls: list[tuple[str, float, float, float]] = []
    buy_puts: list[tuple[str, float, float, float]] = []

    print(f"Scanning {len(provider.symbols())} symbols for {today}...\n")

    for symbol in provider.symbols():
        sessions = provider.previous_sessions(symbol, today, count=2)
        if len(sessions) < 2:
            continue

        _, today_ohlc = sessions[0]
        _, yest_ohlc = sessions[1]

        today_levels = calculate_cpr(today_ohlc.high, today_ohlc.low, today_ohlc.close)
        yest_levels = calculate_cpr(yest_ohlc.high, yest_ohlc.low, yest_ohlc.close)

        call_trigger = max(today_levels.r1, yest_levels.r1)
        put_trigger = min(today_levels.s1, yest_levels.s1)

        try:
            ltp = provider.ltp(symbol)
        except Exception:
            continue

        if ltp >= call_trigger:
            buy_calls.append((symbol, ltp, call_trigger, today_levels.r1))
        elif ltp <= put_trigger:
            buy_puts.append((symbol, ltp, put_trigger, today_levels.s1))

    print(f"TODAY'S SLO-CPR REPORT — {today.strftime('%d %b %Y').upper()}")
    print("=" * 50)

    print("\nBUY CALL")
    print("-" * 50)
    if buy_calls:
        for symbol, ltp, trigger, r1 in sorted(buy_calls, key=lambda x: x[0]):
            print(f"  {symbol:<20} LTP={ltp:.2f}  R1_trigger={trigger:.2f}  Today_R1={r1:.2f}")
    else:
        print("  No signals")

    print("\nBUY PUT")
    print("-" * 50)
    if buy_puts:
        for symbol, ltp, trigger, s1 in sorted(buy_puts, key=lambda x: x[0]):
            print(f"  {symbol:<20} LTP={ltp:.2f}  S1_trigger={trigger:.2f}  Today_S1={s1:.2f}")
    else:
        print("  No signals")


if __name__ == "__main__":
    main()
