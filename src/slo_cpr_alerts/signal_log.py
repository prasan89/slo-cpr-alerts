from __future__ import annotations

from pathlib import Path


def append_text_signal(path: str | Path, timestamp: str, calls: list[str], puts: list[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} IST\n")
        handle.write(f"BUY CALL ({len(calls)}): {', '.join(calls) if calls else 'None'}\n")
        handle.write(f"BUY PUT  ({len(puts)}): {', '.join(puts) if puts else 'None'}\n")
        handle.write("-" * 50 + "\n")
