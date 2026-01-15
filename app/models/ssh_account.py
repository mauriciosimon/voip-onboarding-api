from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class SSHAccount(Base):
    """SSH Account for FreePBX connections"""
    __tablename__ = "ssh_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # Friendly name like "Production PBX"
    host = Column(String, nullable=False)  # FreePBX host
    ssh_user = Column(String, nullable=False, default="root")
    ssh_key_path = Column(String, nullable=False)  # Path to SSH private key

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship to users
    users = relationship("User", back_populates="ssh_account")
