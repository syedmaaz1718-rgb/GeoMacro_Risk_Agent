import asyncio
import os
import logging
import time
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, select, text

from . import alerts as alerts_mod
from . import auth, live, scheduler as pipeline
from .api.routes import r as extra_router
from .collectors import ais, shadowbroker
from .config import LABEL_RANK, cfg, env, regions
from .db import Alert, Feedback, FeedRun, RawEvent, RiskSnapshot, SessionLocal, Signal, init_db, now

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # never log URLs (Telegram token lives in the URL)
logging.getLogger("httpcore").setLevel(logging.WARNING)
STATIC = Path(__file__).parent / "static"
STARTED = time.time()
_sched = {"s": None}
_last_test = {"t": 0.0}


@asynccontextmanager
async def lifespan(app):
    init_db()
    if env("GEOMACRO_NO_SCHEDULER") != "1":
        _sched["s"] = pipeline.start_scheduler()
        pipeline.start_ais_listener()
        if env('LIVE_LAYER', '1') == '1':
            live.start()
    yield
    if _sched["s"]:
        _sched["s"].shutdown(wait=False)


app = FastAPI(title="Geo-Macro Risk Agent", version="1.0.0", lifespan=lifespan)
app.middleware("http")(auth.gate)
app.include_router(extra_router)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def admin(request: Request):
    if not auth.authed(request):
        raise HTTPException(401, "login required")


def iso(d):
    return d.isoformat() if d else None


def snap_dict(x):
    return {"region": x.region, "name": regions()[x.region]["name"], "score": x.score, "label": x.label,
            "active_signals": x.active_signals, "details": x.details, "timestamp": iso(x.created_at)}


def latest_snaps(s):
    out = []
    for r in regions():
        x = s.scalars(select(RiskSnapshot).where(RiskSnapshot.region == r).order_by(RiskSnapshot.created_at.desc()).limit(1)).first()
        if x:
            out.append(x)
    return out


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    ok = True
    try:
        with SessionLocal() as s:
            s.execute(text("select 1"))
    except Exception:  # noqa: BLE001
        ok = False
    return {"status": "ok" if ok else "degraded", "uptime_s": int(time.time() - STARTED)}


@app.get("/risk/latest")
def risk_latest():
    with SessionLocal() as s:
        snaps = latest_snaps(s)
        if not snaps:
            return {"timestamp": None, "overall_risk": "NORMAL", "max_score": 0, "regions": [], "note": "warming up - first scoring run pending"}
        top = max(snaps, key=lambda x: (LABEL_RANK[x.label], x.score))
        return {"timestamp": iso(max(x.created_at for x in snaps)), "overall_risk": top.label, "max_score": top.score,
                "regions": [{"region": x.region, "score": x.score, "label": x.label} for x in snaps]}


@app.get("/risk/region/{region}")
def risk_region(region: str, hours: int = Query(24, ge=1, le=168)):
    if region not in regions():
        raise HTTPException(404, "unknown region")
    with SessionLocal() as s:
        cur = s.scalars(select(RiskSnapshot).where(RiskSnapshot.region == region).order_by(RiskSnapshot.created_at.desc()).limit(1)).first()
        hist = list(s.scalars(select(RiskSnapshot).where(RiskSnapshot.region == region, RiskSnapshot.created_at >= now() - timedelta(hours=hours)).order_by(RiskSnapshot.created_at)))
        return {"region": region, "name": regions()[region]["name"], "multiplier": regions()[region]["multiplier"],
                "bbox": regions()[region]["bbox"], "current": snap_dict(cur) if cur else None,
                "history": [{"t": iso(x.created_at), "score": x.score, "label": x.label} for x in hist]}


def alert_dict(a, full=False):
    d = {"id": a.id, "region": a.region, "score": a.score, "label": a.label, "message": a.message,
         "sent_to": a.sent_to, "sent_at": iso(a.sent_at), "status": a.status, "kind": a.meta.get("kind", "risk")}
    if full:
        d["metadata"] = a.meta
    return d


@app.get("/alerts/recent")
def alerts_recent(limit: int = Query(20, ge=1, le=200)):
    with SessionLocal() as s:
        return [alert_dict(a) for a in s.scalars(select(Alert).order_by(Alert.sent_at.desc()).limit(limit))]


@app.get("/alerts/{alert_id}")
def alert_explain(alert_id: str):
    """Explainability: the alert, the signals behind it and the raw evidence events."""
    with SessionLocal() as s:
        a = s.get(Alert, alert_id)
        if not a:
            raise HTTPException(404, "alert not found")
        evidence = []
        for sig in a.meta.get("signals", []):
            row = s.get(Signal, sig.get("signal_id")) if sig.get("signal_id") else None
            if row:
                ids = row.evidence.get("event_ids", [])[:12]
                evs = list(s.scalars(select(RawEvent).where(RawEvent.id.in_(ids)))) if ids else []
                evidence.append({"signal": sig["type"], "score": row.score, "evidence": {k: v for k, v in row.evidence.items() if k != "event_ids"},
                                 "events": [{"source": e.source, "type": e.event_type, "time": iso(e.timestamp), "lat": e.lat, "lon": e.lon,
                                             "detail": e.meta.get("title") or e.meta.get("callsign") or e.meta.get("hex") or e.meta.get("symbol")} for e in evs]})
        fb = [{"feedback": f.user_feedback, "notes": f.notes, "at": iso(f.created_at)} for f in s.scalars(select(Feedback).where(Feedback.alert_id == alert_id))]
        return {**alert_dict(a, True), "evidence": evidence, "feedback": fb}


class TestAlert(BaseModel):
    region: str = "hormuz"


@app.post("/alerts/test", dependencies=[Depends(admin)])
def alerts_test(body: TestAlert | None = None):
    if time.time() - _last_test["t"] < 30:
        raise HTTPException(429, "test alerts are limited to one per 30 seconds")
    _last_test["t"] = time.time()
    with SessionLocal() as s:
        msg = "🧪 TEST ALERT - Geo-Macro Risk Agent\nThis confirms the alert channel works. No market risk is implied."
        a = alerts_mod.store_alert(s, (body.region if body else "hormuz"), 0, "NORMAL", msg, {"kind": "test", "test": True})
        return alert_dict(a)


class FeedbackIn(BaseModel):
    alert_id: str
    user_feedback: str
    market_reaction: str = ""
    notes: str = ""


@app.post("/feedback", dependencies=[Depends(admin)])
def feedback(body: FeedbackIn):
    if body.user_feedback not in ("useful", "false_positive", "too_late", "missed_event"):
        raise HTTPException(422, "user_feedback must be useful, false_positive, too_late or missed_event")
    with SessionLocal() as s:
        if not s.get(Alert, body.alert_id):
            raise HTTPException(404, "alert not found")
        f = Feedback(**body.model_dump())
        s.add(f)
        s.commit()
        return {"id": f.id, "status": "saved"}


@app.get("/signals/recent")
def signals_recent(limit: int = Query(50, ge=1, le=300), region: str | None = None):
    with SessionLocal() as s:
        q = select(Signal).order_by(Signal.created_at.desc()).limit(limit)
        if region:
            q = q.where(Signal.region == region)
        return [{"id": g.id, "type": g.signal_type, "region": g.region, "score": g.score, "window_end": iso(g.window_end),
                 "evidence": {k: v for k, v in g.evidence.items() if k != "event_ids"}} for g in s.scalars(q)]


@app.get("/api/overview")
def overview():
    """Everything the dashboard needs in one call."""
    with SessionLocal() as s:
        snaps = latest_snaps(s)
        t = now()
        regs = []
        for x in snaps:
            hist = list(s.scalars(select(RiskSnapshot.score).where(RiskSnapshot.region == x.region, RiskSnapshot.created_at >= t - timedelta(hours=24)).order_by(RiskSnapshot.created_at)))
            d = snap_dict(x)
            d.update(multiplier=regions()[x.region]["multiplier"], why=regions()[x.region]["why"], spark=hist[-288:],
                     bbox=regions()[x.region]["bbox"])
            # live counts, last 60 min
            since = t - timedelta(minutes=60)
            counts = {}
            for etype, key in (("gps_jamming", "gps_aircraft"), ("military_aircraft", "military_aircraft"), ("news_spike", "news_articles"), ("ais_dark_gap", "ais_anomalies")):
                since_e = since if etype != "ais_dark_gap" else t - timedelta(hours=2)
                rows = s.scalars(select(RawEvent).where(RawEvent.region == x.region, RawEvent.event_type == etype, RawEvent.timestamp >= since_e))
                keys = {(e.meta.get("hex") or e.meta.get("key") or e.id) for e in rows}
                counts[key] = len(keys)
            d["live_counts"] = counts
            regs.append(d)
        top = max(snaps, key=lambda x: (LABEL_RANK[x.label], x.score)) if snaps else None
        market = {}
        for etype, name in (("crude_move", "brent"), ("vix_move", "india_vix")):
            e = s.scalars(select(RawEvent).where(RawEvent.event_type == etype).order_by(RawEvent.timestamp.desc()).limit(1)).first()
            if e:
                market[name] = {**e.meta, "observed_at": iso(e.timestamp)}
        alerts = [alert_dict(a) for a in s.scalars(select(Alert).order_by(Alert.sent_at.desc()).limit(8))]
        headlines = [{"title": e.meta.get("title"), "domain": e.meta.get("domain"), "url": e.meta.get("url"), "region": e.region, "time": iso(e.timestamp)}
                     for e in s.scalars(select(RawEvent).where(RawEvent.event_type == "news_spike").order_by(RawEvent.timestamp.desc()).limit(12))]
        return {"now": iso(t), "overall": top.label if top else "NORMAL", "max_score": top.score if top else 0,
                "regions": regs, "market": market, "alerts": alerts, "headlines": headlines,
                "telegram": alerts_mod.telegram_ready(), "ais_enabled": ais.enabled(),
                "feeds": feeds_status(s), "thresholds": cfg()["rules"], "weights": cfg()["weights"], "bands": cfg()["risk_bands"]}


@app.get("/api/live")
def api_live():
    """Cached live aircraft + recent vessels. Cheap: the browser may poll every few seconds."""
    from .db import Vessel
    with SessionLocal() as s:
        vs = []
        if ais.enabled():
            for v in s.scalars(select(Vessel).where(Vessel.last_seen >= now() - timedelta(minutes=15), Vessel.lat.is_not(None)).limit(2000)):
                vs.append({"mmsi": v.mmsi, "name": v.name, "type": v.ship_type, "lat": v.lat, "lon": v.lon, "sog": v.sog,
                           "tanker": v.ship_type is not None and 80 <= v.ship_type <= 89, "seen": iso(v.last_seen)})
    return {"now": time.time(), "aircraft": live.snapshot(), "vessels": vs, "sweeps": live.STATUS, "ais": ais.STATE if ais.enabled() else None}


@app.get("/api/map")
def map_points(hours: int = Query(2, ge=1, le=24)):
    with SessionLocal() as s:
        rows = s.scalars(select(RawEvent).where(RawEvent.event_type.in_(["gps_jamming", "military_aircraft", "ais_dark_gap"]),
                                                RawEvent.timestamp >= now() - timedelta(hours=hours), RawEvent.lat.is_not(None)).order_by(RawEvent.timestamp.desc()).limit(1500))
        pts = [{"type": e.event_type, "lat": e.lat, "lon": e.lon, "region": e.region, "time": iso(e.timestamp),
                "label": e.meta.get("callsign") or e.meta.get("hex") or "", "severity": e.severity} for e in rows]
        return {"points": pts, "regions": {k: v["bbox"] for k, v in regions().items()}}


def feeds_status(s):
    out = []
    names = ["adsb", "gdelt", "market"] + (["ais"] if ais.enabled() else []) + (["shadowbroker"] if shadowbroker.enabled() else [])
    for n in names:
        last = s.scalars(select(FeedRun).where(FeedRun.feed == n).order_by(FeedRun.started_at.desc()).limit(1)).first()
        ok_last = s.scalars(select(FeedRun).where(FeedRun.feed == n, FeedRun.ok.is_(True)).order_by(FeedRun.started_at.desc()).limit(1)).first()
        recent = list(s.scalars(select(FeedRun).where(FeedRun.feed == n, FeedRun.started_at >= now() - timedelta(hours=24))))
        out.append({"feed": n, "last_run": iso(last.started_at) if last else None, "last_ok": iso(ok_last.started_at) if ok_last else None,
                    "ok": bool(last and last.ok), "events_last_run": last.events if last else 0, "duration_s": last.duration_s if last else None,
                    "error": last.detail if last and not last.ok else "",
                    "success_rate_24h": round(sum(1 for r in recent if r.ok) / len(recent) * 100) if recent else None})
    if ais.enabled():
        st = ais.STATE
        note = st["error"]
        if st.get("blocked") and not st["connected"]:
            retry = f"; next retry at {st['next_retry_at']}" if st.get("next_retry_at") else ""
            note = f"aisstream is rate-limiting this server's IP (HTTP 429). Backing off quietly{retry}. New API key may help; if not, the host's IP range is blocked."
        out.append({"feed": "ais_stream", "ok": st["connected"], "messages": st["messages"],
                    "last_message": st["last_message"], "error": note, "blocked": st.get("blocked", False),
                    "next_retry_at": st.get("next_retry_at")})
    return out


@app.get("/feeds/status")
def feeds():
    with SessionLocal() as s:
        return feeds_status(s)


@app.get("/alerts.csv", response_class=PlainTextResponse)
def alerts_csv():
    import csv, io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["sent_at", "region", "label", "score", "status", "sent_to", "id"])
    with SessionLocal() as s:
        for a in s.scalars(select(Alert).order_by(Alert.sent_at.desc()).limit(1000)):
            w.writerow([iso(a.sent_at), a.region, a.label, a.score, a.status, a.sent_to, a.id])
    return buf.getvalue()


if __name__ == "__main__":  # `python -m app.main` (spec section 16)
    import os

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
