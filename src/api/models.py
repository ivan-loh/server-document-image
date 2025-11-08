"""API request and response models."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


class RenderRequest(BaseModel):
    """Request parameters for document page rendering."""

    s3_url: HttpUrl = Field(..., description="S3 URL of the document to render")
    page: int = Field(..., ge=1, description="Page number to render (1-indexed)")
    output: Literal["base64", "json", "binary"] = Field(
        default="base64",
        description="Response format: base64 string, JSON with metadata, or binary image",
    )
    device: Optional[Literal["desktop", "tablet", "mobile", "auto"]] = Field(
        default="auto", description="Target device profile for optimization"
    )
    quality: Optional[str] = Field(
        default="auto",
        description="Image quality: 'auto', 'low', 'medium', 'high', or 1-100",
    )
    max_width: Optional[int] = Field(
        default=None, ge=100, le=3840, description="Maximum width in CSS pixels"
    )
    pixel_ratio: Optional[float] = Field(
        default=1.0, ge=1.0, le=3.0, description="Device pixel ratio"
    )
    format: Optional[Literal["auto", "webp", "avif", "jpeg", "png"]] = Field(
        default="auto", description="Output image format"
    )


class RenderResponse(BaseModel):
    """Response containing rendered image data and metadata."""

    data: str = Field(..., description="Base64-encoded image data")
    format: str = Field(..., description="Image format (webp, jpeg, png)")
    mime_type: str = Field(..., description="MIME type of the image")
    width: int = Field(..., description="Image width in pixels")
    height: int = Field(..., description="Image height in pixels")
    size_bytes: int = Field(..., description="Size of the encoded image in bytes")
    compression_ratio: float = Field(
        ..., description="Compression ratio (output size / original size)"
    )
    cache_hit: bool = Field(..., description="Whether this response was served from cache")
    processing_ms: int = Field(..., description="Processing time in milliseconds")
    optimizations: list[str] = Field(
        ..., description="List of optimizations applied (resized, webp, compressed, etc.)"
    )
    original_size_bytes: int = Field(..., description="Original uncompressed image size")
