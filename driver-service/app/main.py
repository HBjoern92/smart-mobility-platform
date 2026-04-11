import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException, status

from app.config import settings
from app.kafka_consumer import start_consumer
from app.kafka_producer import publish, stop_producer
from app.schemas import (
    AcceptRideRequest,
    CompleteRideRequest,
    DriverStatusResponse,
    RegisterDriverRequest,
)
from app.store import (
    close_redis,
    get_driver,
    list_drivers,
    register_driver,
    set_available,
)

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
    consumer_task = asyncio.create_task(start_consumer())
    logger.info("Driver service started")

    yield

    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await stop_producer()
    await close_redis()
    logger.info("Driver service shut down cleanly")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Driver Service",
    description="Smart Mobility Platform – Driver management & availability",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "driver-service"}


@app.post(
    "/drivers",
    response_model=DriverStatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new driver",
)
async def register(req: RegisterDriverRequest):
    """
    Registers a driver and marks them as available.
    Simplified: no password, just driver_id + name.
    """
    existing = await get_driver(req.driver_id)
    if existing:
        raise HTTPException(status_code=409, detail="Driver already registered")

    data = await register_driver(req.driver_id, req.name)
    return DriverStatusResponse(**data)


@app.get(
    "/drivers",
    response_model=List[DriverStatusResponse],
    summary="List all registered drivers",
)
async def get_all_drivers():
    drivers = await list_drivers()
    return [DriverStatusResponse(**d) for d in drivers]


@app.get(
    "/drivers/{driver_id}",
    response_model=DriverStatusResponse,
    summary="Get a single driver's status",
)
async def get_driver_status(driver_id: str):
    driver = await get_driver(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return DriverStatusResponse(**driver)


@app.post(
    "/drivers/{driver_id}/available",
    response_model=DriverStatusResponse,
    summary="Manually set driver as available (e.g. after going online)",
)
async def set_driver_available(driver_id: str):
    driver = await get_driver(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    if driver["available"]:
        raise HTTPException(status_code=409, detail="Driver is already available")

    await set_available(driver_id, available=True)
    updated = await get_driver(driver_id)
    return DriverStatusResponse(**updated)


@app.post(
    "/rides/{ride_id}/complete",
    response_model=DriverStatusResponse,
    summary="Driver confirms arrival at destination – completes the ride",
)
async def complete_ride(ride_id: str, req: CompleteRideRequest):
    """
    Called by the driver when they reach the destination.
    1. Marks driver as available again.
    2. Publishes ride.completed → Ride Service updates status to COMPLETED.
    """
    driver = await get_driver(req.driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    if driver.get("current_ride_id") != ride_id:
        raise HTTPException(
            status_code=409,
            detail=f"Driver {req.driver_id} is not assigned to ride {ride_id}",
        )

    # Free up driver
    await set_available(req.driver_id, available=True, ride_id="")

    # Notify other services
    await publish(
        topic=settings.kafka_topic_ride_completed,
        key=ride_id,
        payload={
            "ride_id":   ride_id,
            "driver_id": req.driver_id,
        },
    )
    logger.info("Ride %s completed by driver %s", ride_id, req.driver_id)

    updated = await get_driver(req.driver_id)
    return DriverStatusResponse(**updated)
