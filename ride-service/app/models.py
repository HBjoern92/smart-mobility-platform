import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Enum, Float, String, create_engine
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


# ---------------------------------------------------------------------------
# Engine & session
# ---------------------------------------------------------------------------

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,   # detect stale connections
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RideStatus(str, enum.Enum):
    PENDING           = "PENDING"            # ride booked, SAGA started
    PAYMENT_PROCESSED = "PAYMENT_PROCESSED"  # payment OK
    DRIVER_ASSIGNED   = "DRIVER_ASSIGNED"    # driver confirmed
    IN_PROGRESS       = "IN_PROGRESS"        # ride ongoing
    COMPLETED         = "COMPLETED"          # arrived at destination
    CANCELLED         = "CANCELLED"          # compensating transaction fired


# ---------------------------------------------------------------------------
# ORM model
# ---------------------------------------------------------------------------

class Ride(Base):
    __tablename__ = "rides"

    id             = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username       = Column(String, nullable=False)

    # Coordinates (simplified: lat/lon as floats)
    start_lat      = Column(Float, nullable=False)
    start_lon      = Column(Float, nullable=False)
    end_lat        = Column(Float, nullable=False)
    end_lon        = Column(Float, nullable=False)

    # Computed at booking time
    distance_km    = Column(Float, nullable=False)
    price_eur      = Column(Float, nullable=False)
    eta_minutes    = Column(Float, nullable=False)

    status         = Column(Enum(RideStatus), nullable=False, default=RideStatus.PENDING)

    # Driver assigned during SAGA step 3
    driver_id      = Column(String, nullable=True)

    # Live position (updated by location.updated events)
    current_lat    = Column(Float, nullable=True)
    current_lon    = Column(Float, nullable=True)

    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Ride id={self.id} status={self.status}>"


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

def create_tables() -> None:
    """Create all tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: yields a DB session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
