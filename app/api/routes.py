"""Read endpoints for the multi-page app."""
from datetime import timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import select

from .. import alerts as alerts_mod
from .. import auth, live
from ..collectors import ais, shadowbroker
from ..config import cfg, env, regions
from ..db import Alert, RawEvent, RiskSnapshot, SessionLocal, Signal, now

r = APIRouter()
iso = lambda d: d.isoformat() if d else None


class Login(BaseModel):
    password: str


@r.post("/auth/login")
def login(body: Login, request: Request, response: Response):
    auth.login(request, response, body.password)
    return {"ok": True}


@r.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(auth.COOKIE)
    return {"ok": True}


@r.get("/auth/me")
def me(request: Request):
    return {"auth_required": auth.enabled(), "authenticated": auth.authed(request)}


@r.get("/api/region/{region}")
def region_page(region: str, hours: int = Query(72, ge=1, le=336)):
    if region not in regions():
        raise HTTPException(404, "unknown region")
    t = now()
    with SessionLocal() as s:
        hist = list(s.scalars(select(RiskSnapshot).where(RiskSnapshot.region == region, RiskSnapshot.created_at >= t - timedelta(hours=hours)).order_by(RiskSnapshot.created_at)))
        cur = hist[-1] if hist else None
        sigs = list(s.scalars(select(Signal).where(Signal.region == region).order_by(Signal.created_at.desc()).limit(40)))
        news = list(s.scalars(select(RawEvent).where(RawEvent.region == region, RawEvent.event_type == "news_spike").order_by(RawEvent.timestamp.desc()).limit(25)))
        al = list(s.scalars(select(Alert).where(Alert.region == region).order_by(Alert.sent_at.desc()).limit(15)))
        rc = regions()[region]
        return {"region": region, "name": rc["name"], "multiplier": rc["multiplier"], "why": rc["why"], "bbox": rc["bbox"],
                "current": {"score": cur.score, "label": cur.label, "active_signals": cur.active_signals, "details": cur.details, "t": iso(cur.created_at)} if cur else None,
                "history": [{"t": iso(x.created_at), "score": x.score, "label": x.label} for x in hist][-1500:],
                "signals": [{"id": g.id, "type": g.signal_type, "score": g.score, "t": iso(g.window_end), "reason": g.evidence.get("reason", ""),
                             "baseline": g.evidence.get("baseline_per_hour_24h")} for g in sigs],
                "news": [{"title": e.meta.get("title"), "domain": e.meta.get("domain"), "url": e.meta.get("url"), "t": iso(e.timestamp)} for e in news],
                "alerts": [{"id": a.id, "label": a.label, "score": a.score, "t": iso(a.sent_at), "status": a.status, "kind": a.meta.get("kind", "risk")} for a in al]}


@r.get("/api/signals")
def signals(region: str | None = None, type: str | None = None, hours: int = Query(48, ge=1, le=336), limit: int = Query(200, ge=1, le=1000)):
    with SessionLocal() as s:
        q = select(Signal).where(Signal.created_at >= now() - timedelta(hours=hours)).order_by(Signal.created_at.desc()).limit(limit)
        if region:
            q = q.where(Signal.region == region)
        if type:
            q = q.where(Signal.signal_type == type)
        return [{"id": g.id, "type": g.signal_type, "region": g.region, "score": g.score, "t": iso(g.window_end),
                 "evidence": {k: v for k, v in g.evidence.items() if k != "event_ids"}} for g in s.scalars(q)]


_EN = {"the", "in", "of", "to", "and", "a", "for", "on", "at", "as", "is", "with", "by", "after", "over", "says", "attack", "war", "iran", "israel",
       "strike", "strikes", "news", "from", "us", "its", "are", "has", "will", "new", "killed", "military", "border", "oil", "sea", "gulf"}


def _english(t: str | None) -> bool:
    """Cheap language guard: GDELT event-file fallback has no language filter."""
    if not t:
        return False
    if sum(c.isascii() for c in t) / len(t) < 0.97:
        return False
    words = {w.strip(".,:;!?\"'()").lower() for w in t.split()}
    return len(words & _EN) >= 1


@r.get("/api/news")
def news(region: str | None = None, hours: int = Query(12, ge=1, le=72), limit: int = Query(100, ge=1, le=300)):
    with SessionLocal() as s:
        q = select(RawEvent).where(RawEvent.event_type == "news_spike", RawEvent.timestamp >= now() - timedelta(hours=hours)).order_by(RawEvent.timestamp.desc()).limit(limit)
        if region:
            q = q.where(RawEvent.region == region)
        return [{"title": e.meta.get("title"), "domain": e.meta.get("domain"), "url": e.meta.get("url"), "region": e.region, "t": iso(e.timestamp),
                 "feed": e.meta.get("feed_name")} for e in s.scalars(q) if _english(e.meta.get("title"))]


@r.get("/api/alerts")
def alerts_list(region: str | None = None, label: str | None = None, limit: int = Query(100, ge=1, le=500)):
    with SessionLocal() as s:
        q = select(Alert).order_by(Alert.sent_at.desc()).limit(limit)
        if region:
            q = q.where(Alert.region == region)
        if label:
            q = q.where(Alert.label == label.upper())
        return [{"id": a.id, "region": a.region, "label": a.label, "score": a.score, "t": iso(a.sent_at), "status": a.status,
                 "sent_to": a.sent_to, "kind": a.meta.get("kind", "risk"), "escalation": a.meta.get("escalation", False)} for a in s.scalars(q)]


@r.get("/api/settings")
def settings():
    c = cfg()
    return {"telegram": {"enabled": c["alerts"]["telegram_enabled"], "token_set": bool(env("TELEGRAM_BOT_TOKEN")),
                         "chat_set": bool(env("TELEGRAM_CHAT_ID")), "ready": alerts_mod.telegram_ready()},
            "llm_provider": env("LLM_PROVIDER", "none"), "ais_enabled": ais.enabled(), "shadowbroker_enabled": shadowbroker.enabled(),
            "live_layer": env("LIVE_LAYER", "1") == "1", "live_tiers_s": live.TIERS,
            "rules": c["rules"], "weights": c["weights"], "bands": c["risk_bands"], "alerts": c["alerts"],
            "regions": {k: {"name": v["name"], "multiplier": v["multiplier"], "bbox": v["bbox"], "why": v["why"]} for k, v in regions().items()},
            "chokepoints": c["chokepoints"], "retention_days": c["retention_days"]}


# ---- editable settings (admin only: the whole API is behind the login gate) ----
from .. import settings_store as ss  # noqa: E402


class SettingsPatch(BaseModel):
    changes: dict


def _need_admin(request: Request):
    if not auth.enabled():
        raise HTTPException(403, "Set ADMIN_PASSWORD to enable editing settings")
    if not auth.authed(request):
        raise HTTPException(401, "login required")


@r.get("/api/settings/editable")
def settings_editable():
    return {"fields": ss.editable_view(), "log": ss.changelog(60), "editing_enabled": auth.enabled()}


@r.put("/api/settings")
def settings_update(body: SettingsPatch, request: Request):
    _need_admin(request)
    try:
        done = ss.apply_changes(body.changes)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"applied": done}


@r.post("/api/settings/reset")
def settings_reset(request: Request):
    _need_admin(request)
    return {"reset": ss.reset_all()}


# ---- Strike Guard: risk-adjusted iron condor planner (real NIFTY spot + India VIX + this app's score) ----
import math  # noqa: E402
import time as _time  # noqa: E402

import httpx  # noqa: E402

from ..collectors import UA  # noqa: E402
from ..collectors.market_collector import yahoo_move  # noqa: E402
from ..config import LABEL_RANK  # noqa: E402

_sg: dict = {"t": 0, "d": None}


def _quotes():
    if _sg["d"] and _time.time() - _sg["t"] < 60:
        return _sg["d"]
    with httpx.Client(timeout=15, headers={"User-Agent": UA}, follow_redirects=True) as c:
        out = {}
        for k, sym in (("nifty", "^NSEI"), ("vix", "^INDIAVIX")):
            try:
                out[k] = yahoo_move(c, sym)
            except Exception as e:  # noqa: BLE001
                out[k] = {"error": str(e)[:100]}
    _sg.update(t=_time.time(), d=out)
    return out


@r.get("/api/strikeguard")
def strikeguard(dte: int = Query(7, ge=1, le=45)):
    q = _quotes()
    if "error" in q["nifty"] or "error" in q["vix"]:
        raise HTTPException(503, "Market data is unavailable right now: " + (q["nifty"].get("error") or q["vix"].get("error")))
    c = cfg()["strike_guard"]
    with SessionLocal() as s:
        from ..main import latest_snaps
        snaps = latest_snaps(s)
        top = max(snaps, key=lambda x: x.score) if snaps else None
    label = top.label if top else "NORMAL"
    spot, vix = q["nifty"]["last"], q["vix"]["last"]
    sigma = spot * vix / 100 * math.sqrt(dte / 365)
    step, wing = c["strike_step"], c["wing_width"]
    rnd = lambda x: int(round(x / step) * step)
    def build(k):
        sc, sp = rnd(spot + k * sigma), rnd(spot - k * sigma)
        return {"k": k, "short_call": sc, "long_call": sc + wing, "short_put": sp, "long_put": sp - wing,
                "call_dist_pct": round((sc - spot) / spot * 100, 2), "put_dist_pct": round((spot - sp) / spot * 100, 2)}
    k = c["sigma_multiple"][label]
    base, adj = build(c["sigma_multiple"]["NORMAL"]), build(k)
    age = (now() - q["nifty"]["bar_time"]).total_seconds() / 60
    return {"spot": spot, "spot_time": iso(q["nifty"]["bar_time"]), "spot_age_min": round(age),
            "vix": vix, "vix_time": iso(q["vix"]["bar_time"]), "dte": dte, "sigma_pts": round(sigma, 1), "sigma_pct": round(sigma / spot * 100, 2),
            "band": label, "score": top.score if top else 0, "region": top.region if top else None,
            "region_name": regions()[top.region]["name"] if top else None, "baseline": base, "adjusted": adj,
            "widen_pts": {"call": adj["short_call"] - base["short_call"], "put": base["short_put"] - adj["short_put"]},
            "stand_aside": label == "AVOID", "multiples": c["sigma_multiple"]}


# ---- Scenario Lab: hypothetical shocks run through the app's own scoring engine ----
from .. import scoring  # noqa: E402

SCENARIOS = {
    "hormuz_closure": {"name": "Strait of Hormuz disruption", "region": "hormuz",
                       "signals": ["gps_jamming_cluster", "military_spike", "tanker_dark_gap", "conflict_news_spike", "crude_confirmation", "vix_confirmation"], "vix_pts": 6,
                       "story": "Interference, naval air activity and tanker anomalies all show up together, news volume jumps, Brent and India VIX react."},
    "red_sea_halt": {"name": "Red Sea shipping halt", "region": "red_sea",
                     "signals": ["tanker_dark_gap", "conflict_news_spike", "military_spike", "crude_confirmation"], "vix_pts": 3,
                     "story": "Tanker anomalies near Bab-el-Mandeb with a news spike and a crude move."},
    "india_pak_escalation": {"name": "India-Pakistan escalation", "region": "india_pak",
                             "signals": ["gps_jamming_cluster", "military_spike", "conflict_news_spike", "vix_confirmation"], "vix_pts": 5,
                             "story": "Military flights and GPS degradation along the border with heavy news flow and a VIX jump."},
    "sanctions_shock": {"name": "Sanctions / market-only shock", "region": "hormuz",
                        "signals": ["crude_confirmation", "vix_confirmation"], "vix_pts": 4,
                        "story": "A sanctions headline moves Brent and India VIX, but no physical or news signal shows it in the feeds. The engine counts market moves only as confirmation, so it should stay quiet."},
}


class ScenarioIn(BaseModel):
    region: str
    signals: list[str]
    vix_pts: float = 0


class _S:  # minimal stand-in for a Signal row, used only inside the pure scoring function
    def __init__(self, t):
        self.signal_type = t


@r.get("/api/scenario/presets")
def scenario_presets():
    return SCENARIOS


@r.post("/api/scenario")
def scenario(body: ScenarioIn):
    if body.region not in regions():
        raise HTTPException(404, "unknown region")
    w = cfg()["weights"]
    bad = [t for t in body.signals if t not in w]
    if bad:
        raise HTTPException(422, f"unknown signal {bad[0]}")
    if not -10 <= body.vix_pts <= 40:
        raise HTTPException(422, "VIX shock must be between -10 and 40 points")
    with SessionLocal() as s:
        cur = scoring.active_signals(s, body.region, now())
        before = scoring.compute(cur, body.region)
        merged = dict(cur)
        added = []
        for t in body.signals:
            if t not in merged:
                merged[t] = _S(t)
                added.append(t)
        after = scoring.compute(merged, body.region)
    out = {"region": body.region, "region_name": regions()[body.region]["name"], "added": added, "already_active": [t for t in body.signals if t not in added],
           "before": {k: before[k] for k in ("score", "label", "signal_types", "quality", "alert_candidate")},
           "after": {k: after[k] for k in ("score", "label", "signal_types", "quality", "alert_candidate", "contributions", "multiplier")},
           "weights": w, "strikes": None}
    try:
        q = _quotes()
        if "error" not in q["nifty"] and "error" not in q["vix"]:
            g = cfg()["strike_guard"]
            spot, vix0 = q["nifty"]["last"], q["vix"]["last"]
            vix1 = vix0 + body.vix_pts
            def build(label, vix):
                sg = spot * vix / 100 * math.sqrt(7 / 365)
                k = g["sigma_multiple"][label]
                st = g["strike_step"]
                rd = lambda x: int(round(x / st) * st)
                return {"label": label, "vix": round(vix, 2), "sigma_pts": round(sg), "short_call": rd(spot + k * sg), "short_put": rd(spot - k * sg), "k": k}
            out["strikes"] = {"spot": round(spot), "now": build(before["label"], vix0), "scenario": build(after["label"], vix1)}
    except Exception:  # noqa: BLE001
        pass
    return out


# ---- Strike calibration backtest: real NIFTY + India VIX daily history (Yahoo, 5 years) ----
_bt: dict = {"t": 0, "d": None}


def _history():
    if _bt["d"] and _time.time() - _bt["t"] < 6 * 3600:
        return _bt["d"]
    out = {}
    with httpx.Client(timeout=25, headers={"User-Agent": UA}, follow_redirects=True) as c:
        for k, sym in (("n", "^NSEI"), ("v", "^INDIAVIX")):
            res = c.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=5y")
            res.raise_for_status()
            j = res.json()["chart"]["result"][0]
            q = j["indicators"]["quote"][0]
            out[k] = {t: (q["close"][i], q["high"][i], q["low"][i]) for i, t in enumerate(j["timestamp"]) if q["close"][i] is not None}
    _bt.update(t=_time.time(), d=out)
    return out


def _day(ts):
    from datetime import datetime as _dt
    return _dt.fromtimestamp(ts + 19800, timezone.utc).strftime("%Y-%m-%d")   # IST date


@r.get("/api/backtest")
def backtest(hold_days: int = Query(5, ge=1, le=10)):
    try:
        h = _history()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, "Historical data is unavailable right now: " + str(e)[:80])
    nd = {_day(t): v for t, v in h["n"].items()}
    vd = {_day(t): v[0] for t, v in h["v"].items()}
    days = sorted(d for d in nd if d in vd)
    mults = list(cfg()["strike_guard"]["sigma_multiple"].values())
    rows = []
    for i in range(0, len(days) - hold_days, hold_days):     # non-overlapping windows
        d0 = days[i]
        win = [nd[d] for d in days[i + 1:i + 1 + hold_days]]
        spot, vix = nd[d0][0], vd[d0]
        sig = vix / 100 * math.sqrt(7 / 365)                  # fractional 1-sigma move over 7 calendar days
        close_mv = win[-1][0] / spot - 1
        up = max(w[1] for w in win if w[1]) / spot - 1
        dn = min(w[2] for w in win if w[2]) / spot - 1
        rows.append({"d": d0, "end": days[i + hold_days], "vix": round(vix, 2), "sigma": sig, "close": close_mv, "up": up, "dn": dn})
    if not rows:
        raise HTTPException(503, "Not enough history")
    def stats(rs, k):
        n = len(rs)
        cl = sum(abs(x["close"]) > k * x["sigma"] for x in rs)
        tc = sum((x["up"] > k * x["sigma"]) or (-x["dn"] > k * x["sigma"]) for x in rs)
        return {"k": k, "n": n, "close_breach": cl, "close_pct": round(cl / n * 100, 1) if n else None, "touch_breach": tc, "touch_pct": round(tc / n * 100, 1) if n else None}
    vs = sorted(x["vix"] for x in rows)
    hi = vs[int(len(vs) * 2 / 3)]
    hi_rows = [x for x in rows if x["vix"] >= hi]
    worst = sorted(rows, key=lambda x: -max(abs(x["close"]) / x["sigma"], 0))[:8]
    return {"hold_days": hold_days, "windows": len(rows), "from": rows[0]["d"], "to": rows[-1]["end"], "source": "Yahoo Finance daily ^NSEI and ^INDIAVIX",
            "all": [stats(rows, k) for k in mults], "high_vix": {"threshold": round(hi, 1), "n": len(hi_rows), "stats": [stats(hi_rows, k) for k in mults]},
            "worst": [{"start": x["d"], "end": x["end"], "vix": x["vix"], "move_pct": round(x["close"] * 100, 2), "sigma_pct": round(x["sigma"] * 100, 2), "multiple": round(abs(x["close"]) / x["sigma"], 2)} for x in worst]}


# ---- Overnight gap risk: real NIFTY opens vs previous close (Yahoo, 5 years) ----
_gp: dict = {"t": 0, "d": None}


def _gap_history():
    if _gp["d"] and _time.time() - _gp["t"] < 6 * 3600:
        return _gp["d"]
    with httpx.Client(timeout=25, headers={"User-Agent": UA}, follow_redirects=True) as c:
        out = {}
        for k, sym in (("n", "^NSEI"), ("v", "^INDIAVIX")):
            res = c.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=5y")
            res.raise_for_status()
            j = res.json()["chart"]["result"][0]
            q = j["indicators"]["quote"][0]
            out[k] = [(t, q["open"][i], q["close"][i]) for i, t in enumerate(j["timestamp"]) if q["open"][i] and q["close"][i]]
    _gp.update(t=_time.time(), d=out)
    return out


def compute_gaps(nifty, vix):
    """nifty/vix: lists of (ts, open, close) sorted by time. Gap = today's open / previous close - 1."""
    vd = {_day(t): c for t, o, c in vix}
    rows = []
    for i in range(1, len(nifty)):
        t, o, _ = nifty[i]
        pc = nifty[i - 1][2]
        d = _day(t)
        pd_ = _day(nifty[i - 1][0])
        rows.append({"d": d, "gap": o / pc - 1, "wd": __import__("datetime").datetime.strptime(d, "%Y-%m-%d").weekday(), "vix_prev": vd.get(pd_)})
    if not rows:
        return None
    a = sorted(abs(x["gap"]) for x in rows)
    n = len(a)
    pct = lambda p: round(a[min(n - 1, int(n * p))] * 100, 2)
    thr = [0.5, 1.0, 1.5, 2.0]
    names = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    bywd = []
    for w in range(5):
        g = [abs(x["gap"]) for x in rows if x["wd"] == w]
        bywd.append({"day": names[w], "n": len(g), "avg_pct": round(sum(g) / len(g) * 100, 3) if g else None,
                     "over1": sum(x > 0.01 for x in g)})
    vs = sorted(x["vix_prev"] for x in rows if x["vix_prev"])
    hi = vs[int(len(vs) * 2 / 3)] if vs else None
    def grp(sel):
        g = [abs(x["gap"]) for x in sel]
        return {"n": len(g), "avg_pct": round(sum(g) / len(g) * 100, 3) if g else None,
                "over1_pct": round(sum(x > 0.01 for x in g) / len(g) * 100, 1) if g else None}
    hist = []
    for lo, hi_b in ((-9, -2), (-2, -1), (-1, -0.5), (-0.5, 0), (0, 0.5), (0.5, 1), (1, 2), (2, 9)):
        hist.append({"lo": lo, "hi": hi_b, "n": sum(lo <= x["gap"] * 100 < hi_b for x in rows)})
    worst = sorted(rows, key=lambda x: -abs(x["gap"]))[:8]
    return {"days": n, "from": rows[0]["d"], "to": rows[-1]["d"],
            "abs_percentiles": {"p50": pct(0.5), "p90": pct(0.9), "p95": pct(0.95), "p99": pct(0.99)},
            "exceed": [{"pct": t, "n": sum(x > t / 100 for x in a), "share": round(sum(x > t / 100 for x in a) / n * 100, 1)} for t in thr],
            "by_weekday": bywd, "hist": hist,
            "vix_split": {"threshold": round(hi, 1) if hi else None, "high": grp([x for x in rows if x["vix_prev"] and x["vix_prev"] >= hi]),
                          "low": grp([x for x in rows if x["vix_prev"] and x["vix_prev"] < hi])},
            "worst": [{"date": x["d"], "gap_pct": round(x["gap"] * 100, 2), "vix_prev": round(x["vix_prev"], 1) if x["vix_prev"] else None} for x in worst]}


@r.get("/api/gaps")
def gaps():
    try:
        h = _gap_history()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, "Historical data is unavailable right now: " + str(e)[:80])
    out = compute_gaps(h["n"], h["v"])
    if not out:
        raise HTTPException(503, "Not enough history")
    out["source"] = "Yahoo Finance daily ^NSEI and ^INDIAVIX (open vs previous close)"
    return out


# ---- Risk now vs usual: percentile of the current score within this agent's own stored snapshot history ----
MIN_READINGS, MIN_HOURS = 100, 24


def context_stats(rows, current):
    """rows: list of (created_at, score) newest first. Honest baseline: needs >= 100 readings over >= 24 h."""
    n = len(rows)
    if n == 0:
        return {"n": 0, "hours": 0, "ready": False}
    span_h = (rows[0][0] - rows[-1][0]).total_seconds() / 3600
    scores = sorted(x[1] for x in rows)
    ready = n >= MIN_READINGS and span_h >= MIN_HOURS
    out = {"n": n, "hours": round(span_h, 1), "ready": ready, "current": current}
    if ready:
        out.update(percentile=round(sum(s <= current for s in scores) / n * 100),
                   median=scores[n // 2], p90=scores[min(n - 1, int(n * 0.9))], max=scores[-1],
                   share_zero=round(sum(s == 0 for s in scores) / n * 100))
    return out


@r.get("/api/context")
def risk_context():
    out = {"min_readings": MIN_READINGS, "min_hours": MIN_HOURS, "regions": []}
    since = now() - timedelta(days=30)
    with SessionLocal() as s:
        for key, rc in regions().items():
            rows = [(x.created_at, x.score) for x in s.scalars(
                select(RiskSnapshot).where(RiskSnapshot.region == key, RiskSnapshot.created_at >= since)
                .order_by(RiskSnapshot.created_at.desc()).limit(20000))]
            st = context_stats(rows, rows[0][1] if rows else 0)
            st.update(region=key, name=rc.get("name", key))
            out["regions"].append(st)
    return out
