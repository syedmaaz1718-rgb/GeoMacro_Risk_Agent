"""ADS-B collector (adsb.lol primary, adsb.fi fallback; both free, keyless).

Produces two event types:
  gps_jamming       aircraft whose reported navigation accuracy (NACp) is degraded.
                    This is the same technique GPSJam and ShadowBroker use: GPS
                    interference makes transponders report poor position integrity.
  military_aircraft aircraft flagged military by the community feed, inside a region.
"""
import math
import time
from datetime import datetime, timezone

import httpx

from ..config import cfg, regions
from . import UA, make_event

LOL = "https://api.adsb.lol"
FI = "https://opendata.adsb.fi/api"
RADIUS_NM = 250
_recent: dict = {}   # (hex, type) -> ts, avoids storing the same aircraft every poll


def tiles(bbox):
    """Cover a bbox with circles of RADIUS_NM (feed max)."""
    la0, la1, lo0, lo1 = bbox
    r_km = RADIUS_NM * 1.852
    spacing = r_km * 1.25
    mid = (la0 + la1) / 2
    h = (la1 - la0) * 111.0
    w = (lo1 - lo0) * 111.0 * math.cos(math.radians(mid))
    nl = max(1, math.ceil(h / spacing))
    nw = max(1, math.ceil(w / spacing))
    pts = []
    for i in range(nl):
        for j in range(nw):
            pts.append((la0 + (i + 0.5) * (la1 - la0) / nl, lo0 + (j + 0.5) * (lo1 - lo0) / nw))
    return pts


def _get(client, url):
    r = client.get(url)
    r.raise_for_status()
    return r.json()


def _point(client, lat, lon):
    try:
        d = _get(client, f"{LOL}/v2/point/{lat:.3f}/{lon:.3f}/{RADIUS_NM}")
        return d.get("ac") or []
    except Exception:  # noqa: BLE001
        time.sleep(1.1)
        d = _get(client, f"{FI}/v2/lat/{lat:.3f}/lon/{lon:.3f}/dist/{RADIUS_NM}")
        return d.get("aircraft") or d.get("ac") or []


def _mil(client):
    try:
        return _get(client, f"{LOL}/v2/mil").get("ac") or []
    except Exception:  # noqa: BLE001
        return _get(client, f"{FI}/v2/mil").get("aircraft") or []


def is_degraded(ac, nacp_max):
    nac = ac.get("nac_p")
    if nac is None or not isinstance(nac, (int, float)):
        return None
    alt = ac.get("alt_baro")
    if alt == "ground" or alt is None:
        return None            # ground traffic: poor integrity is common and uninformative
    if (ac.get("seen_pos") or 0) > 60:
        return None            # stale position
    if nac <= nacp_max:
        return max(0.0, min(1.0, (8 - nac) / 8))
    return False


def _region_events(aircraft, ts, kind):
    from ..config import region_of
    nacp_max = cfg()["rules"]["gps"]["degraded_nacp_max"]
    out = []
    for ac in aircraft:
        lat, lon = ac.get("lat"), ac.get("lon")
        if lat is None or lon is None:
            continue
        region = region_of(lat, lon)
        if not region:
            continue
        hexid = ac.get("hex")
        if kind == "gps":
            sev = is_degraded(ac, nacp_max)
            if sev is False or sev is None:
                continue
            etype = "gps_jamming"
            meta = {"confidence": 0.6, "feed_name": "adsb_nacp", "nac_p": ac.get("nac_p"), "nic": ac.get("nic")}
        else:
            etype, sev = "military_aircraft", 0.5
            meta = {"confidence": 0.7, "feed_name": "adsb_mil"}
        key = (hexid, etype)
        if ts.timestamp() - _recent.get(key, 0) < 600:
            continue
        _recent[key] = ts.timestamp()
        meta.update({"hex": hexid, "callsign": (ac.get("flight") or "").strip(), "type": ac.get("t")})
        payload = {k: ac.get(k) for k in ("hex", "flight", "t", "r", "lat", "lon", "alt_baro", "gs", "nac_p", "nic", "sil", "dbFlags")}
        out.append(make_event("adsb", etype, region, ts, lat, lon, sev, payload, meta))
    return out


def collect_gps_and_aircraft():
    ts = datetime.now(timezone.utc)
    seen, out_gps = {}, []
    from .. import live
    cached = live.fresh_aircraft()
    with httpx.Client(timeout=20, headers={"User-Agent": UA}) as c:
        if cached is not None:           # live layer already holds fresh positions: no extra upstream calls
            seen = {ac.get("hex"): ac for ac in cached}
        else:
            for key, r in regions().items():
                for lat, lon in tiles(r["bbox"]):
                    for ac in _point(c, lat, lon):
                        seen[ac.get("hex")] = ac
                    time.sleep(1.1)
        mil = _mil(c)
    # prune cache
    cutoff = ts.timestamp() - 3600
    for k in [k for k, v in _recent.items() if v < cutoff]:
        _recent.pop(k, None)
    out_gps = _region_events(list(seen.values()), ts, "gps")
    out_mil = _region_events(mil, ts, "mil")
    return out_gps + out_mil
