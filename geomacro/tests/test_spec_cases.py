"""Spec section 18 manual test cases 1-4, plus integration tests with mocked HTTP (spec section 17)."""
from datetime import timedelta

import httpx

from app import alerts, extractors, scoring
from app.collectors import make_event, run_feed
from app.db import Alert, FeedRun, RawEvent, SessionLocal, now
from tests.test_core import ev


def run(s):
    t = now()
    extractors.run_extractors(s, t)
    snaps = {x.region: x for x in scoring.score_regions(s, t)}
    return snaps, alerts.run_alerts(s, t)


def market(s, kind, pct):
    m = {"pct": pct, "last": 90, "stale": False, "symbol": "T", "bar_time": now().isoformat()}
    s.add(make_event("market_feed", kind, "global", now(), None, None, 0.5, dict(m), m))
    s.commit()


def test_tc1_normal_no_alert():
    with SessionLocal() as s:
        snaps, sent = run(s)
        assert all(x.label == "NORMAL" for x in snaps.values()) and sent == []


def test_tc2_news_plus_mild_military_is_caution():
    # Spec TC2 says news alone = CAUTION, but its own formula gives 15 x 1.10 = 16.5 (NORMAL) and a single family never alerts.
    with SessionLocal() as s:
        ev(s, "news_spike", "red_sea", 5, source="gdelt")
        snaps, sent = run(s)
        assert snaps["red_sea"].label == "NORMAL" and sent == []
        ev(s, "military_aircraft", "red_sea", 8, prefix="m")
        snaps, sent = run(s)
        assert snaps["red_sea"].label == "CAUTION"


def test_tc3_hormuz_gps_military_crude_is_high():
    with SessionLocal() as s:
        ev(s, "gps_jamming", "hormuz", 6)
        ev(s, "military_aircraft", "hormuz", 8, prefix="m")
        market(s, "crude_move", 2.6)
        snaps, sent = run(s)
        assert snaps["hormuz"].label == "HIGH" and sent and sent[0].label == "HIGH"


def test_tc4_all_signals_is_avoid():
    with SessionLocal() as s:
        ev(s, "gps_jamming", "hormuz", 6)
        ev(s, "military_aircraft", "hormuz", 8, prefix="m")
        ev(s, "news_spike", "hormuz", 5, source="gdelt")
        ev(s, "ais_dark_gap", "hormuz", 3, source="aisstream")
        market(s, "crude_move", 2.6)
        market(s, "vix_move", 9.0)
        snaps, sent = run(s)
        assert snaps["hormuz"].label == "AVOID" and "AVOID FRESH NARROW IC" in sent[0].message


def test_collector_inserts_raw_events_with_mocked_http(monkeypatch):
    from app.collectors import adsb
    called = {}

    def fake(tiles=None):
        called["ok"] = True
        return [make_event("adsb", "gps_jamming", "hormuz", now(), 26, 56, 0.7, {}, {"hex": "abc", "key": "abc"})]
    monkeypatch.setattr(adsb, "collect_gps_and_aircraft", fake)
    run_feed("adsb", adsb.collect_gps_and_aircraft)
    with SessionLocal() as s:
        assert s.query(RawEvent).count() == 1 and s.query(FeedRun).filter_by(feed="adsb", ok=True).count() == 1


def test_telegram_retries_three_times_then_failed(monkeypatch):
    from app.alerts import telegram
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(telegram.time, "sleep", lambda *_: None)
    n = {"c": 0}

    def boom(*a, **k):
        n["c"] += 1
        raise httpx.ConnectError("down")
    monkeypatch.setattr(telegram.httpx, "post", boom)
    status, _ = telegram.deliver("hi")
    assert n["c"] == 3 and status == "failed"


def test_telegram_success_mocked(monkeypatch):
    from app.alerts import telegram
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(telegram.httpx, "post", lambda *a, **k: httpx.Response(200, request=httpx.Request("POST", "http://x")))
    assert telegram.deliver("hi") == ("sent", "telegram:42")


def test_stale_feed_warning(monkeypatch):
    with SessionLocal() as s:
        s.add(FeedRun(feed="adsb", started_at=now() - timedelta(minutes=35), ok=True))
        s.commit()
        w = alerts.stale_feed_warnings(s)
        assert len(w) == 1 and w[0].region == "system"
        assert "feed stale for 35 minutes. Risk score may be incomplete." in w[0].message
        assert alerts.stale_feed_warnings(s) == []          # deduped for 2 h
    with SessionLocal() as s:
        s.add(FeedRun(feed="adsb", started_at=now(), ok=True))
        s.commit()
