import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from app.config import settings
from app.kafka_producer import publish
from app.store import get_available_driver, set_available

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _handle_ride_created(payload: dict) -> None:
    """
    SAGA step 3 – assign an available driver to the ride.

    Happy path:  find driver → mark unavailable → publish driver.assigned
    Sad path:    no driver   → publish driver.not_found  (compensating trigger)
    """
    ride_id = payload.get("ride_id")
    if not ride_id:
        logger.warning("ride.created missing ride_id: %s", payload)
        return

    driver = await get_available_driver()

    if driver:
        driver_id = driver["driver_id"]
        await set_available(driver_id, available=False, ride_id=ride_id)
        logger.info("Driver %s assigned to ride %s", driver_id, ride_id)

        await publish(
            topic=settings.kafka_topic_driver_assigned,
            key=ride_id,
            payload={
                "ride_id":   ride_id,
                "driver_id": driver_id,
                "driver_name": driver["name"],
            },
        )
    else:
        logger.warning("No available driver for ride %s – firing driver.not_found", ride_id)
        await publish(
            topic=settings.kafka_topic_driver_not_found,
            key=ride_id,
            payload={
                "ride_id": ride_id,
                "reason":  "no_driver_available",
            },
        )


async def _handle_ride_completed(payload: dict) -> None:
    """
    Ride finished – free up the driver again.
    """
    ride_id   = payload.get("ride_id")
    driver_id = payload.get("driver_id")

    if not driver_id:
        logger.warning("ride.completed missing driver_id: %s", payload)
        return

    await set_available(driver_id, available=True, ride_id="")
    logger.info("Driver %s is now available again (ride %s completed)", driver_id, ride_id)


async def _handle_ride_cancelled(payload: dict) -> None:
    """
    Compensating transaction – ride was cancelled, free up driver if assigned.
    """
    ride_id   = payload.get("ride_id")
    driver_id = payload.get("driver_id")

    if driver_id:
        await set_available(driver_id, available=True, ride_id="")
        logger.info("Driver %s freed due to ride %s cancellation", driver_id, ride_id)


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

HANDLERS = {
    settings.kafka_topic_ride_created:   _handle_ride_created,
    settings.kafka_topic_ride_completed: _handle_ride_completed,
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
    logger.info("Driver consumer started, listening on: %s", topics)

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
        logger.info("Driver consumer cancelled – shutting down")
    finally:
        await consumer.stop()
        logger.info("Driver consumer stopped")
