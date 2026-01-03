from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from app.database import Base


class TrustedIP(Base):
    __tablename__ = "trusted_ips"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, nullable=True)  # Optional: track which user added it
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    @staticmethod
    def calculate_expiry(hours: int = 2) -> datetime:
        """Calculate expiration time from now (hours)"""
        return datetime.utcnow() + timedelta(hours=hours)

    @staticmethod
    def calculate_expiry_minutes(minutes: int = 2) -> datetime:
        """Calculate expiration time from now (minutes)"""
        return datetime.utcnow() + timedelta(minutes=minutes)

    @property
    def is_expired(self) -> bool:
        """Check if this IP has expired"""
        return datetime.utcnow() > self.expires_at
