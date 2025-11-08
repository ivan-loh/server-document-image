"""End-to-end integration tests for render API endpoint."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from src.api.routes.render import (
    router,
    get_cache_service,
    get_document_service,
    get_image_optimizer,
)

class TestRenderEndToEnd:
    """End-to-end integration tests for complete render flow."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create test FastAPI app."""
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def sample_image(self) -> Image.Image:
        """Create a sample test image."""
        return Image.new("RGB", (1920, 1080), color=(255, 255, 255))

    def test_full_render_flow_cache_hit(self, client: TestClient, app: FastAPI) -> None:
        """Test complete render flow with cache hit."""
        cached_data = {
            "data": "base64encodeddata",
            "format": "webp",
            "mime_type": "image/webp",
            "width": 1920,
            "height": 1080,
            "size_bytes": 150000,
            "compression_ratio": 0.15,
            "cache_hit": False,
            "processing_ms": 450,
            "optimizations": ["resized", "compressed"],
            "original_size_bytes": 1000000,
        }

        def mock_cache():
            service = MagicMock()
            service.generate_cache_key = MagicMock(return_value="test_key")
            service.get = AsyncMock(return_value=cached_data)
            return service

        def mock_doc_service():
            service = MagicMock()
            return service

        app.dependency_overrides[get_cache_service] = mock_cache
        app.dependency_overrides[get_document_service] = mock_doc_service

        try:
            response = client.get(
                "/api/v1/render",
                params={
                    "s3_url": "https://s3.amazonaws.com/test-bucket/document.pdf",
                    "page": 1,
                    "output": "json",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["cache_hit"] is True
        finally:
            app.dependency_overrides.clear()

    def test_render_flow_different_devices(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """Test render flow with different device profiles."""
        cached_data = {
            "data": "base64encodeddata",
            "format": "webp",
            "mime_type": "image/webp",
            "width": 640,
            "height": 480,
            "size_bytes": 50000,
            "compression_ratio": 0.1,
            "cache_hit": False,
            "processing_ms": 200,
            "optimizations": ["resized", "compressed"],
            "original_size_bytes": 500000,
        }

        call_count = {"count": 0}

        def mock_cache():
            service = MagicMock()

            def generate_key(**kwargs):
                call_count["count"] += 1
                return f"test_key_{kwargs['device']}"

            service.generate_cache_key = generate_key
            service.get = AsyncMock(return_value=cached_data)
            return service

        def mock_doc_service():
            return MagicMock()

        app.dependency_overrides[get_cache_service] = mock_cache
        app.dependency_overrides[get_document_service] = mock_doc_service

        try:
            for device in ["mobile", "tablet", "desktop"]:
                response = client.get(
                    "/api/v1/render",
                    params={
                        "s3_url": "https://s3.amazonaws.com/bucket/doc.pdf",
                        "page": 1,
                        "device": device,
                        "output": "json",
                    },
                )

                assert response.status_code == 200

            assert call_count["count"] == 3
        finally:
            app.dependency_overrides.clear()

    def test_cache_key_differs_by_parameters(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """Test that different parameters generate different cache keys."""
        cached_data = {
            "data": "base64data",
            "format": "webp",
            "mime_type": "image/webp",
            "width": 1920,
            "height": 1080,
            "size_bytes": 150000,
            "compression_ratio": 0.15,
            "cache_hit": False,
            "processing_ms": 450,
            "optimizations": ["resized", "compressed"],
            "original_size_bytes": 1000000,
        }

        generated_keys = []

        def mock_cache():
            service = MagicMock()

            def capture_key(**kwargs):
                key = f"key_{len(generated_keys)}"
                generated_keys.append((key, kwargs.copy()))
                return key

            service.generate_cache_key = capture_key
            service.get = AsyncMock(return_value=cached_data)
            return service

        def mock_doc_service():
            return MagicMock()

        app.dependency_overrides[get_cache_service] = mock_cache
        app.dependency_overrides[get_document_service] = mock_doc_service

        try:
            client.get(
                "/api/v1/render",
                params={
                    "s3_url": "https://s3.amazonaws.com/bucket/doc.pdf",
                    "page": 1,
                    "device": "mobile",
                    "output": "json",
                },
            )

            client.get(
                "/api/v1/render",
                params={
                    "s3_url": "https://s3.amazonaws.com/bucket/doc.pdf",
                    "page": 1,
                    "device": "desktop",
                    "output": "json",
                },
            )

            assert len(generated_keys) >= 2
            assert generated_keys[0][1]["device"] != generated_keys[1][1]["device"]
        finally:
            app.dependency_overrides.clear()
