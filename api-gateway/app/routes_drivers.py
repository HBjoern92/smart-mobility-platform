from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.client import proxy_get, proxy_post
from app.config import settings

router = APIRouter(prefix="/drivers", tags=["Drivers"])

BASE = settings.driver_service_url


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class RegisterDriverRequest(BaseModel):
    driver_id: str = Field(..., examples=["driver-42"])
    name:      str = Field(..., examples=["Max Mustermann"])


class CompleteRideRequest(BaseModel):
    driver_id: str = Field(..., examples=["driver-42"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", summary="Register a new driver", status_code=201)
async def register_driver(req: RegisterDriverRequest) -> Any:
    return await proxy_post(f"{BASE}/drivers", req.model_dump())


@router.get("", summary="List all drivers")
async def list_drivers() -> Any:
    return await proxy_get(f"{BASE}/drivers")


@router.get("/{driver_id}", summary="Get driver status")
async def get_driver(driver_id: str) -> Any:
    return await proxy_get(f"{BASE}/drivers/{driver_id}")


@router.post("/{driver_id}/available", summary="Set driver as available")
async def set_available(driver_id: str) -> Any:
    return await proxy_post(f"{BASE}/drivers/{driver_id}/available", {})


@router.post("/rides/{ride_id}/complete", summary="Driver completes a ride")
async def complete_ride(ride_id: str, req: CompleteRideRequest) -> Any:
    return await proxy_post(f"{BASE}/rides/{ride_id}/complete", req.model_dump())
