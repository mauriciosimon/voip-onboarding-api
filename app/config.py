from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./voip_onboarding.db"

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440  # 24 hours

    # FreePBX
    freepbx_host: str
    freepbx_api_token: str
    freepbx_api_user: str = "admin"

    # SIP Domain (for client config)
    sip_domain: str
    sip_port: int = 5060
    sip_transport: str = "udp"

    # Extension numbering
    extension_start: int = 1000

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
