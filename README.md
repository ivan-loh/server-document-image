# Document-to-Image Service

High-performance API that converts PDF pages to web-optimized images with device-aware compression and base64 encoding.

## What It Does

- Converts PDF pages to optimized images (WebP, JPEG, PNG)
- Automatically adjusts quality and size based on device type (mobile, tablet, desktop)
- Fetches PDFs from S3 storage
- Returns images as base64, JSON, or binary downloads
- Built-in caching for fast repeated requests

## How It Works

```
┌─────────┐
│ Client  │
└────┬────┘
     │ :8000
┌────▼────────┐
│   FastAPI   │
│  (L1 Cache) │
└──────┬──────┘
       │
       ▼
   ┌───────┐
   │  S3   │
   └───────┘
```

The service fetches PDFs from S3, renders the requested page, optimizes it for the target device, and returns the image with caching for performance.

## Quick Start

### Option 1: Docker with Local S3

Uses local S3-compatible storage (Garage), does not require AWS credentials:

```bash
# Start everything (API + local S3 storage)
docker-compose up -d

# Wait for setup to complete
docker-compose logs -f garage-init

# Test it out
curl "http://localhost:8000/api/v1/render?s3_url=s3://test-documents/sample-report.pdf&page=1&output=json" | jq
```

Services running:
- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Local S3: http://localhost:3900

### Option 2: Docker with AWS S3

Connects to AWS S3 or S3-compatible storage with credentials:

```bash
# Set your AWS credentials
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_REGION=us-east-1
export S3_ALLOWED_BUCKETS=your-bucket

# Start the API
docker-compose -f docker-compose.simple.yml up -d

# Test with your bucket
curl "http://localhost:8000/api/v1/render?s3_url=s3://your-bucket/document.pdf&page=1&output=json" | jq
```

### Option 3: Local Development

Run directly without Docker using uv package manager:

```bash
# Install dependencies (requires uv package manager)
uv sync

# Set AWS credentials in .env file
cat > .env << EOF
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=us-east-1
S3_ALLOWED_BUCKETS=your-bucket
EOF

# Run the server
uv run uvicorn src.main:app --reload

# Access at http://localhost:8000
```

## API Usage

### Endpoints

- `GET /` - Root endpoint
- `GET /api/v1/render` - Convert PDF page to image
- `GET /api/v1/health` - Health check with cache statistics

### Basic Examples

```bash
# Get base64-encoded image (default)
curl "http://localhost:8000/api/v1/render?s3_url=s3://bucket/doc.pdf&page=1"

# Get JSON with metadata and dimensions
curl "http://localhost:8000/api/v1/render?s3_url=s3://bucket/doc.pdf&page=1&output=json" | jq

# Download image file directly
curl "http://localhost:8000/api/v1/render?s3_url=s3://bucket/doc.pdf&page=1&output=binary" > page1.webp
```

### Device-Specific Optimization

The service automatically optimizes images for different device types:

```bash
# Mobile optimization (640px width, quality 80)
curl "http://localhost:8000/api/v1/render?s3_url=s3://bucket/doc.pdf&page=1&device=mobile&output=json" | jq

# Tablet optimization (1024px width, quality 85)
curl "http://localhost:8000/api/v1/render?s3_url=s3://bucket/doc.pdf&page=1&device=tablet&output=json" | jq

# Desktop optimization (1920px width, quality 90)
curl "http://localhost:8000/api/v1/render?s3_url=s3://bucket/doc.pdf&page=1&device=desktop&output=json" | jq

# Retina displays (3840px width, quality 90)
curl "http://localhost:8000/api/v1/render?s3_url=s3://bucket/doc.pdf&page=1&device=retina&output=json" | jq
```

### Custom Quality and Format

```bash
# High quality JPEG
curl "http://localhost:8000/api/v1/render?s3_url=s3://bucket/doc.pdf&page=1&quality=high&format=jpeg&output=json" | jq

# Custom quality value (1-100)
curl "http://localhost:8000/api/v1/render?s3_url=s3://bucket/doc.pdf&page=1&quality=85&output=json" | jq

# PNG for transparency support
curl "http://localhost:8000/api/v1/render?s3_url=s3://bucket/doc.pdf&page=1&format=png&output=json" | jq
```

### Health Check

```bash
# Check service status and cache statistics
curl http://localhost:8000/api/v1/health | jq
```

## API Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `s3_url` | string | required | S3 URL in format: s3://bucket/file.pdf |
| `page` | int | required | Page number to render (starts at 1) |
| `output` | enum | `base64` | Response format: `base64`, `json`, `binary` |
| `device` | enum | `auto` | Device profile: `mobile`, `tablet`, `desktop`, `retina`, `auto` |
| `quality` | string | `auto` | Quality preset: `low`, `medium`, `high`, `auto`, or number 1-100 |
| `max_width` | int | null | Maximum image width in pixels (100-3840) |
| `pixel_ratio` | float | 1.0 | Device pixel ratio for high-DPI displays (1.0-3.0) |
| `format` | enum | `auto` | Image format: `auto`, `webp`, `jpeg`, `png` |

## Device Profiles

Each device profile has optimized defaults:

| Profile | Width | Quality | Format | Use Case |
|---------|-------|---------|--------|----------|
| Mobile | 640px | 80 | WebP | Smartphones |
| Tablet | 1024px | 85 | WebP | Tablets, iPad |
| Desktop | 1920px | 90 | WebP | Desktop browsers |
| Retina | 3840px | 90 | WebP | High-DPI displays |

## Configuration

### Environment Variables

Create a `.env` file or set these environment variables:

```env
# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=us-east-1
S3_ALLOWED_BUCKETS=bucket1,bucket2  # Comma-separated list of allowed buckets
S3_ENDPOINT_URL=http://localhost:3900  # Optional: for S3-compatible storage like Garage

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
API_CORS_ORIGINS=*  # Comma-separated list of allowed origins

# Cache Configuration
CACHE_L1_SIZE_MB=500  # In-memory cache size in megabytes

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
```

### S3 Bucket Access

The service needs read access to your S3 buckets. Make sure:

1. Your AWS credentials have `s3:GetObject` permission
2. The bucket names are listed in `S3_ALLOWED_BUCKETS`
3. For local testing with Garage, no special permissions needed

Example IAM policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::your-bucket/*"
    }
  ]
}
```

## Technical Details

### Architecture Notes

- **Caching**: In-memory L1 LRU cache (default 500MB)
- **Framework**: FastAPI with async request handling
- **Rendering**: PyMuPDF (fitz) for PDF to image conversion
- **Compression**: Pillow for WebP/JPEG/PNG optimization
- **Storage**: S3-compatible object storage (AWS S3, Garage, MinIO, etc.)

### Cache Behavior

- Cache keys include all parameters: S3 URL, page, device, quality, format
- LRU eviction when cache size limit is reached
- Cache hits typically respond in <5ms
- Cache misses take ~660ms (S3 fetch + render + optimize)

### Image Processing Pipeline

1. Fetch PDF from S3 (with caching)
2. Render page at 150 DPI
3. Apply device profile (resize + quality)
4. Compress to target format (WebP preferred)
5. Return as base64, JSON, or binary stream

### Testing

```bash
# Install dependencies with test extras
uv sync --all-extras

# Run test suite (54 tests, ~5.2s)
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Type checking
uv run mypy src/

# Code formatting
uv run black src/ tests/
```
