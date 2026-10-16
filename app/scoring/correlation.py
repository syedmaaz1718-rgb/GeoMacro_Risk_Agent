"""Correlation engine (spec section 6): which signals are active, and are they independent enough to alert."""
from datetime import timedelta

from sqlalchemy import select

from ..config import cfg
from ..db import Signal
from ..extractors import MARKET, OSINT


def active_signals(s, region, now):
    r = cfg()["rules"]
    out = {}
    q = select(Signal).where(Signal.region.in_([region, "global"]), Signal.window_end >= now - timedelta(minutes=r["news_lookback_minutes"])).order_by(Signal.window_end)
    for sig in s.scalars(q):
        lb = r["news_lookback_minutes"] if sig.signal_type == "conflict_news_spike" else r["lookback_minutes"]
        if sig.window_end >= now - timedelta(minutes=lb):
            out[sig.signal_type] = sig            # latest per type wins
    return out


def correlate(sigs: dict) -> dict:
    """Independence principle: market confirmations only count when at least one OSINT signal is present.
    An alert candidate needs >= 2 independent signal types including OSINT."""
    osint = [t for t in sigs if t in OSINT]
    market = [t for t in sigs if t in MARKET]
    counted = osint + (market if osint else [])
    n = len(counted)
    if n >= 3 or (len(osint) >= 2 and market):
        quality = "high"
    elif n >= 2:
        quality = "standard"
    else:
        quality = "single-signal"
    return {"counted": counted, "osint": osint, "market": market, "n": n, "quality": quality,
            "alert_candidate": n >= 2 and bool(osint)}
