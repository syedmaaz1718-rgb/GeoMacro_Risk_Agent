"""Shared helpers for the signal extractors."""
from datetime import timedelta

from sqlalchemy import select

from ..config import cfg
from ..db import RawEvent, Signal

OSINT = ("gps_jamming_cluster", "military_spike", "tanker_dark_gap", "conflict_news_spike")


MARKET = ("crude_confirmation", "vix_confirmation")


def _sig(stype, region, now, minutes, score, evidence):
    return Signal(signal_type=stype, region=region, window_start=now - timedelta(minutes=minutes),
                  window_end=now, score=int(min(100, round(score))), evidence=evidence)


def _events(s, region, etype, since, source=None):
    q = select(RawEvent).where(RawEvent.region == region, RawEvent.event_type == etype, RawEvent.timestamp >= since)
    if source:
        q = q.where(RawEvent.source == source)
    return list(s.scalars(q))


def _distinct(events, key):
    seen = {}
    for e in events:
        seen.setdefault(key(e), e)
    return list(seen.values())


def _baseline_per_hour(s, region, etype, now, key):
    """Distinct-object count per hour over the previous 24h (excluding the last hour)."""
    ev = _events(s, region, etype, now - timedelta(hours=25))
    ev = [e for e in ev if e.timestamp < now - timedelta(hours=1)]
    if not ev:
        return None
    buckets = {}
    for e in ev:
        buckets.setdefault(int(e.timestamp.timestamp() // 3600), set()).add(key(e))
    hours = max(1, len(buckets))
    return round(sum(len(b) for b in buckets.values()) / hours, 1)


def _market(s, now, etype, stype, thresholds, label):
    e = s.scalars(select(RawEvent).where(RawEvent.event_type == etype).order_by(RawEvent.timestamp.desc()).limit(1)).first()
    if not e or e.meta.get("stale"):
        return None
    pct = e.meta.get("pct", 0)
    t1, t2, t3 = thresholds
    if pct < t1:
        return None
    score = 50 if pct < t2 else 75 if pct < t3 else 100
    return _sig(stype, "global", now, 120, score, {
        "reason": f"{label} {pct:+.1f}% intraday", "pct": pct, "last": e.meta.get("last"),
        "symbol": e.meta.get("symbol"), "event_ids": [e.id]})
