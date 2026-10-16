"""Editable settings: whitelist, validation, DB overrides, change log, reset."""
from sqlalchemy import select

from .db import SessionLocal, SettingChange, SettingOverride, now


NAMES = {"gps_jamming_cluster": "GPS degradation cluster", "military_spike": "military aircraft spike", "tanker_dark_gap": "tanker AIS anomaly",
         "conflict_news_spike": "conflict news velocity", "crude_confirmation": "crude confirmation", "vix_confirmation": "India VIX confirmation"}


def _spec():
    from .config import base_cfg
    b = base_cfg()
    S = {}
    for k in b["weights"]:
        S[f"weights.{k}"] = dict(t="int", lo=0, hi=100, label="Weight: " + NAMES.get(k, k))
    for k in ("caution", "high", "avoid"):
        S[f"bands.{k}"] = dict(t="int", lo=1, hi=100, label=f"{k.capitalize()} band starts at score")
    S["rules.gps.min_events"] = dict(t="int", lo=1, hi=100, label="GPS cluster: min aircraft in 60 min")
    S["rules.gps.min_avg_severity"] = dict(t="float", lo=0.1, hi=1.0, label="GPS cluster: min average severity")
    S["rules.gps.degraded_nacp_max"] = dict(t="int", lo=0, hi=11, label="GPS degraded when NACp is at or below")
    S["rules.military.min_aircraft"] = dict(t="int", lo=1, hi=200, label="Military spike: min aircraft in 60 min")
    S["rules.ais.min_anomalies"] = dict(t="int", lo=1, hi=100, label="Tanker anomalies needed in 2 h")
    S["rules.ais.gap_minutes"] = dict(t="int", lo=10, hi=720, label="Tanker dark gap (minutes)")
    S["rules.news.min_mentions"] = dict(t="int", lo=1, hi=500, label="News: min items in 60 min")
    S["rules.crude.thresholds"] = dict(t="list3", lo=0.1, hi=50, label="Crude move % (low / mid / high)")
    S["rules.vix.thresholds"] = dict(t="list3", lo=0.1, hi=100, label="India VIX move % (low / mid / high)")
    S["alerts.dedupe_minutes"] = dict(t="int", lo=5, hi=1440, label="Alert dedupe window (minutes)")
    S["alerts.resolve_after_checks"] = dict(t="int", lo=1, hi=20, label="Clear alert after N quiet checks")
    S["alerts.telegram_enabled"] = dict(t="bool", label="Send Telegram alerts")
    for r in b["regions"]:
        S[f"regions.{r}.multiplier"] = dict(t="float", lo=0.5, hi=3.0, label=f"Multiplier: {b['regions'][r]['name']}")
    return S


def spec():
    return _spec()


def get_default(key):
    from .config import base_cfg
    b = base_cfg()
    if key.startswith("bands."):
        return b["risk_bands"][key.split(".")[1]][0]
    cur = b
    for p in key.split("."):
        cur = cur[p]
    return cur


def _set(c, key, v):
    if key.startswith("bands."):
        c["risk_bands"][key.split(".")[1]][0] = v
        bd = c["risk_bands"]
        bd["normal"] = [0, bd["caution"][0] - 1]
        bd["caution"][1] = bd["high"][0] - 1
        bd["high"][1] = bd["avoid"][0] - 1
        bd["avoid"][1] = 100
        return
    parts = key.split(".")
    cur = c
    for p in parts[:-1]:
        cur = cur[p]
    cur[parts[-1]] = v


def validate(key, v):
    sp = _spec().get(key)
    if not sp:
        raise ValueError(f"'{key}' is not an editable setting")
    t = sp["t"]
    try:
        if t == "bool":
            if not isinstance(v, bool):
                raise ValueError
            return v
        if t == "int":
            if isinstance(v, bool) or float(v) != int(float(v)):
                raise ValueError
            v = int(float(v))
        elif t == "float":
            v = round(float(v), 3)
        elif t == "list3":
            if not isinstance(v, (list, tuple)) or len(v) != 3:
                raise ValueError
            v = [round(float(x), 3) for x in v]
            if not (v[0] < v[1] < v[2]):
                raise ValueError(f"{sp['label']}: the three values must increase")
            for x in v:
                if not sp["lo"] <= x <= sp["hi"]:
                    raise ValueError
            return v
    except (TypeError, ValueError) as e:
        msg = str(e) or f"{sp['label']}: invalid value"
        raise ValueError(msg if "must" in msg else f"{sp['label']}: invalid value") from None
    if not sp["lo"] <= v <= sp["hi"]:
        raise ValueError(f"{sp['label']}: must be between {sp['lo']} and {sp['hi']}")
    return v


def merge(c):
    try:
        with SessionLocal() as s:
            rows = s.scalars(select(SettingOverride)).all()
    except Exception:
        return c        # table not created yet
    ov = {r.key: r.value["v"] for r in rows}
    for k in [x for x in ov if x.startswith("bands.")] + [x for x in ov if not x.startswith("bands.")]:
        if k in _spec():
            _set(c, k, ov[k])
    return c


def current(key):
    from .config import cfg
    c = cfg()
    if key.startswith("bands."):
        return c["risk_bands"][key.split(".")[1]][0]
    cur = c
    for p in key.split("."):
        cur = cur[p]
    return cur


def _check_bands(changes):
    vals = {k: changes.get(f"bands.{k}", current(f"bands.{k}")) for k in ("caution", "high", "avoid")}
    if not (vals["caution"] < vals["high"] < vals["avoid"]):
        raise ValueError("Risk bands must increase: caution < high < avoid")


def apply_changes(changes: dict, actor="admin"):
    """Validate everything first, then write all or nothing. Returns list of applied diffs."""
    from .config import reload_cfg
    clean = {k: validate(k, v) for k, v in changes.items()}
    _check_bands(clean)
    wsum = sum(clean.get(f"weights.{k}", current(f"weights.{k}")) for k in _wkeys())
    if wsum <= 0:
        raise ValueError("At least one signal weight must be above zero")
    done = []
    with SessionLocal() as s:
        for k, v in clean.items():
            old = current(k)
            if old == v:
                continue
            row = s.get(SettingOverride, k)
            if get_default(k) == v:
                if row:
                    s.delete(row)
            elif row:
                row.value = {"v": v}; row.updated_at = now(); row.updated_by = actor
            else:
                s.add(SettingOverride(key=k, value={"v": v}, updated_by=actor))
            s.add(SettingChange(actor=actor, key=k, old={"v": old}, new={"v": v}))
            done.append({"key": k, "old": old, "new": v})
        s.commit()
    reload_cfg()
    return done


def _wkeys():
    from .config import base_cfg
    return list(base_cfg()["weights"])


def reset_all(actor="admin"):
    from .config import reload_cfg
    done = []
    with SessionLocal() as s:
        for row in s.scalars(select(SettingOverride)).all():
            s.add(SettingChange(actor=actor, key=row.key, old=row.value, new={"v": get_default(row.key)}, note="reset"))
            done.append({"key": row.key, "old": row.value["v"], "new": get_default(row.key)})
            s.delete(row)
        s.commit()
    reload_cfg()
    return done


def changelog(limit=50):
    with SessionLocal() as s:
        q = select(SettingChange).order_by(SettingChange.ts.desc()).limit(limit)
        return [{"t": c.ts.isoformat(), "actor": c.actor, "key": c.key, "label": (_spec().get(c.key) or {}).get("label", c.key),
                 "old": c.old.get("v"), "new": c.new.get("v"), "note": c.note} for c in s.scalars(q)]


def editable_view():
    out = []
    for k, sp in _spec().items():
        d = get_default(k); cur = current(k)
        out.append({"key": k, "label": sp["label"], "type": sp["t"], "min": sp.get("lo"), "max": sp.get("hi"),
                    "default": d, "value": cur, "changed": d != cur})
    return out
