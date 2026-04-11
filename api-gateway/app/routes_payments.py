from typing import Any

from fastapi import APIRouter

from app.client import proxy_get
from app.config import settings

router = APIRouter(prefix="/payments", tags=["Payments"])

BASE = settings.payment_service_url


@router.get("", summary="List all payment records")
async def list_payments() -> Any:
    return await proxy_get(f"{BASE}/payments")


@router.get("/{ride_id}", summary="Get payment status for a ride")
async def get_payment(ride_id: str) -> Any:
    return await proxy_get(f"{BASE}/payments/{ride_id}")
