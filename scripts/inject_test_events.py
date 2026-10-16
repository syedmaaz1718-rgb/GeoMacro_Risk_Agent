"""DEV ONLY: inject spec manual test cases 1-4 (spec section 18) into a THROWAWAY database.

The live app only ever uses real feeds. This script exists so the pipeline (events -> signals -> score -> alert)
can be exercised end to end. By default it uses a temporary SQLite file and prints the result. It refuses to touch
a DATABASE_URL that is set in the environment unless you pass --force.

    python scripts/inject_test_events.py            # runs all four cases on a temp DB
    python scripts/inject_test_events.py --case 3
"""
import argparse
import os
import sys
import tempfile
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ap = argparse.ArgumentParser()
ap.add_argument("--case", type=int, choices=[1, 2, 3, 4])
ap.add_argument("--force", action="store_true", help="allow writing to the DATABASE_URL from the environment")
args = ap.parse_args()
if os.environ.get("DATABASE_URL") and not args.force:
    sys.exit("Refusing: DATABASE_URL is set. This script writes fake events. Unset it or pass --force (never on production).")
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/inject.db"
os.environ.setdefault("GEOMACRO_NO_SCHEDULER", "1")
os.environ["LLM_PROVIDER"] = "none"
os.environ["TELEGRAM_BOT_TOKEN"] = ""

from app import alerts, extractors, scoring  # noqa: E402
from app.collectors import make_event  # noqa: E402
from app.db import Base, SessionLocal, engine, init_db, now  # noqa: E402


def add(s, etype, region, n, source="adsb", sev=0.5, prefix="h"):
    for i in range(n):
        s.add(make_event(source, etype, region, now() - timedelta(minutes=5), 26.0, 56.0, sev, {},
                         {"hex": f"{prefix}{i}", "key": f"{prefix}{i}", "title": f"t{i}", "domain": f"d{i}"}))
    s.commit()


def market(s, kind, pct):
    m = {"pct": pct, "last": 90, "stale": False, "symbol": "TEST", "bar_time": now().isoformat()}
    s.add(make_event("market_feed", kind, "global", now(), None, None, 0.5, dict(m), m))
    s.commit()


CASES = {
    1: ("Normal day: no signals", lambda s: None),
    2: ("Red Sea news spike + mild military activity (see note in README)", lambda s: (
        add(s, "news_spike", "red_sea", 5, "gdelt"), add(s, "military_aircraft", "red_sea", 8, prefix="m"))),
    3: ("Hormuz GPS + military + crude", lambda s: (
        add(s, "gps_jamming", "hormuz", 6), add(s, "military_aircraft", "hormuz", 8, prefix="m"), market(s, "crude_move", 2.6))),
    4: ("Hormuz GPS + military + news + AIS dark gap + crude + VIX", lambda s: (
        add(s, "gps_jamming", "hormuz", 6), add(s, "military_aircraft", "hormuz", 8, prefix="m"),
        add(s, "news_spike", "hormuz", 5, "gdelt"), add(s, "ais_dark_gap", "hormuz", 3, "aisstream"),
        market(s, "crude_move", 2.6), market(s, "vix_move", 9.0))),
}

for n in ([args.case] if args.case else sorted(CASES)):
    init_db()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    name, fn = CASES[n]
    with SessionLocal() as s:
        fn(s)
        t = now()
        extractors.run_extractors(s, t)
        snaps = scoring.score_regions(s, t)
        sent = alerts.run_alerts(s, t)
        top = max(snaps, key=lambda x: x.score)
        print(f"TEST CASE {n}: {name}\n  top region {top.region}: score {top.score} {top.label}; alerts sent: {len(sent)}")
        for a in sent:
            print("  ->", a.label, a.region, "|", a.message.splitlines()[0])
