"""Telegram message templates (spec section 10)."""
from ..config import regions

HEAD = {"CAUTION": "⚠️ GEO RISK: CAUTION", "HIGH": "🚨 GEO RISK: HIGH", "AVOID": "🛑 GEO RISK: AVOID FRESH NARROW IC",
        "NORMAL": "✅ GEO RISK: RESOLVED"}

ACTION = {
    "CAUTION": "Avoid very tight IC. Use normal size only if premiums justify the risk.",
    "HIGH": "Reduce lot size or widen IC strikes. Avoid aggressive overnight short options.",
    "AVOID": "Avoid new narrow IC. Review existing position hedge/exit rules.",
    "NORMAL": "Normal IC rules allowed.",
}

WHY = {
    "CAUTION": "Potential volatility build-up. Not enough confirmation yet.",
    "HIGH": "Higher crude shock and India gap-risk probability.",
    "AVOID": "Direct India market event risk. Gap risk can hurt weekly IC.",
    "NORMAL": "Signals have cleared for 3 consecutive checks.",
}

SIGNAL_TEXT = {
    "gps_jamming_cluster": "GPS degradation cluster (proxy for interference)",
    "military_spike": "Military aircraft activity spike",
    "tanker_dark_gap": "Tanker AIS anomaly count elevated",
    "conflict_news_spike": "Conflict news velocity rising",
    "crude_confirmation": "Crude oil confirming",
    "vix_confirmation": "India VIX confirming",
}


def region_why(label, region):
    base = WHY[label]
    if label in ("CAUTION", "HIGH") and region in regions():
        return f"{regions()[region]['why']}. {base}"
    return base


def format_message(snap, signals_detail=None):
    r = regions()[snap.region]
    lines = [HEAD[snap.label], f"Region: {r['name']}", f"Score: {snap.score}/100", "Signals:"]
    for a in snap.active_signals:
        lines.append(f"- {a['evidence'] or SIGNAL_TEXT.get(a['type'], a['type'])}")
    if not snap.active_signals:
        lines.append("- none active")
    lines += ["Why it matters:", region_why(snap.label, snap.region), "Options Action:", ACTION[snap.label],
              f"Confidence: {int(snap.details.get('confidence', 0) * 100)}% ({snap.details.get('quality', '')})"]
    return "\n".join(lines)
