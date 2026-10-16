"""Extractor 1: GPS degradation cluster (spec 5.4)."""
from datetime import timedelta

from ..config import cfg
from ._common import _baseline_per_hour, _distinct, _events, _sig


def gps(s, region, now):
    r = cfg()["rules"]["gps"]
    ev = _events(s, region, "gps_jamming", now - timedelta(minutes=60))
    objs = _distinct(ev, lambda e: e.meta.get("hex") or e.id)
    n = len(objs)
    if not n:
        return None
    avg = sum(e.severity for e in objs) / n
    if n >= r["min_events"] or (n >= r.get("min_events_for_severity_rule", 3) and avg >= r["min_avg_severity"]):
        base = _baseline_per_hour(s, region, "gps_jamming", now, lambda e: e.meta.get("hex") or e.id)
        return _sig("gps_jamming_cluster", region, now, 60, n * 10 + avg * 50, {
            "reason": f"{n} aircraft with degraded GPS integrity in 60 min (avg severity {avg:.2f})",
            "count": n, "avg_severity": round(avg, 2), "baseline_per_hour_24h": base,
            "sources": sorted({e.source for e in objs}), "event_ids": [e.id for e in objs][:50]})
