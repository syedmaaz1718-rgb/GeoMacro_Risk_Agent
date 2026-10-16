from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)


def test_health_and_empty_state():
    assert c.get("/health").json()["status"] == "ok"
    r = c.get("/risk/latest").json()
    assert r["overall_risk"] == "NORMAL" and r["regions"] == []
    assert c.get("/alerts/recent").json() == []
    assert c.get("/risk/region/nowhere").status_code == 404
    assert c.get("/").status_code == 200


def test_test_alert_and_feedback_and_rate_limit():
    a = c.post("/alerts/test").json()
    assert a["status"] == "logged" and a["kind"] == "test"
    assert c.post("/alerts/test").status_code == 429
    fb = c.post("/feedback", json={"alert_id": a["id"], "user_feedback": "useful"})
    assert fb.status_code == 200
    assert c.post("/feedback", json={"alert_id": a["id"], "user_feedback": "bogus"}).status_code == 422
    assert c.get(f"/alerts/{a['id']}").json()["feedback"][0]["feedback"] == "useful"
    assert c.get("/api/overview").status_code == 200 and c.get("/api/map").status_code == 200
    assert "region" in c.get("/alerts.csv").text


def test_auth_gate(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    cc = TestClient(app)
    assert cc.get("/api/overview").status_code == 401
    assert cc.get("/health").status_code == 200 and cc.get("/").status_code == 200
    assert cc.post("/auth/login", json={"password": "bad"}).status_code == 401
    assert cc.post("/auth/login", json={"password": "s3cret"}).status_code == 200
    assert cc.get("/api/overview").status_code == 200
    assert cc.get("/auth/me").json() == {"auth_required": True, "authenticated": True}
    assert TestClient(app).get("/api/settings").status_code == 401


def test_new_endpoints():
    for u in ("/api/settings", "/api/signals", "/api/news", "/api/alerts", "/api/region/hormuz", "/api/live"):
        assert c.get(u).status_code == 200, u
    assert c.get("/api/region/zzz").status_code == 404


def test_settings_edit_log_reset(monkeypatch):
    from app import settings_store as ss
    from app.config import cfg
    monkeypatch.setenv("ADMIN_PASSWORD", "pw")

    assert c.post("/auth/login", json={"password": "pw"}).status_code == 200
    d = c.get("/api/settings/editable").json()
    assert any(f["key"] == "weights.military_spike" for f in d["fields"])
    r = c.put("/api/settings", json={"changes": {"weights.military_spike": 30, "bands.high": 60}})
    assert r.status_code == 200 and len(r.json()["applied"]) == 2
    assert cfg()["weights"]["military_spike"] == 30 and cfg()["risk_bands"]["high"][0] == 60 and cfg()["risk_bands"]["caution"][1] == 59
    bad = c.put("/api/settings", json={"changes": {"weights.military_spike": 500}})
    assert bad.status_code == 422
    bad = c.put("/api/settings", json={"changes": {"bands.caution": 90}})
    assert bad.status_code == 422
    assert c.put("/api/settings", json={"changes": {"nope": 1}}).status_code == 422
    log = c.get("/api/settings/editable").json()["log"]
    assert log[0]["old"] is not None and {x["key"] for x in log} >= {"weights.military_spike", "bands.high"}
    assert c.post("/api/settings/reset").status_code == 200
    assert cfg()["weights"]["military_spike"] == 20 and cfg()["risk_bands"]["high"][0] == 56
    assert c.get("/api/settings/editable").json()["log"][0]["note"] == "reset"


def test_strikeguard_math(monkeypatch):
    from datetime import datetime, timezone
    import app.api.routes as ax
    bt = datetime.now(timezone.utc)
    monkeypatch.setattr(ax, "_quotes", lambda: {"nifty": {"last": 24000.0, "bar_time": bt}, "vix": {"last": 15.0, "bar_time": bt}})
    d = c.get("/api/strikeguard?dte=7").json()
    assert abs(d["sigma_pts"] - 24000 * 0.15 * (7 / 365) ** 0.5) < 0.2
    assert d["adjusted"]["short_call"] >= d["baseline"]["short_call"] and d["adjusted"]["short_put"] <= d["baseline"]["short_put"]
    assert d["adjusted"]["short_call"] % 50 == 0 and d["adjusted"]["long_call"] - d["adjusted"]["short_call"] == 100


def test_scenario_engine():
    r = c.post("/api/scenario", json={"region": "hormuz", "signals": ["gps_jamming_cluster", "military_spike", "tanker_dark_gap", "conflict_news_spike", "crude_confirmation", "vix_confirmation"], "vix_pts": 6})
    assert r.status_code == 200
    j = r.json()
    assert j["before"]["score"] == 0 and j["after"]["score"] == 100 and j["after"]["label"] == "AVOID" and j["after"]["alert_candidate"]
    only_mkt = c.post("/api/scenario", json={"region": "hormuz", "signals": ["crude_confirmation", "vix_confirmation"]}).json()
    assert only_mkt["after"]["score"] == 0 and not only_mkt["after"]["alert_candidate"]   # independence rule
    assert c.post("/api/scenario", json={"region": "x", "signals": []}).status_code == 404
    assert c.post("/api/scenario", json={"region": "hormuz", "signals": ["nope"]}).status_code == 422


def test_backtest_math(monkeypatch):
    import app.api.routes as ax
    from datetime import datetime, timedelta, timezone
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
    n, v = {}, {}
    for i in range(60):
        ts = t0 + i * 86400
        p = 100 + i
        n[ts] = (p, p + 1, p - 1)
        v[ts] = (15.0, 15.0, 15.0)
    monkeypatch.setattr(ax, "_history", lambda: {"n": n, "v": v})
    d = c.get("/api/backtest?hold_days=5").json()
    assert d["windows"] >= 10 and d["all"][0]["n"] == d["windows"]
    assert d["all"][0]["touch_pct"] >= d["all"][0]["close_pct"]
    assert d["all"][-1]["touch_pct"] <= d["all"][0]["touch_pct"]   # wider strikes never breach more


def test_gap_math():
    import app.api.routes as ax
    D = 86400
    t0 = 1_700_000_000
    nifty = [(t0, 100, 100), (t0 + D, 99, 100), (t0 + 2 * D, 102.5, 101), (t0 + 3 * D, 101, 101)]
    vix = [(t0 + i * D, 15, 15) for i in range(4)]
    g = ax.compute_gaps(nifty, vix)
    assert g["days"] == 3
    assert [round(x["gap_pct"], 2) for x in g["worst"]] == [2.5, -1.0, 0.0]
    assert g["exceed"][1]["n"] == 2 and g["hist"][0]["n"] + sum(h["n"] for h in g["hist"][1:]) == 3


def test_context_baseline_honesty():
    from datetime import datetime, timedelta, timezone
    import app.api.routes as ax
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    short = [(t - timedelta(minutes=5 * i), 10) for i in range(30)]
    assert ax.context_stats(short, 10)["ready"] is False            # 30 readings, 2.5 h: no percentile claimed
    long = [(t - timedelta(minutes=15 * i), 0 if i % 2 else 20) for i in range(200)]   # 200 readings over ~50 h
    r = ax.context_stats(long, 20)
    assert r["ready"] and r["percentile"] == 100 and r["share_zero"] == 50 and r["median"] == 20
