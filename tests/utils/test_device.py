"""Tests for device detection utilities."""

from unittest.mock import Mock

import pytest
from fastapi import Request

from src.utils.device import DeviceDetector


class TestDeviceDetector:
    """Test device detection functionality."""

    def test_detect_mobile_from_client_hints(self) -> None:
        """Test mobile detection using Client Hints."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"viewport-width": "375", "dpr": "2.0"}

        device = DeviceDetector.detect_device(mock_request)
        assert device == "retina"

    def test_detect_mobile_from_user_agent(self) -> None:
        """Test mobile detection from User-Agent."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"
        }

        device = DeviceDetector.detect_device(mock_request)
        assert device == "mobile"

    def test_default_to_desktop(self) -> None:
        """Test default detection when no hints available."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"user-agent": "Unknown"}

        device = DeviceDetector.detect_device(mock_request)
        assert device == "desktop"

    def test_detect_pixel_ratio(self) -> None:
        """Test pixel ratio detection."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"dpr": "2.0"}

        ratio = DeviceDetector.detect_pixel_ratio(mock_request)
        assert ratio == 2.0

    def test_detect_network_quality_save_data(self) -> None:
        """Test network quality detection with Save-Data."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"save-data": "on"}

        quality = DeviceDetector.detect_network_quality(mock_request)
        assert quality == "low"

    def test_get_viewport_width(self) -> None:
        """Test viewport width extraction."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"viewport-width": "1024"}

        width = DeviceDetector.get_viewport_width(mock_request)
        assert width == 1024

    def test_get_client_hints(self) -> None:
        """Test extracting all client hints."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "viewport-width": "1920",
            "dpr": "2.0",
            "save-data": "on",
        }

        hints = DeviceDetector.get_client_hints(mock_request)

        assert hints["device"] == "retina"
        assert hints["pixel_ratio"] == 2.0
        assert hints["viewport_width"] == 1920
        assert hints["save_data"] is True
