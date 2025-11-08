"""Application configuration and constants."""

from dataclasses import dataclass
from typing import Dict, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass
class DeviceProfile:
    """Device-specific optimization profile."""

    max_width: int
    max_height: int
    quality: int
    format: str
    aggressive_compression: bool


DEVICE_PROFILES: Dict[str, DeviceProfile] = {
    "mobile": DeviceProfile(
        max_width=640,
        max_height=1136,
        quality=80,
        format="webp",
        aggressive_compression=True,
    ),
    "tablet": DeviceProfile(
        max_width=1024,
        max_height=1366,
        quality=85,
        format="webp",
        aggressive_compression=False,
    ),
    "desktop": DeviceProfile(
        max_width=1920,
        max_height=1080,
        quality=90,
        format="webp",
        aggressive_compression=False,
    ),
    "retina": DeviceProfile(
        max_width=3840,
        max_height=2160,
        quality=90,
        format="webp",
        aggressive_compression=False,
    ),
}

QUALITY_PRESETS: Dict[str, int] = {
    "low": 70,
    "medium": 85,
    "high": 95,
    "auto": 90,
}

MAX_INPUT_SIZE_MB = 100
MAX_OUTPUT_SIZE_MB = 10
REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_DPI = 150

CACHE_L1_SIZE_MB = 500


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    s3_timeout_seconds: int = 30
    s3_allowed_buckets: str = ""
    s3_endpoint_url: Optional[str] = None

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_cors_origins: str = "*"

    max_input_size_mb: int = 100
    max_output_size_mb: int = 10
    default_dpi: int = 150
    request_timeout_seconds: int = 30

    cache_l1_size_mb: int = 500

    log_level: str = "INFO"
    log_format: str = "json"

    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        if self.api_cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.api_cors_origins.split(",")]

    @property
    def s3_allowed_buckets_list(self) -> list[str]:
        """Parse allowed S3 buckets from comma-separated string."""
        if not self.s3_allowed_buckets:
            return []
        return [bucket.strip() for bucket in self.s3_allowed_buckets.split(",")]


settings = Settings()
