"""Crude (Brent, WTI fallback) and India VIX from Yahoo Finance chart API; VIX falls back to NSE.

Yahoo rate-limits some shared hosting IPs (HTTP 429). When every live source fails, the last
real response stored by `market_fallback` is emitted instead, marked `cached` with its real
fetch time. Stale values never raise the risk score: the extractors ignore stale market events."""
from datetime import datetime, timezone

import httpx

from ..config import cfg
from ..market_fallback import load_quote, save_quote
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


def _event(kind, d, thresholds, cached_as_of=None):
    ts = datetime.now(timezone.utc)
    age = (ts - d["bar_time"]).total_seconds() / 60
    stale = age > cfg()["rules"]["market_max_age_minutes"]
    top = thresholds[-1] * 1.5
    sev = max(0.0, min(1.0, d["pct"] / top))
    meta = {"pct": round(d["pct"], 3), "last": d["last"], "prev_close": d["prev_close"],
            "symbol": d["symbol"], "bar_time": d["bar_time"].isoformat(), "age_minutes": round(age, 1),
            "stale": stale, "feed_name": "yahoo_chart", "confidence": 0.9}
    if cached_as_of is not None:
        meta["cached"] = True
        meta["cached_as_of"] = cached_as_of.isoformat()
    return make_event("market_feed", kind, "global", ts, None, None, sev, dict(meta, bar_time=meta["bar_time"]), meta)


def _live_or_cached(client, live_fns, cache_symbols, errors):
    """Try each live source; on success refresh the stored last-good quote and return it live.
    When every live source fails, fall back to the newest stored real quote."""
    for fn, sym in live_fns:
        try:
            d = fn()
            save_quote(sym, d)
            return d, None
        except Exception as e:  # noqa: BLE001
            errors.append(f"{sym}: {e}")
    for sym in cache_symbols:
        c = load_quote(sym)
        if c:
            return c["quote"], c["fetched_at"]
    return None, None


def collect_market():
    out, errors = [], []
    with httpx.Client(timeout=20, headers={"User-Agent": UA}, follow_redirects=True) as c:
        d, cached = _live_or_cached(c, [(lambda: yahoo_move(c, s), s) for s in ("BZ=F", "CL=F")], ("BZ=F", "CL=F"), errors)
        if d:
            out.append(_event("crude_move", d, cfg()["rules"]["crude"]["thresholds"], cached))
        d, cached = _live_or_cached(c, [(lambda: yahoo_move(c, "^INDIAVIX"), "^INDIAVIX"), (lambda: nse_vix(c), "NSE:INDIA VIX")],
                                    ("^INDIAVIX", "NSE:INDIA VIX"), errors)
        if d:
            out.append(_event("vix_move", d, cfg()["rules"]["vix"]["thresholds"], cached))
    if not out:
        raise RuntimeError("; ".join(errors) or "no live or cached market data")
    return out
