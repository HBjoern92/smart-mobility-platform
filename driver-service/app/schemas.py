from typing import Optional
from pydantic import BaseModel, Field


class RegisterDriverRequest(BaseModel):
    driver_id: str = Field(..., min_length=1, max_length=64, examples=["driver-42"])
    name:      str = Field(..., min_length=1, max_length=128, examples=["Max Mustermann"])


class DriverStatusResponse(BaseModel):
    driver_id:   str
    name:        str
    available:   bool
    current_ride_id: Optional[str] = None


class AcceptRideRequest(BaseModel):
    driver_id: str = Field(..., examples=["driver-42"])


class CompleteRideRequest(BaseModel):
    driver_id: str = Field(..., examples=["driver-42"])
