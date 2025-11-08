"""Render API endpoint."""

import asyncio
import logging
import time
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import HttpUrl
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.api.config import DEFAULT_DPI, REQUEST_TIMEOUT_SECONDS, settings
from src.api.models import RenderResponse
from src.core.cache import CacheService
from src.core.document import DocumentConversionError, DocumentFetchError, DocumentService
from src.core.optimizer import ImageOptimizer
from src.utils.device import DeviceDetector

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1")


def get_document_service() -> DocumentService:
    """Get document service instance."""
    return DocumentService(
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        aws_region=settings.aws_region,
        timeout_seconds=settings.s3_timeout_seconds,
        allowed_buckets=settings.s3_allowed_buckets_list,
        endpoint_url=settings.s3_endpoint_url,
    )


def get_cache_service() -> CacheService:
    """Get cache service instance."""
    return CacheService()


def get_image_optimizer() -> ImageOptimizer:
    """Get image optimizer instance."""
    return ImageOptimizer()


async def process_render_request(
    request: Request,
    s3_url: str,
    page: int,
    output: str,
    device: Optional[str],
    quality: Optional[str],
    max_width: Optional[int],
    pixel_ratio: Optional[float],
    format: Optional[str],
    document_service: DocumentService,
    cache_service: CacheService,
    optimizer: ImageOptimizer,
    start_time: float,
) -> Response:
    """Core render processing logic."""
    detected_device: str
    if device == "auto":
        detected_device = DeviceDetector.detect_device(request)
        logger.info(f"Auto-detected device: {detected_device}")
    else:
        detected_device = device or "auto"

    if pixel_ratio is None:
        pixel_ratio = DeviceDetector.detect_pixel_ratio(request)

    cache_key = cache_service.generate_cache_key(
        s3_url=str(s3_url),
        page=page,
        device=detected_device or "auto",
        quality=quality or "auto",
        max_width=max_width,
        pixel_ratio=pixel_ratio,
        output_format=format or "auto",
    )

    cached_result = await cache_service.get(cache_key)
    if cached_result:
        cached_result["cache_hit"] = True
        logger.info(f"Cache hit for {cache_key}")
        return _format_response(cached_result, output)

    logger.info(f"Cache miss for {cache_key}, processing document")

    document_bytes = await document_service.fetch_from_s3(str(s3_url))

    raw_image = await document_service.convert_page_to_image(
        document_bytes, page, DEFAULT_DPI
    )

    image_bytes, metadata = optimizer.optimize_for_web(
        raw_image,
        device=detected_device or "auto",
        quality=quality,
        max_width=max_width,
        pixel_ratio=pixel_ratio,
        output_format=format or "auto",
        pdf_size_bytes=len(document_bytes),
    )

    base64_data = optimizer.encode_base64(
        image_bytes, f"image/{metadata.format.lower()}"
    )
    base64_string = base64_data.split(",", 1)[1]

    processing_ms = int((time.time() - start_time) * 1000)

    if metadata.pdf_size_bytes:
        compression_ratio = metadata.optimized_size / metadata.pdf_size_bytes
        original_size = metadata.pdf_size_bytes
    else:
        compression_ratio = metadata.optimized_size / metadata.original_size
        original_size = metadata.original_size

    response_data = {
        "data": base64_string,
        "format": metadata.format.lower(),
        "mime_type": f"image/{metadata.format.lower()}",
        "width": metadata.width,
        "height": metadata.height,
        "size_bytes": metadata.optimized_size,
        "compression_ratio": compression_ratio,
        "cache_hit": False,
        "processing_ms": processing_ms,
        "optimizations": metadata.optimizations,
        "original_size_bytes": original_size,
    }

    await cache_service.set(cache_key, response_data)

    return _format_response(response_data, output)


@router.get("/render")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
@limiter.limit(f"{settings.rate_limit_per_hour}/hour")
async def render_page(
    request: Request,
    s3_url: str = Query(..., description="S3 URL of the document (s3://bucket/key)"),
    page: int = Query(..., ge=1, description="Page number to render (1-indexed)"),
    output: Literal["base64", "json", "binary"] = Query(
        default="base64", description="Response format"
    ),
    device: Optional[Literal["desktop", "tablet", "mobile", "auto"]] = Query(
        default="auto", description="Target device profile"
    ),
    quality: Optional[str] = Query(default="auto", description="Image quality setting"),
    max_width: Optional[int] = Query(
        default=None, ge=100, le=3840, description="Maximum width in pixels"
    ),
    pixel_ratio: Optional[float] = Query(
        default=None, ge=1.0, le=3.0, description="Device pixel ratio"
    ),
    format: Optional[Literal["auto", "webp", "avif", "jpeg", "png"]] = Query(
        default="auto", description="Output image format"
    ),
    document_service: DocumentService = Depends(get_document_service),
    cache_service: CacheService = Depends(get_cache_service),
    optimizer: ImageOptimizer = Depends(get_image_optimizer),
) -> Response:
    """
    Render a document page to an optimized image.

    Returns base64-encoded, JSON, or binary image based on output parameter.
    """
    start_time = time.time()

    try:
        response = await asyncio.wait_for(
            process_render_request(
                request=request,
                s3_url=str(s3_url),
                page=page,
                output=output,
                device=device,
                quality=quality,
                max_width=max_width,
                pixel_ratio=pixel_ratio,
                format=format,
                document_service=document_service,
                cache_service=cache_service,
                optimizer=optimizer,
                start_time=start_time,
            ),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        return response

    except asyncio.TimeoutError:
        logger.error(f"Request timeout after {REQUEST_TIMEOUT_SECONDS}s")
        raise HTTPException(
            status_code=504,
            detail=f"Request timeout: processing took longer than {REQUEST_TIMEOUT_SECONDS}s",
        )

    except DocumentFetchError as e:
        logger.error(f"Document fetch error: {e}")
        raise HTTPException(status_code=404, detail=str(e))

    except DocumentConversionError as e:
        logger.error(f"Document conversion error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error rendering page: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


def _format_response(data: dict[str, object], output: str) -> Response:
    """
    Format response based on output type.

    Args:
        data: Response data dictionary
        output: Output format ('base64', 'json', 'binary')

    Returns:
        Formatted response
    """
    if output == "json":
        return JSONResponse(content=data)

    elif output == "base64":
        mime_type = data["mime_type"]
        base64_data = data["data"]
        data_uri = f"data:{mime_type};base64,{base64_data}"
        return PlainTextResponse(content=data_uri)

    elif output == "binary":
        import base64

        base64_data = str(data["data"])
        mime_type = str(data["mime_type"])
        binary_data = base64.b64decode(base64_data)
        return Response(
            content=binary_data,
            media_type=mime_type,
            headers={
                "Content-Length": str(len(binary_data)),
                "Cache-Control": "public, max-age=604800",
            },
        )

    else:
        raise HTTPException(status_code=400, detail=f"Invalid output format: {output}")


@router.get("/health")
async def health_check(
    cache_service: CacheService = Depends(get_cache_service),
) -> JSONResponse:
    """
    Health check endpoint.

    Checks L1 cache status.
    """
    checks: dict[str, dict[str, object]] = {}
    overall_status = "healthy"

    try:
        cache_size_mb = cache_service.l1_cache.current_size / (1024 * 1024)
        checks["l1_cache"] = {
            "status": "healthy",
            "size_mb": round(cache_size_mb, 2),
        }
    except Exception as e:
        checks["l1_cache"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "degraded"

    return JSONResponse(
        content={
            "status": overall_status,
            "checks": checks,
        }
    )


