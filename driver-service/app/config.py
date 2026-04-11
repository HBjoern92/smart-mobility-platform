from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_ride_created:      str = "ride.created"
    kafka_topic_driver_assigned:   str = "driver.assigned"
    kafka_topic_driver_not_found:  str = "driver.not_found"
    kafka_topic_ride_completed:    str = "ride.completed"
    kafka_topic_ride_cancelled:    str = "ride.cancelled"
    kafka_consumer_group:          str = "driver-service-group"

    class Config:
        env_file = ".env"


settings = Settings()
