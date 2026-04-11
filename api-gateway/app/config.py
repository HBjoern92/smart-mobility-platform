from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Downstream service URLs
    ride_service_url:    str = "http://localhost:8001"
    driver_service_url:  str = "http://localhost:8002"
    payment_service_url: str = "http://localhost:8003"

    # Gateway port (informational, used in docs)
    port: int = 8000

    class Config:
        env_file = ".env"


settings = Settings()
