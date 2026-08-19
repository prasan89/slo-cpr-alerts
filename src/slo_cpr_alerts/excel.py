from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font


HEADERS = [
    "timestamp_ist", "symbol", "ltp", "r3", "r2", "r1", "tc", "pivot", "bc",
    "s1", "s2", "s3", "yesterday_r1", "yesterday_s1", "r1_improving", "s1_improving",
    "cpr_width_pct", "state", "alert", "previous_ltp",
]


def append_snapshot(path: str | Path, row: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        wb = load_workbook(path)
        ws = wb["CPR Alerts"]
        # Existing workbooks created by an earlier version are upgraded in place.
        existing = [cell.value for cell in ws[1]]
        if existing != HEADERS:
            ws.delete_rows(1, ws.max_row)
            ws.append(HEADERS)
            for cell in ws[1]:
                cell.font = Font(bold=True)
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "CPR Alerts"
        ws.append(HEADERS)
        for cell in ws[1]:
            cell.font = Font(bold=True)

    ws = wb["CPR Alerts"]
    ws.append([row.get(h) for h in HEADERS])
    ws.freeze_panes = "A2"
    wb.save(path)


def create_workbook(path: str | Path) -> None:
    path = Path(path)
    if path.exists():
        return
    wb = Workbook()
    ws = wb.active
    ws.title = "CPR Alerts"
    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    wb.create_sheet("Latest Snapshot")
    wb.create_sheet("CPR Levels")
    wb.save(path)
