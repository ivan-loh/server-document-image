"""Tests for API models."""

import pytest
from pydantic import ValidationError

from src.api.models import RenderRequest


class TestRenderRequest:
    """Test render request model."""

    def test_page_validation_minimum(self) -> None:
        """Test page number must be >= 1."""
        with pytest.raises(ValidationError):
            RenderRequest(s3_url="https://s3.amazonaws.com/bucket/file.pdf", page=0)
