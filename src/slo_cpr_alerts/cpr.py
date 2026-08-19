from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CPR:
    pivot: float
    bc: float
    tc: float
    r1: float
    r2: float
    r3: float
    s1: float
    s2: float
    s3: float


def calculate_cpr(high: float, low: float, close: float) -> CPR:
    """Calculate previous-day CPR plus standard floor-pivot S/R levels."""
    if high < low:
        raise ValueError("high cannot be below low")
    if close <= 0:
        raise ValueError("close must be positive")

    pivot = (high + low + close) / 3.0
    raw_bc = (high + low) / 2.0
    raw_tc = 2.0 * pivot - raw_bc
    bc = min(raw_bc, raw_tc)
    tc = max(raw_bc, raw_tc)

    r1 = 2.0 * pivot - low
    s1 = 2.0 * pivot - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)
    r3 = high + 2.0 * (pivot - low)
    s3 = low - 2.0 * (high - pivot)

    return CPR(
        pivot=pivot,
        bc=bc,
        tc=tc,
        r1=r1,
        r2=r2,
        r3=r3,
        s1=s1,
        s2=s2,
        s3=s3,
    )


def classify_price(price: float, cpr: CPR) -> str:
    if price > cpr.r1:
        return "ABOVE_R1"
    if price < cpr.s1:
        return "BELOW_S1"
    if price > cpr.tc:
        return "ABOVE_CPR"
    if price < cpr.bc:
        return "BELOW_CPR"
    return "INSIDE_CPR"


def crossing_alert(previous_price: float | None, current_price: float, cpr: CPR) -> str:
    """Return an alert only when price crosses R1 upward or S1 downward."""
    if previous_price is None:
        return ""
    if previous_price <= cpr.r1 < current_price:
        return "CROSS_ABOVE_R1"
    if previous_price >= cpr.s1 > current_price:
        return "CROSS_BELOW_S1"
    return ""
