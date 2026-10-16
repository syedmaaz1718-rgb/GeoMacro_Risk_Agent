"""Alert generation: dedupe, escalation, resolution, delivery, morning summary (spec sections 8-10, 13, 23)."""
import logging
from datetime import timedelta

from sqlalchemy import select

from ..config import LABEL_RANK, cfg, regions
from ..db import Alert, RiskSnapshot, now
from .llm_summarizer import PROMPT, llm_note  # noqa: F401
from .telegram import deliver, telegram_ready  # noqa: F401
from .templates import ACTION, HEAD, SIGNAL_TEXT, WHY, format_message, region_why  # noqa: F401

log = logging.getLogger("geomacro.alerts")


def store_alert(s, region, score, label, message, meta):
    status, to = deliver(message)
    a = Alert(region=region, score=score, label=label, message=message, sent_to=to, status=status, sent_at=now(), meta=meta)
    s.add(a)
    s.commit()
    return a


def decide(label, candidate, recent_alerts, last_alert, last_snaps, dedupe_minutes, resolve_after, ts):
    """Pure decision: returns 'send' | 'resolve' | None.
    recent_alerts: alerts for region within dedupe window (non-test).
    last_alert: most recent non-test alert for region (any age).
    last_snaps: latest snapshots (newest first)."""
    if label == "NORMAL":
        if last_alert and last_alert.label in ("HIGH", "AVOID") and last_alert.meta.get("kind") != "resolved":
            if len(last_snaps) >= resolve_after and all(x.label == "NORMAL" for x in last_snaps[:resolve_after]):
                return "resolve"
        return None
    if not candidate:
        return None
    if any(a.label == label for a in recent_alerts):
        return None                      # same region + same band within window
    return "send"                        # new band, or window expired (escalation is a new band)


def run_alerts(s, ts=None):
    ts = ts or now()
    a_cfg = cfg()["alerts"]
    sent = []
    for region in regions():
        snaps = list(s.scalars(select(RiskSnapshot).where(RiskSnapshot.region == region)
                               .order_by(RiskSnapshot.created_at.desc()).limit(5)))
        if not snaps:
            continue
        cur = snaps[0]
        base = select(Alert).where(Alert.region == region, Alert.label.in_(list(LABEL_RANK)),
                                   Alert.status != "test").order_by(Alert.sent_at.desc())
        alerts = [a for a in s.scalars(base.limit(30)) if not a.meta.get("test") and a.meta.get("kind") != "morning"]
        recent = [a for a in alerts if a.sent_at >= ts - timedelta(minutes=a_cfg["dedupe_minutes"]) and a.meta.get("kind") != "resolved"]
        last = alerts[0] if alerts else None
        action = decide(cur.label, cur.details.get("alert_candidate"), recent, last, snaps,
                        a_cfg["dedupe_minutes"], a_cfg["resolve_after_checks"], ts)
        if not action:
            log.info("alert skipped region=%s label=%s score=%s reason=%s", region, cur.label, cur.score,
                     "no new alert condition (below threshold, deduped, or single-signal)")
            continue
        msg = format_message(cur)
        note = llm_note(cur)
        if note:
            msg += "\n\nAnalyst note:\n" + note
        meta = {"kind": "resolved" if action == "resolve" else "risk", "snapshot_id": cur.id,
                "signals": cur.active_signals, "details": cur.details, "llm_note": bool(note),
                "escalation": bool(last and LABEL_RANK[cur.label] > LABEL_RANK.get(last.label, 0))}
        a = store_alert(s, region, cur.score, cur.label, msg, meta)
        log.info("alert %s region=%s label=%s status=%s llm_fallback=%s", a.id, region, cur.label, a.status, not note)
        sent.append(a)
    return sent


def morning_summary(s, ts=None):
    from .db import RawEvent
    snaps = {}
    for region in regions():
        x = s.scalars(select(RiskSnapshot).where(RiskSnapshot.region == region).order_by(RiskSnapshot.created_at.desc()).limit(1)).first()
        if x:
            snaps[region] = x
    if not snaps:
        return None
    top = max(snaps.values(), key=lambda x: (LABEL_RANK[x.label], x.score))
    stance = {"NORMAL": "Normal IC rules allowed.", "CAUTION": "Reduce aggression, avoid tight strikes.",
              "HIGH": "Reduce lot size, widen wings, avoid overnight risk.",
              "AVOID": "Avoid fresh narrow IC; review hedge/exit rules."}[top.label]
    lines = ["Morning Geo Risk Summary for NIFTY IC", f"Overall: {top.label}", "Top regions:"]
    for x in sorted(snaps.values(), key=lambda x: -x.score):
        sig = ", ".join(SIGNAL_TEXT.get(a["type"], a["type"]) for a in x.active_signals) or "no active signals"
        lines.append(f"- {regions()[x.region]['name']}: {x.label} {x.score}/100 ({sig})")
    for etype, name in (("crude_move", "Brent"), ("vix_move", "India VIX")):
        e = s.scalars(select(RawEvent).where(RawEvent.event_type == etype).order_by(RawEvent.timestamp.desc()).limit(1)).first()
        if e:
            lines.append(f"{name}: {e.meta['last']:.2f} ({e.meta['pct']:+.2f}% vs prev close{', last session' if e.meta.get('stale') else ''})")
    lines.append(f"Suggested stance: {stance}")
    msg = "\n".join(lines)
    return store_alert(s, "all", top.score, top.label, msg, {"kind": "morning"})


CRITICAL_FEEDS = {"adsb": "GPS/aircraft", "ais": "AIS"}


def stale_feed_warnings(s, ts=None, stale_minutes=30, repeat_minutes=120):
    """Spec section 23: critical feeds stale > 30 min -> system warning. Repeats at most every 2 h per feed."""
    from ..db import FeedRun
    from ..collectors import ais as ais_mod
    ts = ts or now()
    out = []
    for feed, name in CRITICAL_FEEDS.items():
        if feed == "ais" and not ais_mod.enabled():
            continue
        any_run = s.scalars(select(FeedRun).where(FeedRun.feed == feed).limit(1)).first()
        if not any_run:
            continue  # never ran (e.g. app just started): nothing to call stale yet
        ok = s.scalars(select(FeedRun).where(FeedRun.feed == feed, FeedRun.ok.is_(True))
                       .order_by(FeedRun.started_at.desc()).limit(1)).first()
        age = (ts - ok.started_at).total_seconds() / 60 if ok else None
        if age is not None and age <= stale_minutes:
            continue
        mins = int(age) if age is not None else None
        prev = [a for a in s.scalars(select(Alert).where(Alert.region == "system").order_by(Alert.sent_at.desc()).limit(10))
                if a.meta.get("feed") == feed and a.sent_at >= ts - timedelta(minutes=repeat_minutes)]
        if prev:
            log.info("stale-feed warning skipped feed=%s reason=already warned within %d min", feed, repeat_minutes)
            continue
        how = f"stale for {mins} minutes" if mins is not None else "has had no successful run"
        msg = f"\u26a0\ufe0f Geo-risk system warning: {name} feed {how}. Risk score may be incomplete."
        out.append(store_alert(s, "system", 0, "NORMAL", msg, {"kind": "system_warning", "feed": feed, "stale_minutes": mins}))
        log.warning(msg)
    return out
