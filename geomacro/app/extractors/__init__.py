"""Signal extractors: raw events -> normalized signals (spec section 5.4)."""
import logging

from ..config import regions
from ._common import MARKET, OSINT, _baseline_per_hour, _distinct, _events, _market, _sig  # noqa: F401
from .conflict_news import news
from .crude import crude
from .gps_jamming import gps
from .india_vix import vix
from .military_aircraft import military
from .tanker_ais import ais

log = logging.getLogger("geomacro.extract")


def run_extractors(s, now):
    out = []
    for region in regions():
        for fn in (gps, military, ais, news):
            sig = fn(s, region, now)
            if sig:
                out.append(sig)
    for fn in (crude, vix):
        sig = fn(s, now)
        if sig:
            out.append(sig)
    s.add_all(out)
    s.commit()
    log.info("signals generated: %d %s", len(out), [(x.signal_type, x.region, x.score) for x in out])
    return out
