import asyncio
import json
import logging
import random

from aiokafka import AIOKafkaConsumer

from app.config import settings
from app.kafka_producer import publish
from app.store import PaymentStatus, create_payment, get_payment, update_status

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Payment logic (simulated)
# ---------------------------------------------------------------------------

def _process_payment(amount_eur: float) -> bool:
    """
    Simulated payment processing.
    Always returns True – as per project spec (return true).
    Set SIMULATE_FAILURE_RATE > 0 in .env to test the sad path.
    """
    if settings.simulate_failure_rate > 0:
        return random.random() >= settings.simulate_failure_rate
    return True


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _handle_ride_created(payload: dict) -> None:
    """
    SAGA step 2 – process payment for a newly created ride.

    Happy path: payment OK  → publish payment.processed
    Sad path:   payment NOK → publish payment.failed  (compensating trigger)
    """
    ride_id    = payload.get("ride_id")
    username   = payload.get("username")
    price_eur  = payload.get("price_eur", 0.0)

    if not ride_id or not username:
        logger.warning("ride.created missing required fields: %s", payload)
        return

    # Idempotency guard – don't process the same ride twice
    existing = get_payment(ride_id)
    if existing:
        logger.info("Payment for ride %s already exists (%s) – skipping", ride_id, existing.status)
        return

    record = create_payment(ride_id=ride_id, username=username, amount_eur=price_eur)
    logger.info("Processing payment for ride %s (%.2f EUR)", ride_id, price_eur)

    success = _process_payment(price_eur)

    if success:
        update_status(ride_id, PaymentStatus.SUCCESS)
        logger.info("Payment SUCCESS for ride %s", ride_id)

        await publish(
            topic=settings.kafka_topic_payment_processed,
            key=ride_id,
            payload={
                "ride_id":    ride_id,
                "username":   username,
                "amount_eur": price_eur,
            },
        )
    else:
        update_status(ride_id, PaymentStatus.FAILED)
        logger.warning("Payment FAILED for ride %s", ride_id)

        await publish(
            topic=settings.kafka_topic_payment_failed,
            key=ride_id,
            payload={
                "ride_id": ride_id,
                "reason":  "payment_declined",
            },
        )


async def _handle_ride_cancelled(payload: dict) -> None:
    """
    Compensating transaction – ride was cancelled after payment succeeded.
    Issue a refund (simulated).
    """
    ride_id = payload.get("ride_id")
    if not ride_id:
        return

    record = get_payment(ride_id)
    if not record:
        logger.info("No payment record for cancelled ride %s – nothing to refund", ride_id)
        return

    if record.status == PaymentStatus.SUCCESS:
        update_status(ride_id, PaymentStatus.REFUNDED)
        logger.info("Payment REFUNDED for ride %s (%.2f EUR)", ride_id, record.amount_eur)
    else:
        logger.info(
            "Ride %s cancelled but payment status is %s – no refund needed",
            ride_id, record.status,
        )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

HANDLERS = {
    settings.kafka_topic_ride_created:   _handle_ride_created,
    settings.kafka_topic_ride_cancelled: _handle_ride_cancelled,
}


# ---------------------------------------------------------------------------
# Consumer loop
# ---------------------------------------------------------------------------

async def start_consumer() -> None:
    topics = list(HANDLERS.keys())
    consumer = AIOKafkaConsumer(
        *topics,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
    )

    await consumer.start()
    logger.info("Payment consumer started, listening on: %s", topics)

    try:
        async for msg in consumer:
            handler = HANDLERS.get(msg.topic)
            if handler:
                try:
                    await handler(msg.value)
                except Exception as exc:
                    logger.exception("Error handling [%s]: %s", msg.topic, exc)
            else:
                logger.warning("No handler for topic: %s", msg.topic)

    except asyncio.CancelledError:
        logger.info("Payment consumer cancelled – shutting down")
    finally:
        await consumer.stop()
        logger.info("Payment consumer stopped")
