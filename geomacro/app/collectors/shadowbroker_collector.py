"""Optional adapter for a self-hosted ShadowBroker backend (SHADOWBROKER_API_BASE).

Reads the `gps_jamming` layer from GET /api/live-data and stores each zone as a
`gps_jamming` event with source `shadowbroker`. Disabled when the env var is empty.
Field names are read defensively since the upstream schema can change."""
from datetime import datetime, timezone

import httpx

from ..config import env, region_of
from . import UA, make_event


def enabled():
    return bool(env("SHADOWBROKER_API_BASE"))


def collect_shadowbroker():
    base = env("SHADOWBROKER_API_BASE").rstrip("/")
    r = httpx.get(f"{base}/api/live-data", timeout=30, headers={"User-Agent": UA})
    r.raise_for_status()
    zones = r.json().get("gps_jamming") or []
    ts = datetime.now(timezone.utc)
    out = []
    for z in zones:
        lat = z.get("lat", z.get("latitude"))
        lon = z.get("lon", z.get("lng", z.get("longitude")))
        if lat is None or lon is None:
            continue
        region = region_of(float(lat), float(lon))
        if not region:
            continue
        sev = z.get("severity", z.get("intensity", 0.7))
        try:
            sev = float(sev)
            sev = sev / 100 if sev > 1 else sev
        except (TypeError, ValueError):
            sev = 0.7
        out.append(make_event("shadowbroker", "gps_jamming", region, ts, float(lat), float(lon), sev, z,
                              {"feed_name": "shadowbroker_gps_jamming", "confidence": 0.8,
                               "hex": f"sb:{round(float(lat), 1)},{round(float(lon), 1)}"}))
    return out
