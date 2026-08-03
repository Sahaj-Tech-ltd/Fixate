"""Backend abstraction for file storage operations.

Cloud mode: AWS S3 with pre-signed URLs.
Desktop mode: local filesystem under MEDIA_ROOT.
"""

import mimetypes
import os
import re
import uuid

from django.conf import settings


def _sanitize_filename(filename):
    """Strip path separators, null bytes, and path traversal from filename."""
    if not filename:
        return "document.pdf"
    filename = filename.replace("\x00", "")
    filename = os.path.basename(filename)
    filename = filename.lstrip(".")
    if not filename or not filename.strip():
        return "document.pdf"
    return filename


def _safe_extension(filename):
    """Extract file extension safely — only the extension, no path noise."""
    sanitized = _sanitize_filename(filename)
    _, ext = os.path.splitext(sanitized)
    ext = ext.lstrip(".").lower()
    if not ext or len(ext) > 10 or re.search(r'[/\\\x00]', ext):
        return "pdf"
    return ext


def _content_type_for_extension(ext):
    """Return MIME content type for a file extension. Falls back to octet-stream."""
    # Try Python's mimetypes first
    mime, _ = mimetypes.guess_type(f"file.{ext}")
    if mime:
        return mime
    # Manual overrides for common document types
    CONTENT_TYPES = {
        "pdf": "application/pdf",
        "epub": "application/epub+zip",
        "txt": "text/plain",
        "html": "text/html",
        "htm": "text/html",
        "csv": "text/csv",
        "json": "application/json",
        "xml": "application/xml",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    return CONTENT_TYPES.get(ext, "application/octet-stream")


def _generate_key(user_id, filename):
    ext = _safe_extension(filename)
    return f"uploads/{user_id}/documents/{uuid.uuid4()}.{ext}"


def _validate_key_within_root(key):
    """Resolve key against MEDIA_ROOT and verify it stays within bounds.

    Returns the safe absolute path. Raises ValueError on path traversal.
    """
    raw_path = os.path.join(settings.MEDIA_ROOT, key)
    resolved = os.path.realpath(raw_path)
    root = os.path.realpath(settings.MEDIA_ROOT)
    if not resolved.startswith(root + os.sep) and resolved != root:
        raise ValueError(
            f"Path traversal blocked: key {key!r} resolves outside MEDIA_ROOT"
        )
    return resolved


def _s3_configured():
    """Return True only if all AWS/S3 settings are present."""
    return bool(
        settings.AWS_ACCESS_KEY_ID
        and settings.AWS_SECRET_ACCESS_KEY
        and settings.AWS_STORAGE_BUCKET_NAME
    )


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


def generate_upload_url(user_id, filename, expires_in=3600):
    """Return {'url': ..., 'key': ..., 'expires_in': ...}

    Cloud with S3: pre-signed S3 PUT URL.
    Cloud without S3 or Desktop: local upload via multipart POST.
    """
    if settings.FIXATE_MODE == "desktop" or not _s3_configured():
        key = _generate_key(user_id, filename)
        # Return local upload endpoint URL so the frontend PUT flow works unchanged
        local_url = f"{settings.FORCE_SCRIPT_NAME}/api/documents/upload-local/{key}"
        return {
            "url": local_url,
            "key": key,
            "expires_in": expires_in,
        }
    else:
        s3_client = _s3_client()
        key = _generate_key(user_id, filename)
        ext = _safe_extension(filename)
        content_type = _content_type_for_extension(ext)
        try:
            url = s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in,
            )
            return {"url": url, "key": key, "expires_in": expires_in}
        except Exception as e:
            raise Exception(f"Failed to generate upload URL: {e}")


def generate_download_url(key, expires_in=3600):
    """Return a URL string for downloading the file.

    S3: pre-signed S3 GET URL.
    Local: /media/ relative URL.
    """
    if settings.FIXATE_MODE == "desktop" or not _s3_configured():
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

    S3: S3 delete_object.
    Local (desktop or cloud without S3): os.remove from MEDIA_ROOT.
    """
    if settings.FIXATE_MODE == "desktop" or not _s3_configured():
        file_path = _validate_key_within_root(key)
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
    if settings.FIXATE_MODE == "desktop" or not _s3_configured():
        file_path = _validate_key_within_root(key)
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
    """Return the absolute local filesystem path for a file key.

    Validates that the resolved path stays within MEDIA_ROOT.
    Works in desktop mode and cloud-without-S3 mode.
    """
    return _validate_key_within_root(key)


def save_uploaded_file(user_id, filename, file_obj):
    """Save an uploaded file to local storage (desktop only).

    Returns the file key (relative path).
    """
    key = _generate_key(user_id, filename)
    dest_path = _validate_key_within_root(key)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as f:
        for chunk in file_obj.chunks():
            f.write(chunk)
    return key
