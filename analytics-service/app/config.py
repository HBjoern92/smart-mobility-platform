from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MongoDB – results are written here
    mongo_url:      str = "mongodb://localhost:27017"
    mongo_db:       str = "analytics"
    mongo_collection: str = "kpi_results"

    # Kafka – event log is the data source
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_rides:       str = "ride.created"
    kafka_topic_completed:   str = "ride.completed"

    # Spark
    spark_app_name:  str = "SmartMobilityAnalytics"
    spark_master:    str = "local[*]"   # on K8s: spark://spark-master:7077

    # How many hours of history to analyse per batch run
    lookback_hours: int = 24

    class Config:
        env_file = ".env"


settings = Settings()
