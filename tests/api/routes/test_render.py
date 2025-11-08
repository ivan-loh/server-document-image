"""Tests for render API endpoint."""

import asyncio
import base64

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from src.api.routes.render import (
    router,
    get_cache_service,
    get_document_service,
    get_image_optimizer,
)
from src.core.cache import CacheService
from src.core.document import (
    DocumentService,
    DocumentFetchError,
    DocumentConversionError,
)
from src.core.optimizer import ImageOptimizer


class TestRenderEndpoint:
    """Test render API endpoint."""

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

    def test_health_endpoint(self, client: TestClient, app: FastAPI) -> None:
        """Test health check endpoint."""

        def mock_cache():
            service = MagicMock()
            service.l1_cache.current_size = 0
            return service

        app.dependency_overrides[get_cache_service] = mock_cache

        try:
            response = client.get("/api/v1/health")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_render_with_invalid_page_number(self, client: TestClient) -> None:
        """Test render endpoint with page number < 1."""
        response = client.get(
            "/api/v1/render",
            params={
                "s3_url": "https://s3.amazonaws.com/bucket/file.pdf",
                "page": 0,
            },
        )
        assert response.status_code == 422

    def test_render_document_fetch_error(self, client: TestClient, app: FastAPI) -> None:
        """Test render endpoint when document fetch fails."""

        def mock_doc_service():
            service = MagicMock()
            service.fetch_from_s3 = AsyncMock(
                side_effect=DocumentFetchError("Document not found")
            )
            return service

        def mock_cache():
            service = MagicMock()
            service.generate_cache_key = MagicMock(return_value="test_key")
            service.get = AsyncMock(return_value=None)
            return service

        def mock_optimizer():
            return ImageOptimizer()

        app.dependency_overrides[get_document_service] = mock_doc_service
        app.dependency_overrides[get_cache_service] = mock_cache
        app.dependency_overrides[get_image_optimizer] = mock_optimizer

        try:
            response = client.get(
                "/api/v1/render",
                params={
                    "s3_url": "https://s3.amazonaws.com/bucket/missing.pdf",
                    "page": 1,
                },
            )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_render_document_conversion_error(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """Test render endpoint when document conversion fails."""

        def mock_doc_service():
            service = MagicMock()
            service.fetch_from_s3 = AsyncMock(return_value=b"pdf content")
            service.convert_page_to_image = AsyncMock(
                side_effect=DocumentConversionError("Page 99 does not exist")
            )
            return service

        def mock_cache():
            service = MagicMock()
            service.generate_cache_key = MagicMock(return_value="test_key")
            service.get = AsyncMock(return_value=None)
            return service

        def mock_optimizer():
            return ImageOptimizer()

        app.dependency_overrides[get_document_service] = mock_doc_service
        app.dependency_overrides[get_cache_service] = mock_cache
        app.dependency_overrides[get_image_optimizer] = mock_optimizer

        try:
            response = client.get(
                "/api/v1/render",
                params={
                    "s3_url": "https://s3.amazonaws.com/bucket/file.pdf",
                    "page": 99,
                },
            )

            assert response.status_code == 400
            assert "does not exist" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_render_unexpected_error(self, client: TestClient, app: FastAPI) -> None:
        """Test render endpoint handles unexpected errors."""

        def mock_doc_service():
            service = MagicMock()
            service.fetch_from_s3 = AsyncMock(side_effect=Exception("Unexpected error"))
            return service

        def mock_cache():
            service = MagicMock()
            service.generate_cache_key = MagicMock(return_value="test_key")
            service.get = AsyncMock(return_value=None)
            return service

        def mock_optimizer():
            return ImageOptimizer()

        app.dependency_overrides[get_document_service] = mock_doc_service
        app.dependency_overrides[get_cache_service] = mock_cache
        app.dependency_overrides[get_image_optimizer] = mock_optimizer

        try:
            response = client.get(
                "/api/v1/render",
                params={
                    "s3_url": "https://s3.amazonaws.com/bucket/file.pdf",
                    "page": 1,
                },
            )

            assert response.status_code == 500
            assert "internal server error" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_render_output_base64(self, client: TestClient, app: FastAPI) -> None:
        """Test render endpoint with base64 output format."""

        def mock_cache():
            service = MagicMock()
            service.generate_cache_key = MagicMock(return_value="test_key")
            service.get = AsyncMock(
                return_value={
                    "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                    "format": "png",
                    "mime_type": "image/png",
                    "width": 1,
                    "height": 1,
                    "size_bytes": 100,
                    "compression_ratio": 0.1,
                    "cache_hit": False,
                    "processing_ms": 50,
                    "optimizations": ["compressed"],
                    "original_size_bytes": 1000,
                }
            )
            return service

        def mock_doc_service():
            return DocumentService()

        def mock_optimizer():
            return ImageOptimizer()

        app.dependency_overrides[get_cache_service] = mock_cache
        app.dependency_overrides[get_document_service] = mock_doc_service
        app.dependency_overrides[get_image_optimizer] = mock_optimizer

        try:
            response = client.get(
                "/api/v1/render",
                params={
                    "s3_url": "https://s3.amazonaws.com/bucket/file.pdf",
                    "page": 1,
                    "output": "base64",
                },
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/plain; charset=utf-8"
            assert response.text.startswith("data:image/png;base64,")
        finally:
            app.dependency_overrides.clear()

    def test_render_output_json(self, client: TestClient, app: FastAPI) -> None:
        """Test render endpoint with JSON output format."""

        def mock_cache():
            service = MagicMock()
            service.generate_cache_key = MagicMock(return_value="test_key")
            service.get = AsyncMock(
                return_value={
                    "data": "base64data",
                    "format": "webp",
                    "mime_type": "image/webp",
                    "width": 1920,
                    "height": 1080,
                    "size_bytes": 150000,
                    "compression_ratio": 0.15,
                    "cache_hit": True,
                    "processing_ms": 450,
                    "optimizations": ["resized", "compressed"],
                    "original_size_bytes": 1000000,
                }
            )
            return service

        def mock_doc_service():
            return DocumentService()

        def mock_optimizer():
            return ImageOptimizer()

        app.dependency_overrides[get_cache_service] = mock_cache
        app.dependency_overrides[get_document_service] = mock_doc_service
        app.dependency_overrides[get_image_optimizer] = mock_optimizer

        try:
            response = client.get(
                "/api/v1/render",
                params={
                    "s3_url": "https://s3.amazonaws.com/bucket/file.pdf",
                    "page": 1,
                    "output": "json",
                },
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"
            data = response.json()
            assert data["format"] == "webp"
            assert data["width"] == 1920
            assert data["cache_hit"] is True
            assert "optimizations" in data
        finally:
            app.dependency_overrides.clear()

    def test_render_output_binary(self, client: TestClient, app: FastAPI) -> None:
        """Test render endpoint with binary output format."""
        test_binary = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        test_base64 = base64.b64encode(test_binary).decode()

        def mock_cache():
            service = MagicMock()
            service.generate_cache_key = MagicMock(return_value="test_key")
            service.get = AsyncMock(
                return_value={
                    "data": test_base64,
                    "format": "png",
                    "mime_type": "image/png",
                    "width": 100,
                    "height": 100,
                    "size_bytes": len(test_binary),
                    "compression_ratio": 0.5,
                    "cache_hit": True,
                    "processing_ms": 50,
                    "optimizations": ["compressed"],
                    "original_size_bytes": len(test_binary) * 2,
                }
            )
            return service

        def mock_doc_service():
            return DocumentService()

        def mock_optimizer():
            return ImageOptimizer()

        app.dependency_overrides[get_cache_service] = mock_cache
        app.dependency_overrides[get_document_service] = mock_doc_service
        app.dependency_overrides[get_image_optimizer] = mock_optimizer

        try:
            response = client.get(
                "/api/v1/render",
                params={
                    "s3_url": "https://s3.amazonaws.com/bucket/file.pdf",
                    "page": 1,
                    "output": "binary",
                },
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "image/png"
            assert response.content == test_binary
            assert "content-length" in response.headers
            assert "cache-control" in response.headers
        finally:
            app.dependency_overrides.clear()
