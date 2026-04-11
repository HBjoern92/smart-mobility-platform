from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://ride_user:ride_pass@localhost:5432/ride_db"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_ride_created: str = "ride.created"
    kafka_topic_payment_failed: str = "payment.failed"
    kafka_topic_driver_not_found: str = "driver.not_found"
    kafka_topic_payment_processed: str = "payment.processed"
    kafka_topic_driver_assigned: str = "driver.assigned"
    kafka_topic_ride_completed: str = "ride.completed"
    kafka_consumer_group: str = "ride-service-group"

    # Pricing
    price_per_km: float = 2.50       # EUR per km
    speed_kmh: float = 40.0          # constant speed assumption

    class Config:
        env_file = ".env"


settings = Settings()
