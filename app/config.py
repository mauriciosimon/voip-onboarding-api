from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
import os


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./voip_onboarding.db"

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440  # 24 hours

    # FreePBX/SSH Configuration (legacy - now uses SSHAccount in DB)
    freepbx_host: Optional[str] = None
    ssh_user: str = "root"
    ssh_key_path: str = "freepbx_key"

    # SIP Domain (for client config)
    sip_domain: str = "voip.example.com"
    sip_port: int = 5060
    sip_transport: str = "udp"

    # Admin Configuration (legacy - now uses AdminUser in DB)
    admin_password: Optional[str] = None

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
