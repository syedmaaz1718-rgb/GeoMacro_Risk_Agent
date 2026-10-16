"""GDELT DOC 2.0 conflict-news collector (free, keyless, strict 1 request / 5 s)."""
import json
import time
from datetime import datetime, timezone

import httpx

from ..db import RawEvent, SessionLocal, now
from . import UA, make_event

URL = "https://api.gdeltproject.org/api/v2/doc/doc"
CONFLICT = ("attack OR missile OR drone OR strike OR explosion OR warship OR tanker OR hijack OR "
            "sanction OR military OR escalation")
QUERIES = {
    "hormuz": f'(Hormuz OR "Persian Gulf" OR Iran OR "Gulf of Oman") ({CONFLICT})',
    "red_sea": f'("Red Sea" OR Houthi OR Houthis OR Yemen OR "Gulf of Aden" OR "Bab el-Mandeb" OR Suez) ({CONFLICT})',
    "india_pak": f'(Kashmir OR Pakistan OR "Line of Control" OR "India Pakistan") ({CONFLICT})',
}
_last_call = 0.0


def _fetch(client, query):
    global _last_call
    for attempt in range(2):
        wait = 10.0 - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()
        r = client.get(URL, params={"query": query, "mode": "artlist", "format": "json",
                                    "maxrecords": 250, "timespan": "4h", "sort": "datedesc",
                                    "sourcelang": "english"})
        if r.status_code == 429:
            time.sleep(12)
            continue
        r.raise_for_status()
        try:
            return json.loads(r.text).get("articles", [])
        except ValueError:
            return []          # GDELT returns an empty body when nothing matches
    raise RuntimeError("GDELT rate limited")


def parse_seen(s):
    return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def collect_news():
    with SessionLocal() as s:
        cutoff = now().replace(microsecond=0)
        known = {e.meta.get("url") for e in s.query(RawEvent).filter(
            RawEvent.source == "gdelt", RawEvent.timestamp > cutoff.replace(hour=0, minute=0, second=0)).all()}
    out, titles = [], set()
    with httpx.Client(timeout=40, headers={"User-Agent": UA}) as c:
        failed = []
        for region, q in QUERIES.items():
            try:
                arts = _fetch(c, q)
            except Exception:  # noqa: BLE001 - one region failing must not lose the others
                failed.append(region)
                continue
            for a in arts:
                url, title = a.get("url"), (a.get("title") or "").strip().lower()
                if not url or url in known or title in titles:
                    continue
                titles.add(title)
                known.add(url)
                out.append(make_event("gdelt", "news_spike", region, parse_seen(a["seendate"]), None, None, 0.5,
                                      {"url": url, "title": a.get("title"), "domain": a.get("domain"),
                                       "seendate": a.get("seendate")},
                                      {"url": url, "title": a.get("title"), "domain": a.get("domain"),
                                       "feed_name": "gdelt_doc", "confidence": 0.5}))
    if failed:
        # DOC API rate limited: fall back to GDELT's 15-minute geocoded event files (plain static files, no rate limit)
        out += collect_event_files(failed, known)
    return out


# ---- fallback: GDELT 2.0 geocoded event export files --------------------------------------
EXPORT_INDEX = "https://data.gdeltproject.org/gdeltv2/lastupdate.txt"
CONFLICT_ROOTS = {"15", "18", "19", "20"}     # exhibit force, assault, fight, mass violence


def _files(client, n=4):
    """URLs of the latest n 15-minute export files (lastupdate gives the newest; others by timestamp)."""
    from datetime import timedelta
    txt = client.get(EXPORT_INDEX).text
    last = next(l.split()[2] for l in txt.splitlines() if "export.CSV" in l)
    stamp = last.rsplit("/", 1)[1][:14]
    t0 = datetime.strptime(stamp, "%Y%m%d%H%M%S")
    base = last.rsplit("/", 1)[0]
    return [f"{base}/{(t0 - timedelta(minutes=15 * i)).strftime('%Y%m%d%H%M%S')}.export.CSV.zip".replace("http://", "https://") for i in range(n)]


def parse_export(text, regions_wanted, known):
    from ..config import bbox
    out = []
    for line in text.splitlines():
        f = line.split("\t")
        if len(f) < 61 or f[28] not in CONFLICT_ROOTS:
            continue
        try:
            lat, lon = float(f[56]), float(f[57])
            when = datetime.strptime(f[59], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        url = f[60]
        for region in regions_wanted:
            la0, la1, lo0, lo1 = bbox(region)
            if not (la0 <= lat <= la1 and lo0 <= lon <= lo1):
                continue
            if region == "india_pak":
                both = {f[7], f[17]} >= {"IND", "PAK"}
                border = any(w in f[52] for w in ("Kashmir", "Jammu", "Line of Control", "Punjab")) and ({f[7], f[17]} & {"IND", "PAK"})
                if not (both or border):
                    continue
            k = (region, url)
            if not url or k in known:
                continue
            known.add(k)
            slug = url.rstrip("/").rsplit("/", 1)[-1].rsplit(".", 1)[0].replace("-", " ").replace("_", " ")[:120]
            if sum(ch.isalpha() for ch in slug) < 15:
                slug = "Conflict-coded event reported"
            out.append(make_event("gdelt", "news_spike", region, when, lat, lon, min(1.0, abs(float(f[30])) / 10),
                                  {"url": url, "event_code": f[26], "goldstein": f[30], "place": f[52]},
                                  {"url": url, "title": f"{slug} ({f[52]})", "domain": url.split("/")[2] if "//" in url else "",
                                   "feed_name": "gdelt_events", "confidence": 0.5}))
    return out


def collect_event_files(regions_wanted, known):
    import io
    import zipfile
    out = []
    with httpx.Client(timeout=60, headers={"User-Agent": UA}, follow_redirects=True) as c:
        for url in _files(c):
            r = c.get(url)
            if r.status_code != 200:
                continue
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                text = z.read(z.namelist()[0]).decode("utf-8", "replace")
            known_k = {(r_, u) for r_, u in known if isinstance(r_, str) and r_ in regions_wanted} if False else known
            out += parse_export(text, regions_wanted, known_k)
    return out
