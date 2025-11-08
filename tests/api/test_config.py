"""Tests for configuration."""

import pytest

from src.api.config import Settings


class TestSettings:
    """Test settings configuration."""

    def test_cors_origins_wildcard(self) -> None:
        """Test CORS origins with wildcard."""
        config = Settings(api_cors_origins="*")
        assert config.cors_origins_list == ["*"]

    def test_s3_allowed_buckets_empty(self) -> None:
        """Test empty S3 bucket whitelist allows all."""
        config = Settings(s3_allowed_buckets="")
        assert config.s3_allowed_buckets_list == []
