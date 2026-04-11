"""
Spark Batch Job – Smart Mobility Analytics
==========================================
Reads historical ride events from MongoDB (written there by ride-service
or collected from Kafka) and computes KPIs for the last N hours.

KPIs computed:
  - total_rides          : number of rides in window
  - completed_rides      : rides that reached COMPLETED status
  - cancelled_rides      : rides that were CANCELLED
  - completion_rate_pct  : completed / total * 100
  - avg_price_eur        : average ride price
  - avg_distance_km      : average ride distance
  - avg_eta_minutes      : average estimated trip time
  - revenue_eur          : total revenue (completed rides only)
  - top_users            : top 5 users by ride count
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    FloatType, StringType, StructField, StructType, TimestampType,
)

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema – matches what ride-service writes to MongoDB / Kafka
# ---------------------------------------------------------------------------

RIDE_SCHEMA = StructType([
    StructField("ride_id",      StringType(),    True),
    StructField("username",     StringType(),    True),
    StructField("status",       StringType(),    True),
    StructField("price_eur",    FloatType(),     True),
    StructField("distance_km",  FloatType(),     True),
    StructField("eta_minutes",  FloatType(),     True),
    StructField("created_at",   TimestampType(), True),
])


# ---------------------------------------------------------------------------
# Spark session factory
# ---------------------------------------------------------------------------

def _get_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName(settings.spark_app_name)
        .master(settings.spark_master)
        # MongoDB connector (jar must be on classpath in production)
        .config(
            "spark.mongodb.input.uri",
            f"{settings.mongo_url}/{settings.mongo_db}.rides",
        )
        .config(
            "spark.mongodb.output.uri",
            f"{settings.mongo_url}/{settings.mongo_db}.{settings.mongo_collection}",
        )
        .getOrCreate()
    )


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_rides_from_mongo(spark: SparkSession, since: datetime):
    """
    Load ride documents from MongoDB written after `since`.
    Requires the mongo-spark-connector JAR on the classpath.
    Falls back to an empty DataFrame with the correct schema if unavailable.
    """
    try:
        df = (
            spark.read
            .format("com.mongodb.spark.sql.DefaultSource")
            .option("collection", "rides")
            .load()
        )
        # Filter to analysis window
        df = df.filter(F.col("created_at") >= F.lit(since))
        logger.info("Loaded %d rides from MongoDB", df.count())
        return df
    except Exception as exc:
        logger.warning("MongoDB load failed (%s) – using empty DataFrame", exc)
        return spark.createDataFrame([], schema=RIDE_SCHEMA)


def _load_rides_from_kafka(spark: SparkSession, since: datetime):
    """
    Alternative: read ride.created events directly from Kafka.
    Uses Spark Structured Streaming in batch mode (readStream not needed here).
    """
    try:
        raw = (
            spark.read
            .format("kafka")
            .option("kafka.bootstrap.servers", settings.kafka_bootstrap_servers)
            .option("subscribe", settings.kafka_topic_rides)
            .option("startingOffsets", "earliest")
            .load()
        )
        from pyspark.sql.functions import from_json, col
        df = (
            raw
            .select(from_json(col("value").cast("string"), RIDE_SCHEMA).alias("data"))
            .select("data.*")
            .filter(F.col("created_at") >= F.lit(since))
        )
        logger.info("Loaded rides from Kafka topic: %s", settings.kafka_topic_rides)
        return df
    except Exception as exc:
        logger.warning("Kafka load failed (%s) – using empty DataFrame", exc)
        return spark.createDataFrame([], schema=RIDE_SCHEMA)


# ---------------------------------------------------------------------------
# KPI computation
# ---------------------------------------------------------------------------

def _compute_kpis(df) -> Dict[str, Any]:
    """
    Run all aggregations on the rides DataFrame.
    Returns a plain dict ready to be stored in MongoDB.
    """
    total = df.count()

    if total == 0:
        logger.info("No rides in window – returning zero KPIs")
        return {
            "total_rides":         0,
            "completed_rides":     0,
            "cancelled_rides":     0,
            "completion_rate_pct": 0.0,
            "avg_price_eur":       0.0,
            "avg_distance_km":     0.0,
            "avg_eta_minutes":     0.0,
            "revenue_eur":         0.0,
            "top_users":           [],
        }

    # Status counts
    status_counts = (
        df.groupBy("status")
        .count()
        .collect()
    )
    counts_by_status = {row["status"]: row["count"] for row in status_counts}
    completed = counts_by_status.get("COMPLETED", 0)
    cancelled = counts_by_status.get("CANCELLED", 0)

    # Aggregations on all rides
    agg_row = df.agg(
        F.round(F.avg("price_eur"),   2).alias("avg_price"),
        F.round(F.avg("distance_km"), 2).alias("avg_distance"),
        F.round(F.avg("eta_minutes"), 2).alias("avg_eta"),
    ).collect()[0]

    # Revenue – only from completed rides
    revenue_row = (
        df.filter(F.col("status") == "COMPLETED")
        .agg(F.round(F.sum("price_eur"), 2).alias("revenue"))
        .collect()[0]
    )
    revenue = float(revenue_row["revenue"] or 0.0)

    # Top 5 users by ride count
    top_users = (
        df.groupBy("username")
        .count()
        .orderBy(F.desc("count"))
        .limit(5)
        .collect()
    )

    completion_rate = round((completed / total) * 100, 1) if total > 0 else 0.0

    return {
        "total_rides":         total,
        "completed_rides":     completed,
        "cancelled_rides":     cancelled,
        "completion_rate_pct": completion_rate,
        "avg_price_eur":       float(agg_row["avg_price"]    or 0.0),
        "avg_distance_km":     float(agg_row["avg_distance"] or 0.0),
        "avg_eta_minutes":     float(agg_row["avg_eta"]      or 0.0),
        "revenue_eur":         revenue,
        "top_users": [
            {"username": r["username"], "ride_count": r["count"]}
            for r in top_users
        ],
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_batch_job(source: str = "mongo") -> Dict[str, Any]:
    """
    Execute the full Spark batch job.

    Args:
        source: "mongo" (default) or "kafka"

    Returns:
        Dict with all computed KPIs.
    """
    since = datetime.utcnow() - timedelta(hours=settings.lookback_hours)
    logger.info(
        "Starting Spark batch job | source=%s | window=%dh | since=%s",
        source, settings.lookback_hours, since.isoformat(),
    )

    spark = _get_spark()
    spark.sparkContext.setLogLevel("WARN")

    try:
        if source == "kafka":
            df = _load_rides_from_kafka(spark, since)
        else:
            df = _load_rides_from_mongo(spark, since)

        kpis = _compute_kpis(df)
        logger.info("KPIs computed: %s", kpis)
        return kpis

    finally:
        spark.stop()
        logger.info("Spark session stopped")
