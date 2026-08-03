"""
DEPRECATED: This module is superseded by config.backends.storage.

All functionality has been moved to config.backends.storage, which provides
a unified interface for both cloud (S3) and desktop (local) storage backends.

This file remains as a compatibility shim re-exporting from the new module.
Import directly from config.backends.storage in new code.
"""
import warnings

warnings.warn(
    "apps.documents.s3_utils is deprecated. Use config.backends.storage instead.",
    DeprecationWarning,
    stacklevel=2,
)

from config.backends.storage import (  # noqa: F401, E402
    generate_upload_url as generate_presigned_upload_url,
    generate_download_url as generate_presigned_download_url,
    delete_file as delete_file_from_s3,
)
