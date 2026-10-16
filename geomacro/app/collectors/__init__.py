"""Feed collectors. Each returns a list of normalized RawEvent rows and never raises
past `run_feed`, which records success/failure for observability."""
import logging
import time

from ..db import FeedRun, RawEvent, SessionLocal, now

log = logging.getLogger("geomacro.collect")
UA = "GeoMacroRiskAgent/1.0 (research; contact via repo)"


def make_event(source, event_type, region, ts, lat=None, lon=None, severity=0.0, payload=None, meta=None):
    return RawEvent(
        source=source, event_type=event_type, region=region, timestamp=ts,
        lat=lat, lon=lon, severity=max(0.0, min(1.0, float(severity))),
        raw_payload=payload or {}, meta=meta or {},
    )


def run_feed(name, fn):
    """Run a collector function returning list[RawEvent]; store events + a FeedRun record."""
    t0 = time.time()
    ok, detail, events = True, "", []
    try:
        events = fn() or []
    except Exception as e:  # noqa: BLE001 - feed failures must never kill the scheduler
        ok, detail = False, f"{type(e).__name__}: {e}"[:500]
        log.warning("feed %s failed: %s", name, detail)
    with SessionLocal() as s:
        if events:
            s.add_all(events)
        s.add(FeedRun(feed=name, started_at=now(), duration_s=round(time.time() - t0, 2),
                      ok=ok, events=len(events), detail=detail))
        s.commit()
    return len(events)


# spec-named collector modules, with the short names the rest of the app uses
from . import gdelt_collector as gdelt  # noqa: E402,F401
from . import market_collector as market  # noqa: E402,F401
from . import shadowbroker_collector as shadowbroker  # noqa: E402,F401
