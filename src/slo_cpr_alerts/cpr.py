from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class CPR:
    pivot: float; bc: float; tc: float; r1: float; r2: float; r3: float; s1: float; s2: float; s3: float
def calculate_cpr(high:float,low:float,close:float)->CPR:
    if high<low: raise ValueError("high cannot be below low")
    if close<=0: raise ValueError("close must be positive")
    pivot=(high+low+close)/3.0; raw_bc=(high+low)/2.0; raw_tc=2.0*pivot-raw_bc; bc=min(raw_bc,raw_tc); tc=max(raw_bc,raw_tc)
    r1=2.0*pivot-low; s1=2.0*pivot-high; r2=pivot+(high-low); s2=pivot-(high-low); r3=high+2.0*(pivot-low); s3=low-2.0*(high-pivot)
    return CPR(pivot,bc,tc,r1,r2,r3,s1,s2,s3)
def classify_price(price:float,cpr:CPR)->str:
    if price>cpr.r1:return "ABOVE_R1"
    if price<cpr.s1:return "BELOW_S1"
    if price>cpr.tc:return "ABOVE_CPR"
    if price<cpr.bc:return "BELOW_CPR"
    return "INSIDE_CPR"
def crossing_alert(previous_price:float|None,current_price:float,current_levels:CPR,prior_levels:CPR,volume_ratio:float=0.0,min_volume_ratio:float=1.2)->str:
    """Confirm only when CMP is beyond BOTH today's and yesterday's R1/S1 and 5m volume is strong."""
    if previous_price is None or volume_ratio<min_volume_ratio:return ""
    buy_trigger=max(current_levels.r1,prior_levels.r1); sell_trigger=min(current_levels.s1,prior_levels.s1)
    if previous_price<buy_trigger<=current_price and current_price>current_levels.r1 and current_price>prior_levels.r1:
        return "BUY_CALL_ABOVE_BOTH_R1_VOLUME"
    if previous_price>sell_trigger>=current_price and current_price<current_levels.s1 and current_price<prior_levels.s1:
        return "BUY_PUT_BELOW_BOTH_S1_VOLUME"
    return ""
