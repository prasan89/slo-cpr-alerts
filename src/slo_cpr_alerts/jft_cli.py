from __future__ import annotations

import os
from slo_cpr_alerts.jft import JFTScanner
from slo_cpr_alerts.providers.fyers import FyersDataProvider


def main() -> None:
    app_id = os.getenv("FYERS_APP_ID")
    access_token = os.getenv("FYERS_ACCESS_TOKEN")
    if not app_id or not access_token:
        raise SystemExit("Missing FYERS_APP_ID or FYERS_ACCESS_TOKEN")
    symbols = [s.strip() for s in os.getenv("SLO_SYMBOLS", "NIFTY,BANKNIFTY").split(",") if s.strip()]
    threshold = float(os.getenv("SLO_MIN_VOLUME_RATIO", "1.2"))
    provider = FyersDataProvider(app_id, access_token, symbols)
    print(f"JFT scanner started: symbols={len(symbols)}, interval=5m, R2/S2 + volume, threshold={threshold:.2f}x")
    JFTScanner(provider, min_volume_ratio=threshold).run_forever()


if __name__ == "__main__":
    main()
