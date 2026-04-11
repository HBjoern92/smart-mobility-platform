import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import List

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.kafka_consumer import start_consumer
from app.kafka_producer import publish, stop_producer
from app.models import Ride, RideStatus, create_tables, get_db
from app.pricing import calculate_eta, calculate_price, haversine_km
from app.schemas import (
    BookRideRequest,
    RideEstimateResponse,
    RideResponse,
    UpdateLocationRequest,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan – startup / shutdown tasks
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_tables()
    logger.info("Database tables ensured")

    consumer_task = asyncio.create_task(start_consumer())
    logger.info("Kafka consumer task created")

    yield

    # Shutdown
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await stop_producer()
    logger.info("Ride service shut down cleanly")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Ride Service",
    description="Smart Mobility Platform – Ride booking & SAGA orchestration",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    """Kubernetes liveness / readiness probe."""
    return {"status": "ok", "service": "ride-service"}


@app.post(
    "/rides/estimate",
    response_model=RideEstimateResponse,
    summary="Get a price & ETA estimate without booking",
)
def estimate_ride(req: BookRideRequest):
    """
    Returns distance, price and ETA for a given start/end coordinate pair.
    No ride is created.
    """
    distance = haversine_km(req.start_lat, req.start_lon, req.end_lat, req.end_lon)
    return RideEstimateResponse(
        distance_km=round(distance, 2),
        price_eur=calculate_price(distance),
        eta_minutes=calculate_eta(distance),
    )


@app.post(
    "/rides",
    response_model=RideResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book a ride and start the SAGA",
)
async def book_ride(req: BookRideRequest, db: Session = Depends(get_db)):
    """
    1. Calculates distance / price / ETA.
    2. Persists a new Ride with status PENDING.
    3. Publishes `ride.created` to Kafka → kicks off the SAGA.
    """
    distance    = haversine_km(req.start_lat, req.start_lon, req.end_lat, req.end_lon)
    price       = calculate_price(distance)
    eta         = calculate_eta(distance)

    ride = Ride(
        id          = str(uuid.uuid4()),
        username    = req.username,
        start_lat   = req.start_lat,
        start_lon   = req.start_lon,
        end_lat     = req.end_lat,
        end_lon     = req.end_lon,
        distance_km = round(distance, 2),
        price_eur   = price,
        eta_minutes = eta,
        status      = RideStatus.PENDING,
    )

    db.add(ride)
    db.commit()
    db.refresh(ride)
    logger.info("Ride %s created for user '%s'", ride.id, ride.username)

    # SAGA step 1 – publish ride.created
    await publish(
        topic=settings.kafka_topic_ride_created,
        key=ride.id,
        payload={
            "ride_id":      ride.id,
            "username":     ride.username,
            "price_eur":    ride.price_eur,
            "distance_km":  ride.distance_km,
            "eta_minutes":  ride.eta_minutes,
            "start_lat":    ride.start_lat,
            "start_lon":    ride.start_lon,
            "end_lat":      ride.end_lat,
            "end_lon":      ride.end_lon,
        },
    )

    return ride


@app.get(
    "/rides/{ride_id}",
    response_model=RideResponse,
    summary="Get current ride status",
)
def get_ride(ride_id: str, db: Session = Depends(get_db)):
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    return ride


@app.get(
    "/rides",
    response_model=List[RideResponse],
    summary="List all rides for a user",
)
def list_rides(username: str, db: Session = Depends(get_db)):
    return db.query(Ride).filter(Ride.username == username).all()


@app.patch(
    "/rides/{ride_id}/location",
    response_model=RideResponse,
    summary="Update driver's current position during a ride",
)
async def update_location(
    ride_id: str,
    req: UpdateLocationRequest,
    db: Session = Depends(get_db),
):
    """
    Called (or triggered via Kafka event) to push GPS position updates.
    Persists the position and re-publishes a `location.updated` event so
    other consumers (e.g. the frontend via SSE/WebSocket) can react.
    """
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    if ride.status not in (RideStatus.DRIVER_ASSIGNED, RideStatus.IN_PROGRESS):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot update location for ride in status {ride.status}",
        )

    # Transition to IN_PROGRESS on first location update
    if ride.status == RideStatus.DRIVER_ASSIGNED:
        ride.status = RideStatus.IN_PROGRESS

    ride.current_lat = req.current_lat
    ride.current_lon = req.current_lon
    db.commit()
    db.refresh(ride)

    await publish(
        topic="location.updated",
        key=ride_id,
        payload={
            "ride_id":     ride_id,
            "current_lat": req.current_lat,
            "current_lon": req.current_lon,
            "status":      ride.status,
        },
    )

    return ride


@app.post(
    "/rides/{ride_id}/cancel",
    response_model=RideResponse,
    summary="Manually cancel a ride (compensating transaction)",
)
async def cancel_ride(ride_id: str, db: Session = Depends(get_db)):
    """
    Explicit cancellation endpoint – mirrors what the SAGA consumer does
    automatically on `payment.failed` / `driver.not_found`.
    """
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    if ride.status in (RideStatus.COMPLETED, RideStatus.CANCELLED):
        raise HTTPException(
            status_code=409,
            detail=f"Ride already in terminal status: {ride.status}",
        )

    ride.status = RideStatus.CANCELLED
    db.commit()
    db.refresh(ride)
    logger.info("Ride %s manually cancelled", ride_id)

    # Notify other services so they can compensate too
    await publish(
        topic="ride.cancelled",
        key=ride_id,
        payload={"ride_id": ride_id, "reason": "manual_cancellation"},
    )

    return ride
