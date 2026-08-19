# SLO CPR Alerts

Independent CPR monitoring and Excel alerting project.

## Scope
- NIFTY 50
- BANKNIFTY
- All current NSE F&O stocks supplied by the configured universe source
- Previous-trading-day CPR levels: Pivot, BC, TC
- Live price checks every 5 minutes during 09:15–15:30 IST
- Excel workbook with CPR levels, snapshots and alert history

## Alerts
- ABOVE_TC: price moves above Top Central
- BELOW_BC: price moves below Bottom Central
- INSIDE_CPR: price remains within CPR
- RE-ENTRY: price returns into CPR after a breakout/breakdown

The application is a monitoring tool. It does not place broker orders.

## Data provider
The first adapter will use a read-only broker/API market-data source. Credentials remain local in `.env` and are never committed.
