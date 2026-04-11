import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from app.config import settings
from app.models import Ride, RideStatus, SessionLocal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _handle_payment_failed(payload: dict, db) -> None:
    """
    SAGA compensating transaction – step 1 failure.
    Payment could not be processed → cancel the ride immediately.
    """
    ride_id = payload.get("ride_id")
    if not ride_id:
        logger.warning("payment.failed event missing ride_id: %s", payload)
        return

    ride: Ride | None = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        logger.warning("payment.failed: ride %s not found", ride_id)
        return

    if ride.status in (RideStatus.PENDING, RideStatus.PAYMENT_PROCESSED):
        ride.status = RideStatus.CANCELLED
        db.commit()
        logger.info("Ride %s CANCELLED due to payment failure", ride_id)
    else:
        logger.info(
            "payment.failed received but ride %s already in status %s – ignoring",
            ride_id, ride.status,
        )


def _handle_driver_not_found(payload: dict, db) -> None:
    """
    SAGA compensating transaction – step 2 failure.
    No driver available → cancel the ride.
    Payment service will be notified separately via its own consumer.
    """
    ride_id = payload.get("ride_id")
    if not ride_id:
        logger.warning("driver.not_found event missing ride_id: %s", payload)
        return

    ride: Ride | None = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        logger.warning("driver.not_found: ride %s not found", ride_id)
        return

    if ride.status != RideStatus.CANCELLED:
        ride.status = RideStatus.CANCELLED
        db.commit()
        logger.info("Ride %s CANCELLED – no driver found", ride_id)


def _handle_payment_processed(payload: dict, db) -> None:
    """SAGA step 2 success – payment went through, advance ride status."""
    ride_id = payload.get("ride_id")
    ride: Ride | None = db.query(Ride).filter(Ride.id == ride_id).first() if ride_id else None
    if ride and ride.status == RideStatus.PENDING:
        ride.status = RideStatus.PAYMENT_PROCESSED
        db.commit()
        logger.info("Ride %s → PAYMENT_PROCESSED", ride_id)


def _handle_driver_assigned(payload: dict, db) -> None:
    """SAGA step 3 success – driver confirmed the ride."""
    ride_id   = payload.get("ride_id")
    driver_id = payload.get("driver_id")
    ride: Ride | None = db.query(Ride).filter(Ride.id == ride_id).first() if ride_id else None
    if ride and ride.status == RideStatus.PAYMENT_PROCESSED:
        ride.status    = RideStatus.DRIVER_ASSIGNED
        ride.driver_id = driver_id
        db.commit()
        logger.info("Ride %s → DRIVER_ASSIGNED (driver: %s)", ride_id, driver_id)


def _handle_ride_completed(payload: dict, db) -> None:
    """Driver confirmed arrival at destination."""
    ride_id = payload.get("ride_id")
    ride: Ride | None = db.query(Ride).filter(Ride.id == ride_id).first() if ride_id else None
    if ride and ride.status in (RideStatus.DRIVER_ASSIGNED, RideStatus.IN_PROGRESS):
        ride.status = RideStatus.COMPLETED
        db.commit()
        logger.info("Ride %s → COMPLETED", ride_id)


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

HANDLERS = {
    settings.kafka_topic_payment_failed:   _handle_payment_failed,
    settings.kafka_topic_driver_not_found: _handle_driver_not_found,
    settings.kafka_topic_payment_processed: _handle_payment_processed,
    settings.kafka_topic_driver_assigned:  _handle_driver_assigned,
    settings.kafka_topic_ride_completed:   _handle_ride_completed,
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
    logger.info("Kafka consumer started, listening on: %s", topics)

    try:
        async for msg in consumer:
            topic   = msg.topic
            payload = msg.value
            logger.debug("Received [%s]: %s", topic, payload)

            handler = HANDLERS.get(topic)
            if handler:
                db = SessionLocal()
                try:
                    handler(payload, db)
                except Exception as exc:
                    logger.exception("Error handling [%s]: %s", topic, exc)
                    db.rollback()
                finally:
                    db.close()
            else:
                logger.warning("No handler for topic: %s", topic)

    except asyncio.CancelledError:
        logger.info("Consumer loop cancelled – shutting down")
    finally:
        await consumer.stop()
        logger.info("Kafka consumer stopped")
