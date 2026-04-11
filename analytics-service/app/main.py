import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from app.config import settings
from app.mongo import close_mongo, get_kpi_history, get_latest_kpis
from app.scheduler import get_scheduler_status, start_scheduler, stop_scheduler
from app.spark_job import run_batch_job
from app.mongo import save_kpi_result

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the periodic batch job (every hour by default)
    start_scheduler(source="mongo", interval_seconds=3600)
    logger.info("Analytics service started")

    yield

    stop_scheduler()
    close_mongo()
    logger.info("Analytics service shut down cleanly")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Analytics Service",
    description="Smart Mobility Platform – Spark Batch Analytics",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "analytics-service"}


@app.get(
    "/analytics/latest",
    summary="Get the most recently computed KPIs",
)
def get_latest():
    result = get_latest_kpis()
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No KPI results yet – batch job may still be running",
        )
    return result


@app.get(
    "/analytics/history",
    summary="Get the last N KPI snapshots",
)
def get_history(limit: int = Query(default=10, ge=1, le=100)):
    return get_kpi_history(limit=limit)


@app.post(
    "/analytics/trigger",
    summary="Manually trigger a batch job run (for testing)",
)
def trigger_job(
    source: str = Query(default="mongo", enum=["mongo", "kafka"]),
):
    """
    Triggers an immediate Spark batch job outside the regular schedule.
    Runs synchronously – may take a few seconds.
    """
    try:
        logger.info("Manual batch job triggered (source=%s)", source)
        kpis = run_batch_job(source=source)
        doc_id = save_kpi_result(kpis, window_hours=settings.lookback_hours)
        return {
            "status":  "completed",
            "doc_id":  doc_id,
            "kpis":    kpis,
        }
    except Exception as exc:
        logger.exception("Manual batch job failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get(
    "/analytics/scheduler",
    summary="Get scheduler status (last run, next run interval)",
)
def scheduler_status():
    return get_scheduler_status()
