from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CPR:
    pivot: float
    bc: float
    tc: float


def calculate_cpr(high: float, low: float, close: float) -> CPR:
    if high < low:
        raise ValueError("high cannot be below low")
    if close <= 0:
        raise ValueError("close must be positive")
    pivot = (high + low + close) / 3.0
    bc = (high + low) / 2.0
    tc = 2.0 * pivot - bc
    return CPR(pivot=pivot, bc=min(bc, tc), tc=max(bc, tc))


def classify_price(price: float, cpr: CPR) -> str:
    if price > cpr.tc:
        return "ABOVE_TC"
    if price < cpr.bc:
        return "BELOW_BC"
    return "INSIDE_CPR"
