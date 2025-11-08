"""Tests for document service."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.document import DocumentConversionError, DocumentFetchError, DocumentService


class TestDocumentService:
    """Test document fetching and conversion."""

    def test_parse_s3_url_valid(self) -> None:
        """Test parsing valid S3 URLs."""
        service = DocumentService()
        bucket, key = service._parse_s3_url("s3://my-bucket/path/to/file.pdf")

        assert bucket == "my-bucket"
        assert key == "path/to/file.pdf"

    def test_parse_s3_url_invalid_scheme(self) -> None:
        """Test parsing URL with invalid scheme."""
        service = DocumentService()

        with pytest.raises(DocumentFetchError, match="Invalid S3 URL scheme"):
            service._parse_s3_url("http://bucket/file.pdf")

    def test_bucket_whitelist_validation(self) -> None:
        """Test bucket whitelist enforcement."""
        service = DocumentService(allowed_buckets=["allowed-bucket"])

        with pytest.raises(DocumentFetchError, match="not in the allowed list"):
            service._parse_s3_url("s3://forbidden-bucket/file.pdf")

    def test_empty_whitelist_allows_all(self) -> None:
        """Test that empty whitelist allows all buckets."""
        service = DocumentService(allowed_buckets=[])
        bucket, key = service._parse_s3_url("s3://any-bucket/file.pdf")

        assert bucket == "any-bucket"

    @pytest.mark.asyncio
    async def test_fetch_from_s3_success(self) -> None:
        """Test successful S3 file download."""
        service = DocumentService()

        mock_content = b"PDF file content here"

        with patch.object(service.session, "client") as mock_client:
            mock_s3 = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_s3

            mock_s3.head_object.return_value = {"ContentLength": len(mock_content)}

            mock_body = AsyncMock()
            mock_body.read.return_value = mock_content
            mock_s3.get_object.return_value = {"Body": mock_body}

            result = await service.fetch_from_s3("s3://test-bucket/doc.pdf")

            assert result == mock_content
            mock_s3.head_object.assert_called_once_with(
                Bucket="test-bucket", Key="doc.pdf"
            )
            mock_s3.get_object.assert_called_once_with(Bucket="test-bucket", Key="doc.pdf")

    @pytest.mark.asyncio
    async def test_fetch_from_s3_file_too_large(self) -> None:
        """Test S3 fetch fails when file exceeds size limit."""
        service = DocumentService()

        class NoSuchKeyError(Exception):
            pass

        with patch.object(service.session, "client") as mock_client:
            mock_s3 = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_s3

            mock_exceptions = MagicMock()
            mock_exceptions.NoSuchKey = NoSuchKeyError
            mock_s3.exceptions = mock_exceptions

            mock_s3.head_object.return_value = {"ContentLength": 200 * 1024 * 1024}

            with pytest.raises(DocumentFetchError, match="File too large"):
                await service.fetch_from_s3("s3://test-bucket/huge.pdf")

            mock_s3.get_object.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_from_s3_not_found(self) -> None:
        """Test S3 fetch fails when file not found."""
        service = DocumentService()

        class NoSuchKeyError(Exception):
            pass

        with patch.object(service.session, "client") as mock_client:
            mock_s3 = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_s3

            mock_exceptions = MagicMock()
            mock_exceptions.NoSuchKey = NoSuchKeyError
            mock_s3.exceptions = mock_exceptions

            mock_s3.head_object.side_effect = NoSuchKeyError()

            with pytest.raises(DocumentFetchError, match="Document not found"):
                await service.fetch_from_s3("s3://test-bucket/missing.pdf")

    @pytest.mark.asyncio
    async def test_fetch_from_s3_timeout(self) -> None:
        """Test S3 fetch timeout handling."""
        service = DocumentService(timeout_seconds=1)

        with patch.object(service.session, "client") as mock_client:
            mock_s3 = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_s3

            mock_s3.head_object.return_value = {"ContentLength": 1024}

            async def slow_get(*args, **kwargs):
                await asyncio.sleep(2)
                return {"Body": AsyncMock()}

            mock_s3.get_object.side_effect = slow_get

            with pytest.raises(DocumentFetchError, match="Timeout"):
                await service.fetch_from_s3("s3://test-bucket/doc.pdf")

    @pytest.mark.asyncio
    async def test_convert_page_to_image_success(self) -> None:
        """Test successful PDF page conversion."""
        service = DocumentService()
        pdf_bytes = b"%PDF-1.4 fake pdf content"

        mock_image = MagicMock()
        mock_image.size = (1920, 1080)

        with patch("src.core.document.convert_from_bytes") as mock_convert:
            mock_convert.return_value = [mock_image]

            result = await service.convert_page_to_image(pdf_bytes, page=1, dpi=150)

            assert result == mock_image
            mock_convert.assert_called_once()
            call_args = mock_convert.call_args
            assert call_args[1]["dpi"] == 150
            assert call_args[1]["first_page"] == 1
            assert call_args[1]["last_page"] == 1

    @pytest.mark.asyncio
    async def test_convert_page_to_image_page_not_found(self) -> None:
        """Test conversion fails when page doesn't exist."""
        service = DocumentService()
        pdf_bytes = b"%PDF-1.4 fake pdf content"

        with patch("src.core.document.convert_from_bytes") as mock_convert:
            mock_convert.return_value = []

            with pytest.raises(DocumentConversionError, match="Page 5 not found"):
                await service.convert_page_to_image(pdf_bytes, page=5, dpi=150)
