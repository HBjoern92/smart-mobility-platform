from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MongoDB
    mongo_url:        str = "mongodb://localhost:27017"
    mongo_db:         str = "analytics"
    mongo_collection: str = "kpi_results"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_rides:       str = "ride.created"
    kafka_topic_completed:   str = "ride.completed"

    # Spark Connect (DHBW Cluster, Gruppe 3)
    spark_connect_host:  str = "10.3.15.18"
    spark_connect_port:  int = 15013
    spark_connect_token: str = "XLai6PfZcuTiebU6YiCiW3XQnuebLGGwXGsJiYyPoFiwEFjattjsnYERFvG2jZrF"

    # Spark App Name (fuer Logs)
    spark_app_name: str = "SmartMobilityAnalytics"

    # Lookback Fenster
    lookback_hours: int = 24

    class Config:
        env_file = ".env"


settings = Settings()
