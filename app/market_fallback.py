"""Last-good market data, so a blocked Yahoo never blanks the market pages.

Render's shared egress IPs are sometimes rate-limited (HTTP 429) by Yahoo Finance.
Every consumer that pulls from Yahoo saves its last successful *real* response here
(Postgres/SQLite table `market_cache`) and, when a live fetch fails, serves that stored
response, always labelled with the time it was really fetched. A snapshot generated
outside Render (app/data/market_seed.json, built by scripts/build_market_seed.py) seeds
a fresh deployment so the pages work even before the first successful live fetch.

Nothing here is estimated or interpolated: cached values are real past Yahoo data."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .db import MarketCache, SessionLocal, now

log = logging.getLogger("geomacro.market_fallback")
SEED_PATH = Path(__file__).parent / "data" / "market_seed.json"


def parse_ts(v):
    """Accept a datetime or an ISO string; always return an aware datetime."""
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def save(key, payload, fetched_at=None):
    """Persist the last good payload for a key. Never raises into a request path."""
    try:
        with SessionLocal() as s:
            row = s.get(MarketCache, key)
            if row is None:
                row = MarketCache(key=key)
                s.add(row)
            row.payload = payload
            row.fetched_at = fetched_at or now()
            s.commit()
    except Exception as e:  # noqa: BLE001
        log.warning("market cache save failed for %s: %s", key, e)


def load(key):
    """Return {"payload", "fetched_at", "origin"} from the DB, else the bundled seed; else None."""
    try:
        with SessionLocal() as s:
            row = s.get(MarketCache, key)
            if row is not None:
                return {"payload": row.payload, "fetched_at": row.fetched_at, "origin": "db"}
    except Exception as e:  # noqa: BLE001
        log.warning("market cache load failed for %s: %s", key, e)
    try:
        if SEED_PATH.exists():
            seed = json.loads(SEED_PATH.read_text())
            item = (seed.get("items") or {}).get(key)
            if item is not None:
                return {"payload": item["payload"], "fetched_at": parse_ts(item["fetched_at"]), "origin": "seed"}
    except Exception as e:  # noqa: BLE001
        log.warning("market seed load failed for %s: %s", key, e)
    return None


# ---- quote packing (yahoo_move returns a datetime; JSON needs a string) ----

def pack_quote(d):
    out = dict(d)
    out["bar_time"] = d["bar_time"].isoformat()
    return out


def unpack_quote(d):
    out = dict(d)
    out["bar_time"] = parse_ts(out["bar_time"])
    return out


def save_quote(symbol, d):
    save("quote:" + symbol, pack_quote(d))


def load_quote(symbol):
    c = load("quote:" + symbol)
    if not c:
        return None
    return {"quote": unpack_quote(c["payload"]), "fetched_at": c["fetched_at"], "origin": c["origin"]}
