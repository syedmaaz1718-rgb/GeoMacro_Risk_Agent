"""Extractor 3: tanker / AIS anomalies (spec 5.4)."""
from datetime import timedelta

from ..config import cfg
from ._common import _baseline_per_hour, _distinct, _events, _sig


def ais(s, region, now):
    r = cfg()["rules"]["ais"]
    ev = _events(s, region, "ais_dark_gap", now - timedelta(hours=2), "aisstream")
    objs = _distinct(ev, lambda e: e.meta.get("key") or e.id)
    n = len(objs)
    if n >= r["min_anomalies"]:
        kinds = {}
        for e in objs:
            kinds[e.meta.get("kind", "anomaly")] = kinds.get(e.meta.get("kind", "anomaly"), 0) + 1
        return _sig("tanker_dark_gap", region, now, 120, n * 20, {
            "reason": f"{n} tanker AIS anomalies in 2 hours", "count": n, "kinds": kinds,
            "event_ids": [e.id for e in objs][:50]})
