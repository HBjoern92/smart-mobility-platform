import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


class PaymentStatus(str, enum.Enum):
    PENDING   = "PENDING"
    SUCCESS   = "SUCCESS"
    FAILED    = "FAILED"
    REFUNDED  = "REFUNDED"


@dataclass
class PaymentRecord:
    ride_id:    str
    username:   str
    amount_eur: float
    status:     PaymentStatus = PaymentStatus.PENDING
    created_at: datetime      = field(default_factory=datetime.utcnow)
    updated_at: datetime      = field(default_factory=datetime.utcnow)


# Simple in-memory store: ride_id → PaymentRecord
# (Good enough for this project – a real system would use a DB)
_payments: Dict[str, PaymentRecord] = {}


def create_payment(ride_id: str, username: str, amount_eur: float) -> PaymentRecord:
    record = PaymentRecord(
        ride_id=ride_id,
        username=username,
        amount_eur=amount_eur,
    )
    _payments[ride_id] = record
    return record


def get_payment(ride_id: str) -> Optional[PaymentRecord]:
    return _payments.get(ride_id)


def update_status(ride_id: str, status: PaymentStatus) -> Optional[PaymentRecord]:
    record = _payments.get(ride_id)
    if record:
        record.status = status
        record.updated_at = datetime.utcnow()
    return record


def list_payments() -> list[PaymentRecord]:
    return list(_payments.values())
