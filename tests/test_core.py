from datetime import timedelta
from types import SimpleNamespace as NS

from app import alerts, extractors, scoring
from app.collectors import adsb, ais, gdelt, make_event
from app.config import label_for, region_of
from app.db import Alert, RawEvent, SessionLocal, Signal, Vessel, now


def test_bands():
    assert [label_for(x) for x in (0, 30, 31, 55, 56, 75, 76, 100)] == ["NORMAL", "NORMAL", "CAUTION", "CAUTION", "HIGH", "HIGH", "AVOID", "AVOID"]


def test_region_lookup():
    assert region_of(26.5, 56.2) == "hormuz"
    assert region_of(20.0, 38.0) == "red_sea"
    assert region_of(31.5, 74.3) == "india_pak"
    assert region_of(0, 0) is None


def sig(t, score=80):
    return NS(signal_type=t, score=score)


def test_score_spec_example():
    # GPS + tanker + crude in Hormuz = (25+20+10) * 1.25 = 68.75 -> 69 HIGH, matches spec's HIGH example
    d = scoring.compute({"gps_jamming_cluster": 1, "tanker_dark_gap": 1, "crude_confirmation": 1}, "hormuz")
    assert d["score"] == 69 and d["label"] == "HIGH" and d["alert_candidate"] and d["quality"] == "high"


def test_market_alone_never_counts():
    d = scoring.compute({"crude_confirmation": 1, "vix_confirmation": 1}, "india_pak")
    assert d["score"] == 0 and not d["alert_candidate"]


def test_single_family_not_candidate():
    d = scoring.compute({"conflict_news_spike": 1}, "red_sea")
    assert not d["alert_candidate"] and d["quality"] == "single-signal"


def test_cap_100():
    d = scoring.compute({k: 1 for k in ("gps_jamming_cluster", "military_spike", "tanker_dark_gap", "conflict_news_spike", "crude_confirmation", "vix_confirmation")}, "india_pak")
    assert d["score"] == 100 and d["label"] == "AVOID"


def ev(s, etype, region, n, source="adsb", sev=0.5, prefix="h", minutes=5):
    for i in range(n):
        s.add(make_event(source, etype, region, now() - timedelta(minutes=minutes), 26.0, 56.0, sev, {}, {"hex": f"{prefix}{i}", "key": f"{prefix}{i}", "title": f"t{i}", "domain": f"d{i}"}))
    s.commit()


def test_gps_rule_and_score():
    with SessionLocal() as s:
        ev(s, "gps_jamming", "hormuz", 4, sev=0.5)
        assert extractors.gps(s, "hormuz", now()) is None          # 4 < 5 and avg < 0.65
        ev(s, "gps_jamming", "hormuz", 2, sev=0.5, prefix="x")
        g = extractors.gps(s, "hormuz", now())
        assert g and g.score == min(100, 6 * 10 + 0.5 * 50)


def test_gps_counts_distinct_aircraft():
    with SessionLocal() as s:
        for _ in range(10):
            ev(s, "gps_jamming", "hormuz", 1, prefix="same")
        assert extractors.gps(s, "hormuz", now()) is None


def test_military_news_ais_rules():
    with SessionLocal() as s:
        ev(s, "military_aircraft", "red_sea", 8)
        assert extractors.military(s, "red_sea", now()).score == 64
        ev(s, "news_spike", "red_sea", 5, source="gdelt")
        assert extractors.news(s, "red_sea", now()).score == 50
        ev(s, "ais_dark_gap", "hormuz", 3, source="aisstream")
        assert extractors.ais(s, "hormuz", now()).score == 60


def test_market_signal_thresholds_and_stale():
    with SessionLocal() as s:
        s.add(make_event("market_feed", "crude_move", "global", now(), meta={"pct": 2.6, "last": 90, "stale": False, "symbol": "BZ=F"}))
        s.add(make_event("market_feed", "vix_move", "global", now(), meta={"pct": 9.0, "last": 15, "stale": True}))
        s.commit()
        assert extractors.crude(s, now()).score == 75
        assert extractors.vix(s, now()) is None               # stale market gives no signal


def test_end_to_end_alert_and_dedupe():
    with SessionLocal() as s:
        ev(s, "gps_jamming", "hormuz", 6)
        ev(s, "military_aircraft", "hormuz", 8, prefix="m")
        t = now()
        extractors.run_extractors(s, t)
        scoring.score_regions(s, t)
        sent = alerts.run_alerts(s, t)
        assert [a.region for a in sent] == ["hormuz"] and sent[0].label == "HIGH"   # (25+20)*1.25 = 56.25 -> 56

        # dedupe: same region + same band within 60 min is not sent again
        scoring.score_regions(s, now())
        assert alerts.run_alerts(s, now()) == []
        # escalation: adding news + crude moves HIGH -> AVOID and sends immediately
        ev(s, "news_spike", "hormuz", 5, source="gdelt")
        ev(s, "ais_dark_gap", "hormuz", 3, source="aisstream")
        t = now()
        extractors.run_extractors(s, t)
        scoring.score_regions(s, t)
        sent = alerts.run_alerts(s, t)
        assert sent and sent[0].label == "AVOID" and sent[0].meta["escalation"]
        assert "AVOID FRESH NARROW IC" in sent[0].message and sent[0].status == "logged"


def test_resolution_after_three_normal_checks():
    snap = lambda lab: NS(label=lab)
    last = NS(label="HIGH", meta={"kind": "risk"})
    assert alerts.decide("NORMAL", False, [], last, [snap("NORMAL")] * 3, 60, 3, now()) == "resolve"
    assert alerts.decide("NORMAL", False, [], last, [snap("NORMAL"), snap("NORMAL"), snap("HIGH")], 60, 3, now()) is None
    assert alerts.decide("NORMAL", False, [], NS(label="HIGH", meta={"kind": "resolved"}), [snap("NORMAL")] * 3, 60, 3, now()) is None
    assert alerts.decide("HIGH", False, [], None, [], 60, 3, now()) is None   # not a candidate


def test_adsb_degraded_and_tiles():
    assert adsb.is_degraded({"nac_p": 8, "alt_baro": 30000}, 5) is False
    assert adsb.is_degraded({"nac_p": 0, "alt_baro": 30000}, 5) == 1.0
    assert adsb.is_degraded({"nac_p": 0, "alt_baro": "ground"}, 5) is None
    assert adsb.is_degraded({"nac_p": 0, "alt_baro": 30000, "seen_pos": 200}, 5) is None
    assert adsb.is_degraded({"alt_baro": 30000}, 5) is None
    from app.config import regions
    for r in regions().values():
        assert len(adsb.tiles(r["bbox"])) >= 1


def test_gdelt_date():
    assert gdelt.parse_seen("20261015T203000Z").hour == 20


def test_ais_dark_gap_stationary_identity():
    t = now()
    with SessionLocal() as s:
        # tanker underway in Hormuz strait, then silent for 2 h
        v = Vessel(mmsi=1, name="A", ship_type=80, lat=26.3, lon=56.3, sog=12.0, last_seen=t - timedelta(hours=2), first_seen=t - timedelta(hours=5),
                   positions=10, last_underway=t - timedelta(hours=2), last_underway_zone="Strait of Hormuz")
        # tanker drifting for 90 min in the strait, still reporting
        w = Vessel(mmsi=2, name="B", ship_type=84, lat=26.4, lon=56.4, sog=0.1, nav_status=0, last_seen=t - timedelta(minutes=2), first_seen=t - timedelta(hours=5),
                   positions=50, stationary_since=t - timedelta(minutes=90))
        # anchored tanker must not count; non-tanker must not count
        x = Vessel(mmsi=3, name="C", ship_type=80, lat=26.4, lon=56.4, sog=0.0, nav_status=1, last_seen=t, first_seen=t, positions=9, stationary_since=t - timedelta(hours=3))
        y = Vessel(mmsi=4, name="D", ship_type=70, lat=26.4, lon=56.4, sog=0.0, nav_status=0, last_seen=t, first_seen=t, positions=9, stationary_since=t - timedelta(hours=3))
        s.add_all([v, w, x, y]); s.commit()
        out = ais.detect_anomalies(s, t)
        kinds = sorted((e.meta["mmsi"], e.meta["kind"]) for e in out)
        assert kinds == [(1, "dark_gap"), (2, "stationary_in_chokepoint")]
        s.add_all(out); s.commit()
        assert ais.detect_anomalies(s, t) == []                       # deduplicated
        msg = {"MessageType": "ShipStaticData", "MetaData": {"MMSI": 2, "ShipName": "NEW NAME"}, "Message": {"ShipStaticData": {"Type": 84, "Name": "NEW NAME"}}}
        e = ais.apply_message(s, msg, t)
        assert e and e.meta["kind"] == "identity_mismatch"


def test_ais_position_message_updates_vessel():
    with SessionLocal() as s:
        msg = {"MessageType": "PositionReport", "MetaData": {"MMSI": 99, "ShipName": "X ", "latitude": 26.2, "longitude": 56.4},
               "Message": {"PositionReport": {"Sog": 11.2, "NavigationalStatus": 0}}}
        ais.apply_message(s, msg); s.commit()
        v = s.get(Vessel, 99)
        assert v.sog == 11.2 and v.last_underway_zone == "Strait of Hormuz"
