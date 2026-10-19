"""Build app/data/market_seed.json from REAL Yahoo Finance responses.

Run this from a network where Yahoo answers (any normal connection; Render's shared
IPs are the ones that get rate-limited). The output is committed to the repo so a
fresh deployment can serve real last-good data before its first successful live fetch.

    python scripts/build_market_seed.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.collectors import UA  # noqa: E402
from app.collectors.market_collector import yahoo_move  # noqa: E402
from app.market_fallback import pack_quote  # noqa: E402

OUT = ROOT / "app" / "data" / "market_seed.json"
CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=5y"


def daily(client, sym):
    r = client.get(CHART.format(sym=sym))
    r.raise_for_status()
    j = r.json()["chart"]["result"][0]
    q = j["indicators"]["quote"][0]
    hist = {t: (q["close"][i], q["high"][i], q["low"][i]) for i, t in enumerate(j["timestamp"]) if q["close"][i] is not None}
    gaps = [(t, q["open"][i], q["close"][i]) for i, t in enumerate(j["timestamp"]) if q["open"][i] and q["close"][i]]
    return hist, gaps


def main():
    fetched = datetime.now(timezone.utc).isoformat()
    items = {}
    with httpx.Client(timeout=30, headers={"User-Agent": UA}, follow_redirects=True) as c:
        for sym in ("^NSEI", "^INDIAVIX", "BZ=F", "CL=F"):
            d = yahoo_move(c, sym)
            items["quote:" + sym] = {"payload": pack_quote(d), "fetched_at": fetched}
            print(f"quote {sym}: last {d['last']} at {d['bar_time'].isoformat()}")
        hn, gn = daily(c, "^NSEI")
        hv, gv = daily(c, "^INDIAVIX")
        items["hist5y"] = {"payload": {"n": [[t] + list(v) for t, v in sorted(hn.items())],
                                       "v": [[t] + list(v) for t, v in sorted(hv.items())]}, "fetched_at": fetched}
        items["gaphist5y"] = {"payload": {"n": gn, "v": gv}, "fetched_at": fetched}
        print(f"history: {len(hn)} nifty days, {len(hv)} vix days")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"built_at": fetched, "source": "Yahoo Finance chart API (real responses)",
                               "items": items}, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
