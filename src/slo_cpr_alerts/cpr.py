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

    return CPR(pivot, bc, tc, r1, r2, r3, s1, s2, s3)


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


def crossing_alert(
    previous_price: float | None,
    current_price: float,
    current_levels: CPR,
    prior_levels: CPR,
) -> str:
    """Alert when price reaches the stronger of today's/yesterday's R1,
    or the weaker of today's/yesterday's S1.

    Long-side trigger: price touches/crosses max(today R1, yesterday R1).
    Short-side trigger: price touches/crosses min(today S1, yesterday S1).
    """
    if previous_price is None:
        return ""

    buy_trigger = max(current_levels.r1, prior_levels.r1)
    sell_trigger = min(current_levels.s1, prior_levels.s1)

    if previous_price < buy_trigger <= current_price:
        return "BUY_CALL_ABOVE_R1"
    if previous_price > sell_trigger >= current_price:
        return "BUY_PUT_BELOW_S1"
    return ""
