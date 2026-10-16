"""Live layer: server-side cache of aircraft positions in the three zones.

Zones are swept on tiers (Hormuz every 15 s, India-Pak 30 s, Red Sea 60 s) with >=1.1 s between
requests, about 0.6 requests per second in total. The browser only talks to this cache, never to
adsb.lol. The 5-minute scoring collector reads from this cache when it is fresh, so the live layer
adds almost no extra upstream load. Errors back off exponentially and fall back to adsb.fi."""
import logging
import threading
import time
from datetime import datetime, timezone

import httpx

from .collectors import UA
from .collectors.adsb import _point, tiles
from .config import cfg, region_of, regions

log = logging.getLogger("geomacro.live")
TIERS = {"hormuz": 15, "india_pak": 30, "red_sea": 60}
CACHE: dict = {}          # region -> {"ts": epoch, "aircraft": {hex: ac}}
STATUS: dict = {r: {"last_sweep": None, "sweep_s": None, "errors": 0, "backoff": 0} for r in TIERS}
_stop = threading.Event()


def sweep(client, region):
    seen = {}
    for lat, lon in tiles(regions()[region]["bbox"]):
        for ac in _point(client, lat, lon):
            if ac.get("lat") is None or ac.get("lon") is None:
                continue
            if region_of(ac["lat"], ac["lon"]) == region:
                seen[ac["hex"]] = ac
        time.sleep(1.1)
    return seen


def loop():
    due = {r: 0.0 for r in TIERS}
    with httpx.Client(timeout=20, headers={"User-Agent": UA}) as c:
        while not _stop.is_set():
            now = time.time()
            region = min((r for r in TIERS if due[r] <= now), key=lambda r: due[r], default=None)
            if region is None:
                _stop.wait(1.0)
                continue
            t0 = time.time()
            try:
                seen = sweep(c, region)
                CACHE[region] = {"ts": time.time(), "aircraft": seen}
                st = STATUS[region]
                st.update(last_sweep=datetime.now(timezone.utc).isoformat(), sweep_s=round(time.time() - t0, 1), errors=0, backoff=0)
                due[region] = time.time() + TIERS[region]
            except Exception as e:  # noqa: BLE001
                st = STATUS[region]
                st["errors"] += 1
                st["backoff"] = min(300, (st["backoff"] or TIERS[region]) * 2)
                log.warning("live sweep %s failed (%s), backing off %ss", region, e, st["backoff"])
                due[region] = time.time() + st["backoff"]


def start():
    t = threading.Thread(target=loop, daemon=True, name="live-aircraft")
    t.start()
    return t


def fresh_aircraft(max_age_s=240):
    """All cached aircraft if every zone was swept recently, else None (collector then fetches itself)."""
    out = {}
    for r in TIERS:
        c = CACHE.get(r)
        if not c or time.time() - c["ts"] > max_age_s:
            return None
        out.update(c["aircraft"])
    return list(out.values())


def snapshot():
    rows = []
    for r, c in CACHE.items():
        for ac in c["aircraft"].values():
            nac = ac.get("nac_p")
            alt = ac.get("alt_baro")
            rows.append({"hex": ac.get("hex"), "call": (ac.get("flight") or "").strip(), "t": ac.get("t"),
                         "lat": ac["lat"], "lon": ac["lon"], "trk": ac.get("track"), "gs": ac.get("gs"),
                         "alt": alt if alt != "ground" else 0, "region": r,
                         "mil": bool((ac.get("dbFlags") or 0) & 1),
                         "deg": bool(nac is not None and isinstance(nac, (int, float)) and nac <= cfg()["rules"]["gps"]["degraded_nacp_max"]
                                     and alt not in (None, "ground") and (ac.get("seen_pos") or 0) <= 60),
                         "age": round(ac.get("seen_pos") or 0, 1), "ts": c["ts"]})
    return rows
