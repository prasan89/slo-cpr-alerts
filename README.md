# SLO CPR Alerts

Independent CPR monitoring and Excel alerting project.

## Scope
- NIFTY 50
- BANKNIFTY
- All current NSE F&O stocks supplied by the configured universe source
- CPR reference levels are constructed once at **09:15 IST** from the two most recent completed trading sessions
- The calculated levels are frozen for the entire trading day
- Live prices are checked every **5 minutes** from 09:15 through the 15:30 IST boundary
- Excel workbook with frozen CPR levels, snapshots and alert history

## Alert logic
- CALL trigger = `MAX(today R1, yesterday R1)`
- PUT trigger = `MIN(today S1, yesterday S1)`
- BUY CALL when price crosses/touches the CALL trigger from below
- BUY PUT when price crosses/touches the PUT trigger from above

The application is a monitoring/paper-trading tool. It does not place broker orders.

## Data provider
FYERS is the active read-only market-data provider. Groww support remains available in the project for future use. Credentials remain local and are never committed.
