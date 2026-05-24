"""Backend abstraction for file storage operations.

Cloud mode: AWS S3 with pre-signed URLs.
Desktop mode: local filesystem under MEDIA_ROOT.
"""

import os
import uuid
from pathlib import Path

from django.conf import settings


def _s3_client():
    import boto3
    from botocore.client import Config

    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
        config=Config(signature_version="s3v4"),
    )


def _generate_key(user_id, filename):
    ext = filename.split(".")[-1].lower()
    return f"uploads/{user_id}/documents/{uuid.uuid4()}.{ext}"


def generate_upload_url(user_id, filename, expires_in=3600):
    """Return {'url': ..., 'key': ..., 'expires_in': ...}

    Cloud: pre-signed S3 PUT URL.
    Desktop: local API endpoint (handled directly in the upload view, so just
             returns key info — actual file saving happens in the view).
    """
    if settings.FIXATE_MODE == "desktop":
        key = _generate_key(user_id, filename)
        return {
            "url": None,  # desktop uploads go directly via multipart POST
            "key": key,
            "expires_in": expires_in,
        }
    else:
        s3_client = _s3_client()
        key = _generate_key(user_id, filename)
        try:
            url = s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                    "Key": key,
                    "ContentType": "application/pdf",
                },
                ExpiresIn=expires_in,
            )
            return {"url": url, "key": key, "expires_in": expires_in}
        except Exception as e:
            raise Exception(f"Failed to generate upload URL: {e}")


def generate_download_url(key, expires_in=3600):
    """Return a URL string for downloading the file.

    Cloud: pre-signed S3 GET URL.
    Desktop: /media/ relative URL.
    """
    if settings.FIXATE_MODE == "desktop":
        return f"{settings.MEDIA_URL}{key}"
    else:
        s3_client = _s3_client()
        try:
            url = s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                    "Key": key,
                },
                ExpiresIn=expires_in,
            )
            return url
        except Exception as e:
            raise Exception(f"Failed to generate download URL: {e}")


def delete_file(key):
    """Delete a file. Returns True on success.

    Cloud: S3 delete_object.
    Desktop: os.remove from MEDIA_ROOT.
    """
    if settings.FIXATE_MODE == "desktop":
        file_path = get_local_path(key)
        try:
            os.remove(file_path)
            return True
        except FileNotFoundError:
            return True
        except Exception as e:
            raise Exception(f"Failed to delete file: {e}")
    else:
        s3_client = _s3_client()
        try:
            s3_client.delete_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key
            )
            return True
        except Exception as e:
            raise Exception(f"Failed to delete file: {e}")


def get_file_bytes(key):
    """Return file contents as bytes.

    Cloud: S3 get_object.
    Desktop: read from local filesystem.
    """
    if settings.FIXATE_MODE == "desktop":
        file_path = get_local_path(key)
        with open(file_path, "rb") as f:
            return f.read()
    else:
        s3_client = _s3_client()
        try:
            response = s3_client.get_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key
            )
            return response["Body"].read()
        except Exception as e:
            raise Exception(f"Failed to get file bytes: {e}")


def get_local_path(key):
    """Return the absolute local filesystem path for a file key (desktop only)."""
    return os.path.join(settings.MEDIA_ROOT, key)


def save_uploaded_file(user_id, filename, file_obj):
    """Save an uploaded file to local storage (desktop only).

    Returns the file key (relative path).
    """
    key = _generate_key(user_id, filename)
    dest_path = get_local_path(key)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as f:
        for chunk in file_obj.chunks():
            f.write(chunk)
    return key
