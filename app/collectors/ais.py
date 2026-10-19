"""AIS via aisstream.io websocket (free key, AISSTREAM_API_KEY).

A background listener keeps the `vessels` table current for chokepoint zones.
`detect_anomalies` (run on the scheduler) turns vessel state into `ais_dark_gap` events:
  * dark gap      tanker last seen underway inside a chokepoint, then silent > gap_minutes
  * stationary    tanker stopped / drifting (not anchored or moored) in a chokepoint > stationary_minutes
  * identity      MMSI broadcast a different vessel name than before
Coverage is limited to what aisstream's receivers hear, so a gap can be a coverage edge;
the signal is intentionally conservative (needs >= 3 anomalies in 2 hours)."""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ..config import cfg, env
from ..db import RawEvent, SessionLocal, Vessel, now
from . import make_event

log = logging.getLogger("geomacro.ais")
WS = "wss://stream.aisstream.io/v0/stream"
STATE = {"connected": False, "messages": 0, "last_message": None, "error": "", "blocked": False, "next_retry_at": None}


def enabled():
    return bool(env("AISSTREAM_API_KEY"))


def zones():
    out = []
    for region, lst in cfg()["chokepoints"].items():
        for z in lst:
            out.append((region, z["name"], z["bbox"]))
    return out


def zone_of(lat, lon):
    for region, name, (la0, la1, lo0, lo1) in zones():
        if la0 <= lat <= la1 and lo0 <= lon <= lo1:
            return region, name
    return None


def is_tanker(t):
    return t is not None and 80 <= t <= 89


def apply_message(s, msg, ts=None):
    """Update the vessel table from one aisstream message. Returns identity event or None."""
    ts = ts or now()
    meta = msg.get("MetaData") or {}
    mmsi = meta.get("MMSI")
    if not mmsi:
        return None
    v = s.get(Vessel, int(mmsi))
    if v is None:
        v = Vessel(mmsi=int(mmsi), first_seen=ts, last_seen=ts, positions=0)
        s.add(v)
    mtype = msg.get("MessageType")
    body = (msg.get("Message") or {}).get(mtype) or {}
    name = (meta.get("ShipName") or "").strip()
    event = None
    if mtype == "ShipStaticData":
        stype = body.get("Type")
        if stype is not None:
            v.ship_type = int(stype)
        sname = (body.get("Name") or name).strip()
        if sname and v.name and sname != v.name and is_tanker(v.ship_type) and v.lat is not None:
            r = zone_of(v.lat, v.lon)
            if r:
                event = make_event("aisstream", "ais_dark_gap", r[0], ts, v.lat, v.lon, 0.5,
                                   {"mmsi": v.mmsi, "old_name": v.name, "new_name": sname},
                                   {"kind": "identity_mismatch", "mmsi": v.mmsi, "zone": r[1],
                                    "key": f"id:{v.mmsi}:{sname}", "feed_name": "aisstream", "confidence": 0.6})
        if sname:
            v.name = sname
        return event
    if mtype in ("PositionReport", "StandardClassBPositionReport"):
        lat, lon = meta.get("latitude"), meta.get("longitude")
        if lat is None or lon is None:
            return None
        sog = body.get("Sog")
        v.lat, v.lon, v.sog = float(lat), float(lon), (float(sog) if sog is not None else None)
        v.nav_status = body.get("NavigationalStatus")
        v.last_seen, v.positions = ts, (v.positions or 0) + 1
        if name and not v.name:
            v.name = name
        z = zone_of(v.lat, v.lon)
        moving = v.sog is not None and v.sog >= 2.0
        if moving:
            v.last_underway, v.stationary_since = ts, None
            if z:
                v.last_underway_zone = z[1]
        elif v.sog is not None and v.sog < 0.5:
            if v.stationary_since is None:
                v.stationary_since = ts
    return event


def detect_anomalies(s, ts=None):
    """Return anomaly RawEvents for current vessel state (deduplicated per vessel)."""
    ts = ts or now()
    r = cfg()["rules"]["ais"]
    out = []
    existing = {e.meta.get("key") for e in s.scalars(select(RawEvent).where(
        RawEvent.source == "aisstream", RawEvent.timestamp > ts - timedelta(hours=6)))}
    for v in s.scalars(select(Vessel).where(Vessel.last_seen > ts - timedelta(hours=24))):
        if not is_tanker(v.ship_type) or v.lat is None:
            continue
        z = zone_of(v.lat, v.lon)
        if z and v.stationary_since and v.nav_status not in (1, 5) and \
                (ts - v.stationary_since) >= timedelta(minutes=r["stationary_minutes"]) and \
                (ts - v.last_seen) < timedelta(minutes=30):
            key = f"stop:{v.mmsi}:{v.stationary_since:%Y%m%d%H}"
            if key not in existing:
                out.append(make_event("aisstream", "ais_dark_gap", z[0], ts, v.lat, v.lon, 0.6,
                                      {"mmsi": v.mmsi, "name": v.name, "sog": v.sog},
                                      {"kind": "stationary_in_chokepoint", "mmsi": v.mmsi, "zone": z[1],
                                       "key": key, "feed_name": "aisstream", "confidence": 0.6}))
        gap = ts - v.last_seen
        if v.last_underway_zone and v.last_underway and (v.positions or 0) >= 3 and z and \
                v.sog is not None and v.sog >= 2.0 and \
                timedelta(minutes=r["gap_minutes"]) <= gap <= timedelta(hours=24):
            key = f"gap:{v.mmsi}:{v.last_seen:%Y%m%d%H%M}"
            if key not in existing:
                out.append(make_event("aisstream", "ais_dark_gap", z[0], ts, v.lat, v.lon, 0.8,
                                      {"mmsi": v.mmsi, "name": v.name, "last_seen": v.last_seen.isoformat()},
                                      {"kind": "dark_gap", "mmsi": v.mmsi, "zone": z[1], "key": key,
                                       "gap_minutes": int(gap.total_seconds() // 60),
                                       "feed_name": "aisstream", "confidence": 0.6}))
    return out


def collect_ais_anomalies():
    with SessionLocal() as s:
        return detect_anomalies(s)


async def listen_forever():
    """Persistent websocket listener; flushes vessel updates in small batches."""
    import random
    import time
    import websockets
    boxes = [[[b[0], b[2]], [b[1], b[3]]] for _, _, b in zones()]
    backoff = 5
    while True:
        started = time.time()
        key = env("AISSTREAM_API_KEY")          # re-read so a changed key is picked up
        sub = {"APIKey": key, "BoundingBoxes": boxes,
               "FilterMessageTypes": ["PositionReport", "ShipStaticData"]}
        try:
            async with websockets.connect(WS, ping_interval=20, max_size=2**20) as ws:
                await ws.send(json.dumps(sub))
                STATE.update(connected=True, error="", blocked=False, next_retry_at=None)
                backoff = 5
                buf, last_flush = [], datetime.now(timezone.utc)
                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=10)
                    except asyncio.TimeoutError:
                        raw = None            # quiet period: still flush what we have
                    if raw is not None:
                        msg = json.loads(raw)
                        if "error" in msg:
                            raise RuntimeError(msg["error"])
                        buf.append(msg)
                        STATE["messages"] += 1
                        STATE["last_message"] = datetime.now(timezone.utc).isoformat()
                    if buf and (len(buf) >= 200 or (datetime.now(timezone.utc) - last_flush).total_seconds() >= 20):
                        await asyncio.to_thread(_flush, buf)
                        buf, last_flush = [], datetime.now(timezone.utc)
        except Exception as e:  # noqa: BLE001
            STATE.update(connected=False, error=f"{type(e).__name__}: {e}"[:200])
            log.warning("aisstream listener error: %s", STATE["error"])
            if time.time() - started > 300:
                backoff = 5                      # was healthy for a while, restart small
            if "429" in str(e):
                # Rate limited: hammering keeps the block alive. Stay quiet for a long time.
                backoff = max(backoff, 900)      # 15 min first, then doubling up to 2 h
                wait = backoff + random.uniform(0, 60)
                backoff = min(backoff * 2, 7200)
                STATE["blocked"] = True
            else:
                wait = backoff + random.uniform(0, 3)
                backoff = min(backoff * 2, 300)
                STATE["blocked"] = False
            STATE["next_retry_at"] = (datetime.now(timezone.utc) + timedelta(seconds=wait)).isoformat()
            await asyncio.sleep(wait)


def _flush(msgs):
    with SessionLocal() as s:
        events = []
        for m in msgs:
            try:
                e = apply_message(s, m)
                if e:
                    events.append(e)
            except Exception as ex:  # noqa: BLE001
                log.debug("bad ais message: %s", ex)
        s.add_all(events)
        s.commit()
