"""
Periodic scheduler for the Spark batch job.
Runs every INTERVAL_SECONDS in a background thread so it does not block
the FastAPI event loop (PySpark is not async-compatible).
"""

import logging
import threading
from datetime import datetime
from typing import Optional

from app.config import settings
from app.mongo import save_kpi_result
from app.spark_job import run_batch_job

logger = logging.getLogger(__name__)

# How often the batch runs (default: every hour)
INTERVAL_SECONDS = 3600

_timer: Optional[threading.Timer] = None
_last_run: Optional[datetime] = None
_last_status: str = "never_run"


def _job_wrapper(source: str) -> None:
    global _last_run, _last_status
    try:
        logger.info("Batch job starting (source=%s)", source)
        kpis = run_batch_job(source=source)
        save_kpi_result(kpis, window_hours=settings.lookback_hours)
        _last_run    = datetime.utcnow()
        _last_status = "success"
        logger.info("Batch job completed successfully")
    except Exception as exc:
        _last_status = f"error: {exc}"
        logger.exception("Batch job failed: %s", exc)
    finally:
        # Schedule the next run
        _schedule(source)


def _schedule(source: str) -> None:
    global _timer
    _timer = threading.Timer(INTERVAL_SECONDS, _job_wrapper, args=[source])
    _timer.daemon = True
    _timer.start()
    logger.info("Next batch job in %ds", INTERVAL_SECONDS)


def start_scheduler(source: str = "mongo", interval_seconds: int = INTERVAL_SECONDS) -> None:
    global INTERVAL_SECONDS
    INTERVAL_SECONDS = interval_seconds
    logger.info("Scheduler started (interval=%ds, source=%s)", interval_seconds, source)
    # Run once immediately at startup, then on schedule
    t = threading.Thread(target=_job_wrapper, args=[source], daemon=True)
    t.start()


def stop_scheduler() -> None:
    global _timer
    if _timer:
        _timer.cancel()
        _timer = None
        logger.info("Scheduler stopped")


def get_scheduler_status() -> dict:
    return {
        "last_run":    _last_run.isoformat() if _last_run else None,
        "last_status": _last_status,
        "interval_seconds": INTERVAL_SECONDS,
    }
