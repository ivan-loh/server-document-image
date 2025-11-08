"""Tests for image optimizer."""

import pytest
from PIL import Image

from src.core.optimizer import ImageOptimizer

class TestImageOptimizer:
    """Test image optimization functionality."""

    def test_optimize_for_mobile(
        self, image_optimizer: ImageOptimizer, sample_image: Image.Image
    ) -> None:
        """Test mobile device optimization."""
        image_bytes, metadata = image_optimizer.optimize_for_web(
            sample_image, device="mobile", quality="auto"
        )

        assert metadata.width <= 640  # Mobile max width
        assert metadata.format.lower() == "webp"
        assert len(image_bytes) > 0
        assert "resized" in metadata.optimizations
        assert metadata.optimized_size < metadata.original_size

    def test_optimize_for_desktop(
        self, image_optimizer: ImageOptimizer, sample_image: Image.Image
    ) -> None:
        """Test desktop device optimization."""
        image_bytes, metadata = image_optimizer.optimize_for_web(
            sample_image, device="desktop", quality="high"
        )

        assert metadata.width == 1920  # Original width preserved
        assert metadata.format.lower() == "webp"
        assert len(image_bytes) > 0
        assert metadata.quality == 95  # High quality

    def test_transparency_preserved(
        self, image_optimizer: ImageOptimizer, sample_image_with_transparency: Image.Image
    ) -> None:
        """Test that transparency causes PNG format selection."""
        image_bytes, metadata = image_optimizer.optimize_for_web(
            sample_image_with_transparency, device="desktop", output_format="auto"
        )

        assert metadata.format.lower() == "png"  # PNG for transparency
        assert len(image_bytes) > 0

    def test_custom_max_width(
        self, image_optimizer: ImageOptimizer, sample_image: Image.Image
    ) -> None:
        """Test custom max width constraint."""
        target_width = 800
        image_bytes, metadata = image_optimizer.optimize_for_web(
            sample_image, max_width=target_width, pixel_ratio=1.0
        )

        assert metadata.width == target_width
        assert "resized" in metadata.optimizations

    def test_pixel_ratio_scaling(
        self, image_optimizer: ImageOptimizer, sample_image: Image.Image
    ) -> None:
        """Test pixel ratio scaling."""
        image_bytes, metadata = image_optimizer.optimize_for_web(
            sample_image, device="mobile", pixel_ratio=2.0
        )

        assert metadata.width <= 640

    def test_text_heavy_quality_boost(
        self, image_optimizer: ImageOptimizer, text_heavy_image: Image.Image
    ) -> None:
        """Test that text-heavy images get quality."""
        image_bytes, metadata = image_optimizer.optimize_for_web(
            text_heavy_image, quality="auto"
        )

        assert 85 <= metadata.quality <= 95

    def test_base64_encoding(self, image_optimizer: ImageOptimizer) -> None:
        """Test base64 encoding with data URI."""
        test_bytes = b"test image data"
        result = image_optimizer.encode_base64(test_bytes, "image/webp")

        assert result.startswith("data:image/webp;base64,")
        assert len(result) > len("data:image/webp;base64,")

    def test_format_selection_jpeg(
        self, image_optimizer: ImageOptimizer, sample_image: Image.Image
    ) -> None:
        """Test explicit JPEG format selection."""
        image_bytes, metadata = image_optimizer.optimize_for_web(
            sample_image, output_format="jpeg"
        )

        assert metadata.format.lower() == "jpeg"
        assert "progressive" in metadata.optimizations or "compressed" in metadata.optimizations

    def test_quality_value_parsing(self, image_optimizer: ImageOptimizer) -> None:
        """Test quality value calculation."""
        assert image_optimizer._calculate_quality(None, "low", None) in range(1, 101)
        assert image_optimizer._calculate_quality(None, "high", None) in range(1, 101)

        from src.api.config import DEVICE_PROFILES

        profile = DEVICE_PROFILES["desktop"]
        quality = image_optimizer._calculate_quality(None, "85", profile)
        assert quality == 85
