"""Image optimization with device-aware compression."""

import logging
from base64 import b64encode
from dataclasses import dataclass
from io import BytesIO
from typing import Dict, Optional, Tuple

import numpy as np
from PIL import Image

from src.api.config import (
    DEVICE_PROFILES,
    MAX_OUTPUT_SIZE_MB,
    QUALITY_PRESETS,
    DeviceProfile,
)

logger = logging.getLogger(__name__)


@dataclass
class OptimizationMetadata:
    """Metadata about applied optimizations."""

    format: str
    quality: int
    original_size: int
    optimized_size: int
    width: int
    height: int
    optimizations: list[str]
    processing_time_ms: int
    pdf_size_bytes: Optional[int] = None  # Actual PDF size for true compression ratio


class ImageOptimizer:
    """Intelligent image optimization based on device and content."""

    def __init__(self) -> None:
        """Initialize the image optimizer."""
        self.device_profiles = DEVICE_PROFILES

    def optimize_for_web(
        self,
        image: Image.Image,
        device: str = "auto",
        quality: Optional[str] = "auto",
        max_width: Optional[int] = None,
        pixel_ratio: float = 1.0,
        output_format: Optional[str] = "auto",
        pdf_size_bytes: Optional[int] = None,
    ) -> Tuple[bytes, OptimizationMetadata]:
        """
        Optimize image for web delivery with device-aware settings.

        Args:
            image: PIL Image to optimize
            device: Target device profile (mobile, tablet, desktop, retina, auto)
            quality: Quality setting (auto, low, medium, high, or 1-100)
            max_width: Maximum width in CSS pixels
            pixel_ratio: Device pixel ratio
            output_format: Output format (auto, webp, jpeg, png, avif)
            pdf_size_bytes: Original PDF size in bytes (for compression ratio)

        Returns:
            Tuple of (optimized image bytes, metadata)
        """
        import time

        start_time = time.time()
        optimizations: list[str] = []
        original_size = image.width * image.height * (4 if image.mode == "RGBA" else 3)

        profile = self._get_device_profile(device)
        logger.info(f"Using device profile: {device} ({profile.max_width}x{profile.max_height})")

        image, resized = self._resize_for_device(image, profile, max_width, pixel_ratio)
        if resized:
            optimizations.append("resized")

        selected_format = self._select_format(image, output_format, profile)
        optimizations.append(selected_format.lower())

        quality_value = self._calculate_quality(image, quality, profile)

        image_bytes = self._compress_image(image, selected_format, quality_value, profile)

        output_size_mb = len(image_bytes) / (1024 * 1024)
        if output_size_mb > MAX_OUTPUT_SIZE_MB:
            logger.warning(
                f"Output size {output_size_mb:.2f}MB exceeds limit, "
                f"applying aggressive compression"
            )
            # Retry with lower quality
            quality_value = int(quality_value * 0.7)
            image_bytes = self._compress_image(image, selected_format, quality_value, profile)
            optimizations.append("aggressive_compression")

        if len(image_bytes) < original_size:
            optimizations.append("compressed")

        processing_time_ms = int((time.time() - start_time) * 1000)

        metadata = OptimizationMetadata(
            format=selected_format.lower(),
            quality=quality_value,
            original_size=original_size,
            optimized_size=len(image_bytes),
            width=image.width,
            height=image.height,
            optimizations=optimizations,
            processing_time_ms=processing_time_ms,
            pdf_size_bytes=pdf_size_bytes,
        )

        logger.info(
            f"Optimized image: {metadata.width}x{metadata.height}, "
            f"{len(image_bytes) / 1024:.1f}KB, "
            f"compression: {(1 - len(image_bytes) / original_size) * 100:.1f}%, "
            f"time: {processing_time_ms}ms"
        )

        return image_bytes, metadata

    def encode_base64(self, image_bytes: bytes, mime_type: str) -> str:
        """
        Encode image bytes to base64 with optional data URI prefix.

        Args:
            image_bytes: Image data as bytes
            mime_type: MIME type (e.g., 'image/webp')

        Returns:
            Base64-encoded string with data URI prefix
        """
        base64_data = b64encode(image_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{base64_data}"

    def _get_device_profile(self, device: str) -> DeviceProfile:
        """Get device profile, using desktop as fallback."""
        if device == "auto":
            device = "desktop"
        return self.device_profiles.get(device, self.device_profiles["desktop"])

    def _resize_for_device(
        self,
        image: Image.Image,
        profile: DeviceProfile,
        max_width: Optional[int],
        pixel_ratio: float,
    ) -> Tuple[Image.Image, bool]:
        """Resize image based on device profile and constraints."""
        target_width = profile.max_width

        if max_width is not None:
            target_width = min(int(max_width * pixel_ratio), profile.max_width)

        if image.width > target_width:
            aspect_ratio = image.height / image.width
            new_height = int(target_width * aspect_ratio)

            # Use LANCZOS for high-quality downsampling
            resized_image = image.resize((target_width, new_height), Image.Resampling.LANCZOS)
            logger.info(
                f"Resized from {image.width}x{image.height} to "
                f"{resized_image.width}x{resized_image.height}"
            )
            return resized_image, True

        return image, False

    def _select_format(
        self, image: Image.Image, requested_format: Optional[str], profile: DeviceProfile
    ) -> str:
        """Select optimal output format based on image content and request."""
        if requested_format and requested_format != "auto":
            return requested_format.upper()

        if image.mode == "RGBA" or self._has_transparency(image):
            logger.info("Image has transparency, using PNG format")
            return "PNG"

        return profile.format.upper()

    def _calculate_quality(
        self, image: Image.Image, quality: Optional[str], profile: DeviceProfile
    ) -> int:
        """Calculate optimal quality based on content analysis."""
        if quality and quality != "auto":
            if quality in QUALITY_PRESETS:
                return QUALITY_PRESETS[quality]
            try:
                return max(1, min(100, int(quality)))
            except ValueError:
                pass

        if self._is_text_heavy(image):
            return 95
        elif self._is_photo(image):
            return 85
        else:
            return profile.quality

    def _compress_image(
        self, image: Image.Image, output_format: str, quality: int, profile: DeviceProfile
    ) -> bytes:
        """Compress image with format-specific optimizations."""
        buffer = BytesIO()

        if output_format in ["JPEG", "WEBP"] and image.mode in ["RGBA", "LA"]:
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "RGBA":
                background.paste(image, mask=image.split()[3])
            else:
                background.paste(image)
            image = background

        save_kwargs: Dict[str, object] = {"quality": quality, "optimize": True}

        if output_format == "WEBP":
            save_kwargs["method"] = 6  # Best compression
            save_kwargs["lossless"] = False
        elif output_format == "JPEG":
            save_kwargs["progressive"] = True
            save_kwargs["subsampling"] = 0
        elif output_format == "PNG":
            save_kwargs["compress_level"] = 9

        image.save(buffer, format=output_format, **save_kwargs)
        return buffer.getvalue()

    def _has_transparency(self, image: Image.Image) -> bool:
        """Check if image has transparent pixels."""
        if image.mode not in ("RGBA", "LA"):
            return False

        alpha = image.split()[-1]
        extrema = alpha.getextrema()
        if isinstance(extrema, tuple) and len(extrema) == 2:
            return bool(extrema[0] < 255)  # type: ignore[operator]
        return False

    def _is_text_heavy(self, image: Image.Image) -> bool:
        """Detect if image is text-heavy using edge density heuristic."""
        gray = image.convert("L")
        arr = np.array(gray)

        edges = float(np.abs(np.diff(arr, axis=0)).sum()) + float(
            np.abs(np.diff(arr, axis=1)).sum()
        )
        edge_density = edges / (float(arr.size) * 255.0)

        return bool(edge_density > 0.3)

    def _is_photo(self, image: Image.Image) -> bool:
        """Detect if image is a photograph using color variance heuristic."""
        if image.mode in ["L", "LA"]:
            return False

        arr = np.array(image.convert("RGB").resize((100, 100)))

        color_variance = float(np.var(arr)) / (255.0 * 255.0)

        return bool(color_variance > 0.1)
