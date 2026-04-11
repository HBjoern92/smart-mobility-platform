from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models import RideStatus


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class BookRideRequest(BaseModel):
    username:  str   = Field(..., min_length=1, max_length=64, examples=["alice"])
    start_lat: float = Field(..., ge=-90,  le=90,  examples=[48.1351])
    start_lon: float = Field(..., ge=-180, le=180, examples=[11.5820])
    end_lat:   float = Field(..., ge=-90,  le=90,  examples=[48.1900])
    end_lon:   float = Field(..., ge=-180, le=180, examples=[11.6200])


class UpdateLocationRequest(BaseModel):
    current_lat: float = Field(..., ge=-90,  le=90)
    current_lon: float = Field(..., ge=-180, le=180)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class RideEstimateResponse(BaseModel):
    distance_km:  float
    price_eur:    float
    eta_minutes:  float


class RideResponse(BaseModel):
    id:           str
    username:     str
    start_lat:    float
    start_lon:    float
    end_lat:      float
    end_lon:      float
    distance_km:  float
    price_eur:    float
    eta_minutes:  float
    status:       RideStatus
    driver_id:    Optional[str]
    current_lat:  Optional[float]
    current_lon:  Optional[float]
    created_at:   datetime
    updated_at:   datetime

    model_config = {"from_attributes": True}
