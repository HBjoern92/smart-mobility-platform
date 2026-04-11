import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.client import close_client, get_client
from app.config import settings
from app.routes_drivers import router as drivers_router
from app.routes_payments import router as payments_router
from app.routes_rides import router as rides_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_client()          # warm up connection pool
    logger.info("API Gateway started – routing to:")
    logger.info("  Ride Service    → %s", settings.ride_service_url)
    logger.info("  Driver Service  → %s", settings.driver_service_url)
    logger.info("  Payment Service → %s", settings.payment_service_url)

    yield

    await close_client()
    logger.info("API Gateway shut down cleanly")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Smart Mobility API Gateway",
    description="""
## Smart Mobility Platform – API Gateway

Single entry point for all clients. Proxies requests to:

| Service         | Internal URL              |
|-----------------|---------------------------|
| Ride Service    | ride-service:8001         |
| Driver Service  | driver-service:8002       |
| Payment Service | payment-service:8003      |

### Typical flow
1. `POST /rides/estimate` – get price & ETA
2. `POST /rides` – book ride (kicks off SAGA)
3. `GET /rides/{id}` – poll status
4. `POST /drivers/rides/{id}/complete` – driver arrives
5. `GET /payments/{ride_id}` – check payment
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# Allow frontend (running on a different port) to call the gateway
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(rides_router)
app.include_router(drivers_router)
app.include_router(payments_router)


# ---------------------------------------------------------------------------
# Health / info
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Meta"])
def health_check():
    return {"status": "ok", "service": "api-gateway"}


@app.get("/", tags=["Meta"])
def root():
    return {
        "service": "Smart Mobility API Gateway",
        "docs":    "/docs",
        "health":  "/health",
        "upstream": {
            "ride_service":    settings.ride_service_url,
            "driver_service":  settings.driver_service_url,
            "payment_service": settings.payment_service_url,
        },
    }
