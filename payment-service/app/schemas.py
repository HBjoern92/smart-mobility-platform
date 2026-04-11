from datetime import datetime
from pydantic import BaseModel
from app.store import PaymentStatus


class PaymentResponse(BaseModel):
    ride_id:    str
    username:   str
    amount_eur: float
    status:     PaymentStatus
    created_at: datetime
    updated_at: datetime
