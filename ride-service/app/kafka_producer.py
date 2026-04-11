import json
import logging
from typing import Any, Dict

from aiokafka import AIOKafkaProducer

from app.config import settings

logger = logging.getLogger(__name__)

_producer: AIOKafkaProducer | None = None


async def get_producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
        )
        await _producer.start()
        logger.info("Kafka producer started")
    return _producer


async def stop_producer() -> None:
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None
        logger.info("Kafka producer stopped")


async def publish(topic: str, payload: Dict[str, Any], key: str | None = None) -> None:
    """Publish a JSON payload to a Kafka topic."""
    producer = await get_producer()
    await producer.send_and_wait(topic, value=payload, key=key)
    logger.info("Published to %s: %s", topic, payload)
