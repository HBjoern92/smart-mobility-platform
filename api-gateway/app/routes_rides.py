from typing import Any, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.client import proxy_get, proxy_patch, proxy_post
from app.config import settings

router = APIRouter(prefix="/rides", tags=["Rides"])

BASE = settings.ride_service_url


# ---------------------------------------------------------------------------
# Request bodies (mirrors ride-service schemas)
# ---------------------------------------------------------------------------

class BookRideRequest(BaseModel):
    username:  str   = Field(..., examples=["alice"])
    start_lat: float = Field(..., examples=[48.1351])
    start_lon: float = Field(..., examples=[11.5820])
    end_lat:   float = Field(..., examples=[48.1900])
    end_lon:   float = Field(..., examples=[11.6200])


class EstimateRequest(BaseModel):
    username:  str   = Field(..., examples=["alice"])
    start_lat: float = Field(..., examples=[48.1351])
    start_lon: float = Field(..., examples=[11.5820])
    end_lat:   float = Field(..., examples=[48.1900])
    end_lon:   float = Field(..., examples=[11.6200])


class UpdateLocationRequest(BaseModel):
    current_lat: float
    current_lon: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/estimate", summary="Get price & ETA estimate")
async def estimate_ride(req: EstimateRequest) -> Any:
    return await proxy_post(f"{BASE}/rides/estimate", req.model_dump())


@router.post("", summary="Book a ride (starts SAGA)", status_code=201)
async def book_ride(req: BookRideRequest) -> Any:
    return await proxy_post(f"{BASE}/rides", req.model_dump())


@router.get("", summary="List rides for a user")
async def list_rides(username: str = Query(..., examples=["alice"])) -> Any:
    return await proxy_get(f"{BASE}/rides?username={username}")


@router.get("/{ride_id}", summary="Get ride status")
async def get_ride(ride_id: str) -> Any:
    return await proxy_get(f"{BASE}/rides/{ride_id}")


@router.patch("/{ride_id}/location", summary="Update driver position")
async def update_location(ride_id: str, req: UpdateLocationRequest) -> Any:
    return await proxy_patch(f"{BASE}/rides/{ride_id}/location", req.model_dump())


@router.post("/{ride_id}/cancel", summary="Cancel a ride")
async def cancel_ride(ride_id: str) -> Any:
    return await proxy_post(f"{BASE}/rides/{ride_id}/cancel", {})
