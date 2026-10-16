"""Risk scoring engine (spec section 7): weights, region multiplier, bands."""
from sqlalchemy import select  # noqa: F401

from ..config import LABEL_RANK, cfg, label_for, regions
from ..db import RiskSnapshot
from .correlation import active_signals, correlate


def compute(sigs: dict, region: str) -> dict:
    """Pure function: signal dict -> score details (testable)."""
    weights, rcfg = cfg()["weights"], regions()[region]
    c = correlate(sigs)
    counted = c["counted"]
    raw = sum(weights[t] for t in counted)
    adj = raw * rcfg["multiplier"]
    score = int(min(100, round(adj)))
    return {"raw_score": raw, "multiplier": rcfg["multiplier"], "score": score, "label": label_for(score),
            "signal_types": counted, "osint_count": len(c["osint"]), "market_count": len(c["market"] if c["osint"] else []),
            "alert_candidate": c["alert_candidate"], "quality": c["quality"],
            "confidence": {"high": 0.85, "standard": 0.65, "single-signal": 0.35}[c["quality"]],
            "contributions": {t: round(weights[t] * rcfg["multiplier"], 1) for t in counted}}


def score_regions(s, now):
    snaps = []
    for region in regions():
        sigs = active_signals(s, region, now)
        d = compute(sigs, region)
        active = [{"type": t, "score": sigs[t].score, "evidence": sigs[t].evidence.get("reason", ""),
                   "signal_id": sigs[t].id, "window_end": sigs[t].window_end.isoformat()} for t in d["signal_types"]]
        snaps.append(RiskSnapshot(region=region, score=d["score"], label=d["label"], active_signals=active, details=d))
    s.add_all(snaps)
    s.commit()
    return snaps


def overall(snaps):
    top = max(snaps, key=lambda x: (LABEL_RANK[x.label], x.score)) if snaps else None
    return top
