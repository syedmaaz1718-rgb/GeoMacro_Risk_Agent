"""Extractor 2: military aircraft spike (spec 5.4)."""
from datetime import timedelta

from ..config import cfg
from ._common import _baseline_per_hour, _distinct, _events, _sig


def military(s, region, now):
    r = cfg()["rules"]["military"]
    ev = _events(s, region, "military_aircraft", now - timedelta(minutes=60))
    objs = _distinct(ev, lambda e: e.meta.get("hex") or e.id)
    n = len(objs)
    if n >= r["min_aircraft"]:
        base = _baseline_per_hour(s, region, "military_aircraft", now, lambda e: e.meta.get("hex") or e.id)
        return _sig("military_spike", region, now, 60, n * 8, {
            "reason": f"{n} military aircraft tracked in region in 60 min", "count": n,
            "baseline_per_hour_24h": base,
            "callsigns": sorted({e.meta.get("callsign") for e in objs if e.meta.get("callsign")})[:15],
            "event_ids": [e.id for e in objs][:50]})
