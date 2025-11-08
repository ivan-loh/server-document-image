#!/bin/sh
set -e

echo "Waiting for Garage to be ready..."
sleep 5

# Create access key and secret
ACCESS_KEY="GK1234567890abcdefgh"
SECRET_KEY="0123456789abcdef0123456789abcdef0123456789abcdef"
BUCKET="test-documents"

echo "Creating key..."
garage -c /etc/garage.toml key create default 2>/dev/null || echo "Key already exists"

echo "Importing key credentials..."
garage -c /etc/garage.toml key import \
  $ACCESS_KEY \
  $SECRET_KEY \
  default 2>/dev/null || echo "Key already imported"

echo "Creating bucket..."
garage -c /etc/garage.toml bucket create $BUCKET 2>/dev/null || echo "Bucket already exists"

echo "Allowing access to bucket..."
garage -c /etc/garage.toml bucket allow \
  --read \
  --write \
  --owner \
  $BUCKET \
  --key $ACCESS_KEY 2>/dev/null || echo "Access already granted"

# Upload sample PDFs if they exist
if [ -d "/resources" ]; then
  echo "Uploading sample PDFs..."
  for file in /resources/*.pdf; do
    if [ -f "$file" ]; then
      filename=$(basename "$file")
      echo "Uploading $filename..."
      # Use AWS CLI to upload
      AWS_ACCESS_KEY_ID=$ACCESS_KEY \
      AWS_SECRET_ACCESS_KEY=$SECRET_KEY \
      aws s3 cp "$file" "s3://$BUCKET/$filename" \
        --endpoint-url http://garage:3900 \
        --region garage 2>/dev/null || echo "$filename already exists or upload failed"
    fi
  done
fi

echo "Garage S3 initialization complete!"
echo "Endpoint: http://localhost:3900"
echo "Bucket: $BUCKET"
echo "Access Key: $ACCESS_KEY"
