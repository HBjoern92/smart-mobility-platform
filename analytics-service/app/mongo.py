import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo import MongoClient
from pymongo.collection import Collection

from app.config import settings

logger = logging.getLogger(__name__)

_client: MongoClient | None = None


def get_collection() -> Collection:
    global _client
    if _client is None:
        _client = MongoClient(settings.mongo_url)
    return _client[settings.mongo_db][settings.mongo_collection]


def save_kpi_result(kpis: Dict[str, Any], window_hours: int) -> str:
    """
    Persist a KPI result document to MongoDB.
    Returns the inserted document id as string.
    """
    col = get_collection()
    doc = {
        "computed_at":   datetime.utcnow(),
        "window_hours":  window_hours,
        "kpis":          kpis,
    }
    result = col.insert_one(doc)
    logger.info("KPI result saved to MongoDB: %s", result.inserted_id)
    return str(result.inserted_id)


def get_latest_kpis() -> Optional[Dict[str, Any]]:
    """Return the most recently computed KPI document."""
    col = get_collection()
    doc = col.find_one(sort=[("computed_at", -1)])
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


def get_kpi_history(limit: int = 10) -> List[Dict[str, Any]]:
    """Return the last `limit` KPI documents, newest first."""
    col = get_collection()
    docs = list(col.find().sort("computed_at", -1).limit(limit))
    for d in docs:
        d["_id"] = str(d["_id"])
    return docs


def close_mongo() -> None:
    global _client
    if _client:
        _client.close()
        _client = None
