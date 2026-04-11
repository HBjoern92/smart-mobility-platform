import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException

from app.kafka_consumer import start_consumer
from app.kafka_producer import stop_producer
from app.schemas import PaymentResponse
from app.store import get_payment, list_payments

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
    logger.info("Payment service started")

    yield

    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await stop_producer()
    logger.info("Payment service shut down cleanly")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Payment Service",
    description="Smart Mobility Platform – Simulated payment processing",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "payment-service"}


@app.get(
    "/payments/{ride_id}",
    response_model=PaymentResponse,
    summary="Get payment status for a ride",
)
def get_payment_status(ride_id: str):
    record = get_payment(ride_id)
    if not record:
        raise HTTPException(status_code=404, detail="No payment found for this ride")
    return PaymentResponse(
        ride_id=record.ride_id,
        username=record.username,
        amount_eur=record.amount_eur,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@app.get(
    "/payments",
    response_model=List[PaymentResponse],
    summary="List all payment records (for debugging)",
)
def get_all_payments():
    return [
        PaymentResponse(
            ride_id=r.ride_id,
            username=r.username,
            amount_eur=r.amount_eur,
            status=r.status,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in list_payments()
    ]
