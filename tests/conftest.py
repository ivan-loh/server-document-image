"""Pytest configuration and fixtures."""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
from PIL import Image

from src.core.cache import CacheService
from src.core.optimizer import ImageOptimizer


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def cache_service() -> AsyncGenerator[CacheService, None]:
    """Create cache service with L1 in-memory cache only."""
    service = CacheService()
    yield service


@pytest.fixture
def image_optimizer() -> ImageOptimizer:
    """Create image optimizer instance."""
    return ImageOptimizer()


@pytest.fixture
def sample_image() -> Image.Image:
    """Create a sample test image."""
    img = Image.new("RGB", (1920, 1080), color=(255, 255, 255))

    pixels = img.load()
    if pixels is not None:
        for i in range(img.size[0]):
            for j in range(img.size[1]):
                pixels[i, j] = (
                    int(255 * i / img.size[0]),
                    int(255 * j / img.size[1]),
                    128,
                )

    return img


@pytest.fixture
def sample_image_with_transparency() -> Image.Image:
    """Create a sample image with transparency."""
    img = Image.new("RGBA", (800, 600), color=(255, 255, 255, 128))
    return img


@pytest.fixture
def text_heavy_image() -> Image.Image:
    """Create an image simulating text-heavy content (high edge density)."""
    img = Image.new("L", (800, 600), color=255)
    pixels = img.load()

    if pixels is not None:
        for i in range(0, img.size[0], 10):
            for j in range(0, img.size[1], 10):
                if (i // 10 + j // 10) % 2 == 0:
                    for x in range(10):
                        for y in range(10):
                            if i + x < img.size[0] and j + y < img.size[1]:
                                pixels[i + x, j + y] = 0

    return img.convert("RGB")
