"""Crude (Brent, WTI fallback) and India VIX from Yahoo Finance chart API; VIX falls back to NSE."""
from datetime import datetime, timezone

import httpx

from ..config import cfg
from . import UA, make_event

YF = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=5m&range=1d"


def yahoo_move(client, sym):
    r = client.get(YF.format(sym=sym))
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    meta = res["meta"]
    ts = res.get("timestamp") or []
    closes = (res["indicators"]["quote"][0].get("close") or [])
    bars = [(t, c) for t, c in zip(ts, closes) if c is not None]
    if not bars:
        raise ValueError(f"no bars for {sym}")
    last_ts, last = bars[-1]
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    pct = (last - prev) / prev * 100 if prev else 0.0
    return {"symbol": sym, "last": last, "prev_close": prev, "pct": pct,
            "bar_time": datetime.fromtimestamp(last_ts, timezone.utc)}


def nse_vix(client):
    client.get("https://www.nseindia.com/", headers={"User-Agent": "Mozilla/5.0"})
    r = client.get("https://www.nseindia.com/api/allIndices", headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    for row in r.json()["data"]:
        if row.get("index") == "INDIA VIX":
            return {"symbol": "NSE:INDIA VIX", "last": row["last"], "prev_close": row["previousClose"],
                    "pct": row["percentChange"], "bar_time": datetime.now(timezone.utc)}
    raise ValueError("INDIA VIX not found")


def _event(kind, d, thresholds):
    ts = datetime.now(timezone.utc)
    age = (ts - d["bar_time"]).total_seconds() / 60
    stale = age > cfg()["rules"]["market_max_age_minutes"]
    top = thresholds[-1] * 1.5
    sev = max(0.0, min(1.0, d["pct"] / top))
    meta = {"pct": round(d["pct"], 3), "last": d["last"], "prev_close": d["prev_close"],
            "symbol": d["symbol"], "bar_time": d["bar_time"].isoformat(), "age_minutes": round(age, 1),
            "stale": stale, "feed_name": "yahoo_chart", "confidence": 0.9}
    return make_event("market_feed", kind, "global", ts, None, None, sev, dict(meta, bar_time=meta["bar_time"]), meta)


def collect_market():
    out, errors = [], []
    with httpx.Client(timeout=20, headers={"User-Agent": UA}, follow_redirects=True) as c:
        d = None
        for sym in ("BZ=F", "CL=F"):
            try:
                d = yahoo_move(c, sym)
                break
            except Exception as e:  # noqa: BLE001
                errors.append(f"{sym}: {e}")
        if d:
            out.append(_event("crude_move", d, cfg()["rules"]["crude"]["thresholds"]))
        d = None
        for fn in (lambda: yahoo_move(c, "^INDIAVIX"), lambda: nse_vix(c)):
            try:
                d = fn()
                break
            except Exception as e:  # noqa: BLE001
                errors.append(f"vix: {e}")
        if d:
            out.append(_event("vix_move", d, cfg()["rules"]["vix"]["thresholds"]))
    if not out:
        raise RuntimeError("; ".join(errors))
    return out
