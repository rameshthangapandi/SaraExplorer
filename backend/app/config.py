from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables / the .env file. No secrets in code."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_env: str = "development"
    app_name: str = "Sara Explorer"

    database_url: str = "sqlite+aiosqlite:///./sara_dev.db"
    redis_url: str | None = None

    # Auth
    jwt_secret: str
    jwt_issuer: str = "sara-explorer"
    access_token_minutes: int = 15
    refresh_token_days: int = 7          # "remember me" sessions
    session_hours: int = 12              # browser-session logins
    cookie_secure: bool = True
    cors_origins: str = "http://localhost:5173"
    max_failed_logins: int = 5
    lockout_minutes: int = 15

    # Groq
    groq_api_key: str = ""
    groq_chat_model: str = "openai/gpt-oss-120b"
    groq_stt_model: str = "whisper-large-v3"
    groq_reasoning_effort: str = "medium"

    # Payments
    payment_provider: str = "upi"        # upi | razorpay | mock (automated tests only)
    merchant_upi_id: str = ""            # UPI ID that receives payments (upi provider)
    merchant_name: str = "Sara Explorer"
    admin_emails: str = ""               # comma-separated; admins verify UPI payments
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    mock_payment_secret: str = ""
    default_spend_cap_inr: int = 200_000
    max_spend_cap_inr: int = 500_000
    consent_hold_minutes: int = 15

    @field_validator("jwt_secret")
    @classmethod
    def strong_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def admin_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
