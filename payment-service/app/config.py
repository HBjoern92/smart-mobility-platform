from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_ride_created:      str = "ride.created"
    kafka_topic_payment_processed: str = "payment.processed"
    kafka_topic_payment_failed:    str = "payment.failed"
    kafka_topic_ride_cancelled:    str = "ride.cancelled"
    kafka_consumer_group:          str = "payment-service-group"

    # Simulated failure rate for testing (0.0 = always succeed)
    simulate_failure_rate: float = 0.0

    class Config:
        env_file = ".env"


settings = Settings()
