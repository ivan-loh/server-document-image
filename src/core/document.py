"""Document fetching and conversion functionality."""

import asyncio
import logging
import tempfile
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Optional
from urllib.parse import urlparse

import aioboto3
from pdf2image import convert_from_bytes
from PIL import Image

from src.api.config import DEFAULT_DPI, MAX_INPUT_SIZE_MB

logger = logging.getLogger(__name__)


class DocumentFetchError(Exception):
    """Raised when document fetching fails."""

    pass


class DocumentConversionError(Exception):
    """Raised when document conversion fails."""

    pass


class DocumentService:
    """Service for fetching and converting documents."""

    def __init__(
        self,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_region: str = "us-east-1",
        timeout_seconds: int = 30,
        allowed_buckets: Optional[list[str]] = None,
        endpoint_url: Optional[str] = None,
    ):
        """Initialize document service with AWS credentials."""
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_region = aws_region
        self.timeout_seconds = timeout_seconds
        self.allowed_buckets = allowed_buckets or []
        self.endpoint_url = endpoint_url
        self.session = aioboto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region,
        )

    async def fetch_from_s3(self, s3_url: str) -> bytes:
        """
        Fetch document from S3 with streaming and size validation.

        Args:
            s3_url: S3 URL in format s3://bucket/key

        Returns:
            Document content as bytes

        Raises:
            DocumentFetchError: If fetching fails or file is too large
        """
        try:
            bucket, key = self._parse_s3_url(s3_url)
            logger.info(f"Fetching document from S3: bucket={bucket}, key={key}")

            client_config = {"region_name": self.aws_region}
            if self.endpoint_url:
                client_config["endpoint_url"] = self.endpoint_url

            async with self.session.client("s3", **client_config) as s3_client:
                try:
                    response = await s3_client.head_object(Bucket=bucket, Key=key)
                    content_length = response.get("ContentLength", 0)

                    if content_length > MAX_INPUT_SIZE_MB * 1024 * 1024:
                        raise DocumentFetchError(
                            f"File too large: {content_length / (1024 * 1024):.2f}MB "
                            f"(max: {MAX_INPUT_SIZE_MB}MB)"
                        )

                    logger.info(f"Document size: {content_length / (1024 * 1024):.2f}MB")

                except s3_client.exceptions.NoSuchKey:
                    raise DocumentFetchError(f"Document not found: {s3_url}")

                try:
                    response = await asyncio.wait_for(
                        s3_client.get_object(Bucket=bucket, Key=key),
                        timeout=self.timeout_seconds,
                    )

                    body = response["Body"]
                    content: bytes = await body.read()

                    logger.info(
                        f"Successfully fetched document: {len(content) / (1024 * 1024):.2f}MB"
                    )
                    return content

                except asyncio.TimeoutError:
                    raise DocumentFetchError(
                        f"Timeout fetching document after {self.timeout_seconds}s"
                    )

        except DocumentFetchError:
            raise
        except Exception as e:
            logger.error(f"Error fetching document from S3: {e}")
            raise DocumentFetchError(f"Failed to fetch document: {str(e)}")

    async def convert_page_to_image(
        self, document_bytes: bytes, page: int, dpi: int = DEFAULT_DPI
    ) -> Image.Image:
        """
        Convert specific page of document to PIL Image.

        Args:
            document_bytes: Document content as bytes
            page: Page number (1-indexed)
            dpi: DPI for rendering

        Returns:
            PIL Image object

        Raises:
            DocumentConversionError: If conversion fails
        """
        try:
            logger.info(f"Converting page {page} at {dpi} DPI")

            # Run pdf2image in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            images = await loop.run_in_executor(
                None,
                lambda: convert_from_bytes(
                    document_bytes,
                    dpi=dpi,
                    first_page=page,
                    last_page=page,
                    fmt="png",
                ),
            )

            if not images:
                raise DocumentConversionError(f"Page {page} not found in document")

            image = images[0]
            logger.info(f"Converted page {page}: {image.size[0]}x{image.size[1]} pixels")

            return image

        except IndexError:
            raise DocumentConversionError(f"Page {page} does not exist in document")
        except Exception as e:
            logger.error(f"Error converting document page: {e}")
            raise DocumentConversionError(f"Failed to convert page {page}: {str(e)}")

    def _parse_s3_url(self, s3_url: str) -> tuple[str, str]:
        """
        Parse S3 URL into bucket and key.

        Args:
            s3_url: S3 URL in format s3://bucket/key

        Returns:
            Tuple of (bucket, key)

        Raises:
            DocumentFetchError: If URL is invalid or bucket not allowed
        """
        try:
            parsed = urlparse(s3_url)
            if parsed.scheme != "s3":
                raise DocumentFetchError(f"Invalid S3 URL scheme: {parsed.scheme}")

            bucket = parsed.netloc
            key = parsed.path.lstrip("/")

            if not bucket or not key:
                raise DocumentFetchError(f"Invalid S3 URL format: {s3_url}")

            # Validate bucket is in allowed list (if whitelist is configured)
            if self.allowed_buckets and bucket not in self.allowed_buckets:
                raise DocumentFetchError(
                    f"Access denied: bucket '{bucket}' is not in the allowed list"
                )

            return bucket, key

        except DocumentFetchError:
            raise
        except Exception as e:
            raise DocumentFetchError(f"Failed to parse S3 URL: {str(e)}")
