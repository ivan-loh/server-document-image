"""Device and network detection utilities."""

import logging
import re
from typing import Optional

from fastapi import Request

logger = logging.getLogger(__name__)


class DeviceDetector:
    """Detect device type and capabilities from request headers."""

    @staticmethod
    def detect_device(request: Request) -> str:
        """
        Detect device type from request headers.

        Priority:
        1. Client Hints (Viewport-Width, DPR)
        2. User-Agent parsing

        Args:
            request: FastAPI request object

        Returns:
            Device type: 'mobile', 'tablet', 'desktop', or 'retina'
        """
        viewport_width = request.headers.get("viewport-width")
        dpr = request.headers.get("dpr")

        if viewport_width:
            try:
                width = int(viewport_width)
                pixel_ratio = float(dpr) if dpr else 1.0

                if pixel_ratio > 1.5:
                    return "retina"
                elif width < 768:
                    return "mobile"
                elif width < 1024:
                    return "tablet"
                else:
                    return "desktop"
            except ValueError:
                pass

        user_agent = request.headers.get("user-agent", "").lower()
        return DeviceDetector._detect_from_user_agent(user_agent)

    @staticmethod
    def _detect_from_user_agent(user_agent: str) -> str:
        """Detect device from User-Agent string."""
        mobile_patterns = [
            r"iphone",
            r"ipod",
            r"android.*mobile",
            r"windows phone",
            r"blackberry",
        ]

        tablet_patterns = [
            r"ipad",
            r"android(?!.*mobile)",
            r"tablet",
            r"kindle",
            r"playbook",
        ]

        for pattern in mobile_patterns:
            if re.search(pattern, user_agent):
                logger.debug(f"Detected mobile device from UA: {pattern}")
                return "mobile"

        for pattern in tablet_patterns:
            if re.search(pattern, user_agent):
                logger.debug(f"Detected tablet device from UA: {pattern}")
                return "tablet"

        logger.debug("Detected desktop device (default)")
        return "desktop"

    @staticmethod
    def detect_pixel_ratio(request: Request) -> float:
        """
        Detect device pixel ratio from headers.

        Args:
            request: FastAPI request object

        Returns:
            Pixel ratio (1.0, 1.5, 2.0, or 3.0)
        """
        dpr = request.headers.get("dpr")
        if dpr:
            try:
                ratio = float(dpr)
                if ratio >= 2.5:
                    return 3.0
                elif ratio >= 1.75:
                    return 2.0
                elif ratio >= 1.25:
                    return 1.5
                else:
                    return 1.0
            except ValueError:
                pass

        return 1.0

    @staticmethod
    def detect_network_quality(request: Request) -> Optional[str]:
        """
        Detect network quality from Save-Data and ECT headers.

        Args:
            request: FastAPI request object

        Returns:
            Network quality: 'low', 'medium', 'high', or None
        """
        save_data = request.headers.get("save-data")
        if save_data and save_data.lower() == "on":
            logger.debug("Save-Data mode detected")
            return "low"

        ect = request.headers.get("ect")
        if ect:
            ect_lower = ect.lower()
            if ect_lower in ["slow-2g", "2g"]:
                return "low"
            elif ect_lower == "3g":
                return "medium"
            elif ect_lower == "4g":
                return "high"

        return None

    @staticmethod
    def get_viewport_width(request: Request) -> Optional[int]:
        """
        Get viewport width from Client Hints.

        Args:
            request: FastAPI request object

        Returns:
            Viewport width in pixels, or None
        """
        viewport_width = request.headers.get("viewport-width")
        if viewport_width:
            try:
                return int(viewport_width)
            except ValueError:
                pass
        return None

    @staticmethod
    def get_client_hints(request: Request) -> dict[str, object]:
        """
        Extract all relevant client hints from request.

        Args:
            request: FastAPI request object

        Returns:
            Dictionary of client hints
        """
        return {
            "device": DeviceDetector.detect_device(request),
            "pixel_ratio": DeviceDetector.detect_pixel_ratio(request),
            "viewport_width": DeviceDetector.get_viewport_width(request),
            "network_quality": DeviceDetector.detect_network_quality(request),
            "save_data": request.headers.get("save-data", "").lower() == "on",
        }
