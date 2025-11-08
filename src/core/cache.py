"""In-memory caching system for rendered documents."""

import hashlib
import json
import logging
from collections import OrderedDict
from typing import Optional

from src.api.config import CACHE_L1_SIZE_MB

logger = logging.getLogger(__name__)


class LRUCache:
    """In-memory LRU cache with size limit."""

    def __init__(self, max_size_mb: int = CACHE_L1_SIZE_MB):
        """Initialize LRU cache with size limit in megabytes."""
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.current_size = 0
        self.cache: OrderedDict[str, tuple[str, int]] = OrderedDict()

    def get(self, key: str) -> Optional[str]:
        """Get value from cache, moving to end (most recently used)."""
        if key in self.cache:
            value, size = self.cache.pop(key)
            self.cache[key] = (value, size)
            logger.debug(f"L1 cache hit: {key}")
            return value
        logger.debug(f"L1 cache miss: {key}")
        return None

    def set(self, key: str, value: str) -> None:
        """Set value in cache, evicting LRU items if needed."""
        value_size = len(value.encode("utf-8"))

        if key in self.cache:
            _, old_size = self.cache.pop(key)
            self.current_size -= old_size

        while self.current_size + value_size > self.max_size_bytes and self.cache:
            evicted_key, (_, evicted_size) = self.cache.popitem(last=False)
            self.current_size -= evicted_size
            logger.debug(f"L1 cache evicted: {evicted_key} ({evicted_size} bytes)")

        if value_size <= self.max_size_bytes:
            self.cache[key] = (value, value_size)
            self.current_size += value_size
            logger.debug(
                f"L1 cache set: {key} ({value_size} bytes, "
                f"total: {self.current_size / (1024 * 1024):.2f}MB)"
            )
        else:
            logger.warning(
                f"Value too large for L1 cache: {value_size / (1024 * 1024):.2f}MB"
            )

    def clear(self) -> None:
        """Clear all items from cache."""
        self.cache.clear()
        self.current_size = 0
        logger.info("L1 cache cleared")


class CacheService:
    """In-memory caching service using LRU cache."""

    def __init__(self) -> None:
        """Initialize cache service with L1 LRU cache."""
        self.l1_cache = LRUCache()

    async def get(self, key: str) -> Optional[dict[str, object]]:
        """
        Get cached value from L1 memory cache.

        Args:
            key: Cache key

        Returns:
            Cached data as dict, or None if not found
        """
        l1_value = self.l1_cache.get(key)
        if l1_value:
            result: dict[str, object] = json.loads(l1_value)
            return result

        logger.debug(f"Cache miss: {key}")
        return None

    async def set(self, key: str, value: dict[str, object]) -> None:
        """
        Set value in L1 cache.

        Args:
            key: Cache key
            value: Data to cache (will be JSON serialized)
        """
        json_value = json.dumps(value)
        self.l1_cache.set(key, json_value)

    def generate_cache_key(
        self,
        s3_url: str,
        page: int,
        device: str,
        quality: str,
        max_width: Optional[int],
        pixel_ratio: float,
        output_format: str,
    ) -> str:
        """
        Generate unique cache key from request parameters.

        Args:
            s3_url: S3 URL of document
            page: Page number
            device: Device profile
            quality: Quality setting
            max_width: Maximum width
            pixel_ratio: Pixel ratio
            output_format: Output format

        Returns:
            Cache key string
        """
        key_parts = [
            s3_url,
            str(page),
            device,
            quality,
            str(max_width) if max_width else "auto",
            f"{pixel_ratio:.1f}",
            output_format,
        ]
        key_string = "|".join(key_parts)

        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]

        return f"render:{key_hash}"

    async def clear_all(self) -> None:
        """Clear L1 cache."""
        self.l1_cache.clear()
