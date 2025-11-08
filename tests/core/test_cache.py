"""Tests for caching system."""

import pytest

from src.core.cache import CacheService, LRUCache

class TestLRUCache:
    """Test in-memory LRU cache."""

    def test_set_and_get(self) -> None:
        """Test basic set and get operations."""
        cache = LRUCache(max_size_mb=1)
        cache.set("key1", "value1")

        result = cache.get("key1")
        assert result == "value1"

    def test_cache_miss(self) -> None:
        """Test cache miss returns None."""
        cache = LRUCache(max_size_mb=1)
        result = cache.get("nonexistent")
        assert result is None

    def test_lru_eviction(self) -> None:
        """Test that LRU items are evicted when size limit reached."""
        cache = LRUCache(max_size_mb=0.0001)

        cache.set("key1", "a" * 50)
        cache.set("key2", "b" * 50)
        cache.set("key3", "c" * 50)

        assert cache.get("key1") is None
        assert cache.get("key3") == "c" * 50

    def test_clear(self) -> None:
        """Test cache clearing."""
        cache = LRUCache(max_size_mb=1)
        cache.set("key1", "value1")
        cache.clear()

        assert cache.get("key1") is None
        assert cache.current_size == 0

class TestCacheService:
    """Test multi-level cache service."""

    @pytest.mark.asyncio
    async def test_l1_cache_hit(self, cache_service: CacheService) -> None:
        """Test L1 cache hit."""
        test_data = {"key": "value", "number": 123}

        await cache_service.set("test_key", test_data)
        result = await cache_service.get("test_key")

        assert result == test_data

    @pytest.mark.asyncio
    async def test_cache_miss(self, cache_service: CacheService) -> None:
        """Test cache miss returns None."""
        result = await cache_service.get("nonexistent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_key_generation(self, cache_service: CacheService) -> None:
        """Test cache key generation is deterministic."""
        key1 = cache_service.generate_cache_key(
            s3_url="s3://bucket/doc.pdf",
            page=1,
            device="mobile",
            quality="auto",
            max_width=None,
            pixel_ratio=1.0,
            output_format="webp",
        )

        key2 = cache_service.generate_cache_key(
            s3_url="s3://bucket/doc.pdf",
            page=1,
            device="mobile",
            quality="auto",
            max_width=None,
            pixel_ratio=1.0,
            output_format="webp",
        )

        assert key1 == key2
        assert key1.startswith("render:")

    @pytest.mark.asyncio
    async def test_cache_key_uniqueness(self, cache_service: CacheService) -> None:
        """Test that different parameters generate different keys."""
        key1 = cache_service.generate_cache_key(
            s3_url="s3://bucket/doc.pdf",
            page=1,
            device="mobile",
            quality="auto",
            max_width=None,
            pixel_ratio=1.0,
            output_format="webp",
        )

        key2 = cache_service.generate_cache_key(
            s3_url="s3://bucket/doc.pdf",
            page=2,
            device="mobile",
            quality="auto",
            max_width=None,
            pixel_ratio=1.0,
            output_format="webp",
        )

        assert key1 != key2

    @pytest.mark.asyncio
    async def test_clear_all(self, cache_service: CacheService) -> None:
        """Test clearing all caches."""
        await cache_service.set("key1", {"data": "value1"})
        await cache_service.clear_all()

        result = await cache_service.get("key1")
        assert result is None
