import os
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_default_db() -> str:
    # If /data persistent volume is mounted (e.g. Railway / Render / Fly), store permanently
    if Path("/data").exists() and os.access("/data", os.W_OK):
        return "/data/devengers_mail.db"
    return "devengers_mail.db"


def _resolve_default_uploads() -> str:
    if Path("/data").exists() and os.access("/data", os.W_OK):
        return "/data/uploads"
    return "uploads"


class Settings(BaseSettings):
    """Configuration settings for Devengers Mail Engine."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # SMTP Server Settings (Brevo 300/day Free Relay by default; supports Zoho / ZeptoMail)
    smtp_host: str = Field(default="smtp-relay.brevo.com", description="SMTP Relay Host")
    smtp_port: int = Field(default=587, description="SMTP Port (587 TLS / 465 SSL)")
    smtp_use_ssl: bool = Field(default=False, description="Connect via SSL (port 465)")
    smtp_use_tls: bool = Field(default=True, description="Connect via STARTTLS (port 587)")
    smtp_user: str = Field(default="", description="SMTP Username / Login")
    smtp_password: str = Field(default="", description="SMTP Password / Key")

    # Brand and Routing
    sender_name: str = Field(default="Team DEVENGERS", description="Friendly sender name")
    sender_email: str = Field(default="event@devengers.org", description="From address")
    reply_to_email: str = Field(default="support@devengers.org", description="Reply-To address")
    primary_inbox_mode: bool = Field(default=True, description="Route to Gmail Primary inbox by omitting bulk marketing headers")

    # Quota & Rate Limiting (Brevo 300/day limit + Website OTP protection)
    daily_send_limit: int = Field(default=300, description="Total daily allowance across account")
    otp_reserve_buffer: int = Field(default=10, description="Credits always reserved for website OTPs")
    brevo_api_key: str = Field(default="", description="Brevo v3 API Key to sync live OTP credit usage")
    send_delay_seconds_min: float = Field(default=5.0, description="Minimum jitter delay between sends")
    send_delay_seconds_max: float = Field(default=10.0, description="Maximum jitter delay between sends")
    batch_size: int = Field(default=25, description="Number of emails before taking a longer breather")
    batch_pause_seconds: float = Field(default=30.0, description="Breather duration between batches")

    # Storage Paths
    database_path: str = Field(default_factory=_resolve_default_db, description="Path to SQLite database")
    upload_dir: str = Field(default_factory=_resolve_default_uploads, description="Directory for uploaded candidate files")

    # Operational Modes
    dry_run: bool = Field(default=False, description="Simulate sending without contacting SMTP")
    debug: bool = Field(default=False, description="Verbose logging")

    @field_validator("sender_email", "reply_to_email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if "@" not in clean or "." not in clean.split("@")[-1]:
            raise ValueError(f"Invalid email format: {v}")
        return clean

    @property
    def formatted_from(self) -> str:
        return f"{self.sender_name} <{self.sender_email}>"

    @property
    def provider_name(self) -> str:
        h = self.smtp_host.lower()
        if "brevo" in h or "sendinblue" in h:
            return "Brevo Relay (Free 300/day)"
        elif "zoho" in h or "zeptomail" in h:
            return "Zoho Mail / ZeptoMail"
        return f"SMTP Relay ({self.smtp_host})"

    @property
    def db_file_path(self) -> Path:
        return Path(self.database_path).resolve()

    @property
    def uploads_path(self) -> Path:
        p = Path(self.upload_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p


# Singleton instance
settings = Settings()
