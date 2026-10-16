"""Extractor 4: conflict news spike (spec 5.4)."""
from datetime import timedelta

from ..config import cfg
from ._common import _baseline_per_hour, _distinct, _events, _sig


def news(s, region, now):
    r = cfg()["rules"]["news"]
    ev = _events(s, region, "news_spike", now - timedelta(minutes=60), "gdelt")
    n = len(ev)
    if n >= r["min_mentions"]:
        domains = sorted({e.meta.get("domain") for e in ev if e.meta.get("domain")})
        return _sig("conflict_news_spike", region, now, 60, n * 10, {
            "reason": f"{n} conflict-related articles in 60 min from {len(domains)} outlets", "count": n,
            "headlines": [e.meta.get("title") for e in ev][:8], "event_ids": [e.id for e in ev][:50]})
