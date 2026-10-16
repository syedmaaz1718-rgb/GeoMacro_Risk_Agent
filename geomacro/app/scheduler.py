"""Scheduler jobs (spec section 13) + wiring."""
import asyncio
import logging
import threading
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import delete

from . import alerts, scoring
from .collectors import adsb, ais, gdelt, market, run_feed, shadowbroker
from .config import cfg
from .db import Alert, FeedRun, RawEvent, RiskSnapshot, SessionLocal, Signal, now
from .extractors import run_extractors

log = logging.getLogger("geomacro.jobs")
_lock = threading.Lock()


def job_collect_gps_aircraft():
    run_feed("adsb", adsb.collect_gps_and_aircraft)
    if shadowbroker.enabled():
        run_feed("shadowbroker", shadowbroker.collect_shadowbroker)


def job_collect_market():
    run_feed("market", market.collect_market)


def job_collect_news():
    run_feed("gdelt", gdelt.collect_news)


def job_collect_ais():
    if ais.enabled():
        run_feed("ais", ais.collect_ais_anomalies)


def job_pipeline():
    """Extract signals -> score risk -> send alerts (jobs 2, 3, 4)."""
    with _lock, SessionLocal() as s:
        t = now()
        run_extractors(s, t)
        snaps = scoring.score_regions(s, t)
        sent = alerts.run_alerts(s, t)
        log.info("pipeline: %s | alerts sent: %d", {x.region: (x.label, x.score) for x in snaps}, len(sent))


def job_stale_check():
    with SessionLocal() as s:
        alerts.stale_feed_warnings(s)


def job_morning():
    with SessionLocal() as s:
        alerts.morning_summary(s)


def job_prune():
    cutoff = now() - timedelta(days=cfg()["retention_days"])
    with SessionLocal() as s:
        for m, col in ((RawEvent, RawEvent.timestamp), (Signal, Signal.created_at), (FeedRun, FeedRun.started_at),
                       (RiskSnapshot, RiskSnapshot.created_at)):
            s.execute(delete(m).where(col < cutoff))
        s.commit()


def start_scheduler():
    sch = BackgroundScheduler(timezone="Asia/Kolkata", job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 120})
    hh, mm = cfg()["alerts"]["morning_summary_time_ist"].split(":")
    sch.add_job(job_collect_gps_aircraft, "interval", minutes=5, id="collect_adsb", next_run_time=now())
    sch.add_job(job_collect_market, "interval", minutes=5, id="collect_market", next_run_time=now())
    sch.add_job(job_collect_news, "interval", minutes=10, id="collect_gdelt", next_run_time=now() + timedelta(seconds=5))
    sch.add_job(job_collect_ais, "interval", minutes=5, id="collect_ais", next_run_time=now() + timedelta(seconds=90))
    sch.add_job(job_pipeline, "interval", minutes=5, id="pipeline", next_run_time=now() + timedelta(seconds=150))
    sch.add_job(job_stale_check, "interval", minutes=5, id="stale_check", next_run_time=now() + timedelta(minutes=6))
    sch.add_job(job_morning, "cron", day_of_week="mon-fri", hour=int(hh), minute=int(mm), id="morning", misfire_grace_time=1800)
    sch.add_job(job_prune, "cron", hour=3, minute=30, id="prune")
    sch.start()
    return sch


def start_ais_listener():
    if not ais.enabled():
        return None
    def runner():
        asyncio.run(ais.listen_forever())
    t = threading.Thread(target=runner, daemon=True, name="aisstream")
    t.start()
    return t
