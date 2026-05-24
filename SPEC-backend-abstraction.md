# SPEC: Fixate Backend Abstraction Layer

## Goal
Refactor Fixate to run in three modes via a single `FIXATE_MODE` env var:
- `cloud` (default): PostgreSQL + S3 + Textract + Celery (current behavior, unchanged)
- `desktop`: SQLite + Local FS + Tesseract OCR + sync tasks + single-user auto-auth

## FIXATE_MODE env var
```
FIXATE_MODE=cloud      # default — current behavior
FIXATE_MODE=desktop     # local-first, no cloud deps
```

## Files to Create

### 1. `config/backends/__init__.py`
Empty init file.

### 2. `config/backends/database.py`
Switch DATABASES config based on mode:
```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

def get_database_config(mode):
    if mode == "desktop":
        db_path = BASE_DIR / "db.sqlite3"
        return {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(db_path),
            }
        }
    # cloud: read from env (existing behavior)
    return None  # signals settings.py to use its existing DATABASES
```

### 3. `config/backends/storage.py`
Abstract file storage operations (S3 for cloud, local for desktop).

Interface:
```python
def generate_upload_url(user_id, filename, expires_in=3600):
    """Returns {'url': ..., 'key': ..., 'expires_in': ...}"""
    
def generate_download_url(key, expires_in=3600):
    """Returns URL string"""

def delete_file(key):
    """Returns True on success"""

def get_file_bytes(key):
    """Returns file contents as bytes (desktop mode needs this for OCR)"""
```

Desktop implementation:
- `generate_upload_url`: Store files in `MEDIA_ROOT / "uploads" / user_id / "documents" / uuid.ext`. Return a local API endpoint URL like `/api/documents/file/<uuid>/` 
- Actually, simpler: just save the file directly in the upload view instead of pre-signed URLs. The desktop flow should be: upload via multipart form → save locally → process.
- `generate_download_url`: Return `/media/uploads/{user_id}/documents/{filename}`
- `delete_file`: `os.remove(path)`

### 4. `config/backends/ocr.py`
Abstract OCR processing.

Interface:
```python
def extract_text(file_path_or_key, mode):
    """
    Returns: {"text": "...", "pages": N, "word_count": N}
    Raises: ValueError if text insufficient
    """
```

Desktop (Tesseract) implementation:
```python
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

def extract_text_tesseract(file_path):
    images = convert_from_path(file_path, dpi=300)
    all_text = []
    for img in images:
        text = pytesseract.image_to_string(img)
        all_text.append(text)
    full_text = "\n\n".join(all_text)
    if len(full_text.strip()) < 50:
        raise ValueError("OCR extracted insufficient text")
    return {
        "text": full_text,
        "pages": len(images),
        "word_count": len(full_text.split())
    }
```

Cloud (Textract) — keep existing code, just wrap in the interface.

### 5. `config/backends/tasks.py`
Abstract async task execution.

Interface:
```python
def process_document_async(document_id):
    """Fire-and-forget document processing"""
```

Desktop: `process_document(document_id)` — called synchronously, directly.
Cloud: `process_document.delay(document_id)` — Celery task, existing behavior.

### 6. `config/backends/auth.py`
Single-user mode for desktop.

```python
def configure_auth(mode):
    """Returns auth-related settings dict or None for defaults"""
    if mode == "desktop":
        return {
            "AUTO_LOGIN_USERNAME": "fixate-user",
            # Middleware that auto-creates and logs in the default user
        }
    return None
```

Implementation for desktop auto-login:
- Create a middleware `config/middleware.py` → `AutoLoginMiddleware`
- On first request, create a User with email="local@fixate.app" and log them in
- Bypass allauth entirely — no signup/login pages needed
- The middleware sets `request.user` to the local user

### 7. `config/backends/media.py` (NEW — needed for desktop file serving)
Desktop needs to serve uploaded PDFs via Django (no S3). 
- `MEDIA_URL = "/media/"`
- `MEDIA_ROOT = BASE_DIR / "media"`
- Add `static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` to urls.py when desktop

## Files to Modify

### `config/settings.py`
At the top, after `env = environ.Env(...)`:
```python
FIXATE_MODE = env("FIXATE_MODE", default="cloud")
```

Replace or wrap the existing database config:
```python
from config.backends.database import get_database_config
_db_config = get_database_config(FIXATE_MODE)
if _db_config:
    DATABASES = _db_config
else:
    DATABASES = { ... existing ... }
```

Replace AWS settings with backend abstraction (import later where used).

Wrap Celery config:
```python
if FIXATE_MODE != "desktop":
    CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = CELERY_BROKER_URL
```

Add desktop-specific settings:
```python
if FIXATE_MODE == "desktop":
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"
    
    # Skip email verification in single-user mode
    ACCOUNT_EMAIL_VERIFICATION = "none"
    
    # Add auto-login middleware at TOP of middleware stack
    MIDDLEWARE.insert(0, "config.middleware.AutoLoginMiddleware")
```

### `config/urls.py`
Add media serving for desktop:
```python
if settings.FIXATE_MODE == "desktop":
    from django.conf.urls.static import static
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

### `config/middleware.py` (NEW)
```python
from django.contrib.auth import login
from django.conf import settings

class AutoLoginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if not request.user.is_authenticated:
            from apps.users.models import User
            user, _ = User.objects.get_or_create(
                email="local@fixate.app",
                defaults={"tier": User.TIER_PRO}  # desktop = always pro
            )
            login(request, user)
        return self.get_response(request)
```

### `apps/documents/views.py`
Replace direct imports of `s3_utils.generate_presigned_upload_url` with backend dispatch:
```python
from config.backends import storage

# In DocumentUploadView.post:
upload_data = storage.generate_upload_url(request.user.id, filename)

# In DocumentDetailView.delete:
storage.delete_file(document.file_key)
```

### `apps/documents/s3_utils.py`
Refactor into `config/backends/storage.py`. Keep this file as a thin wrapper for backward compat or delete it.

### `apps/documents/tasks.py`
Replace direct Textract calls:
```python
from config.backends import ocr, storage

@shared_task(bind=True, max_retries=3)
def process_document(self, document_id):
    # ... existing setup code ...
    
    if settings.FIXATE_MODE == "desktop":
        # Get local file path
        file_path = storage.get_local_path(document.file_key)
        result = ocr.extract_text(file_path)
    else:
        # Existing Textract flow
        ...
```

Wait — actually for desktop, the upload is different. Let me think about this...

For desktop mode, the upload flow should be simpler:
1. User selects file in browser
2. File uploaded via multipart POST to `/api/documents/upload/`
3. File saved to `MEDIA_ROOT/uploads/{user_id}/documents/{uuid}.pdf`
4. Document created with `file_key` = relative path
5. OCR runs synchronously (Tesseract)
6. Document status set to `ready` immediately

So we need a different upload view for desktop, OR make the existing view dispatch on mode.

The cleanest approach: modify `DocumentUploadView` to handle both flows:
```python
def post(self, request):
    if settings.FIXATE_MODE == "desktop":
        # Handle multipart file upload directly
        file = request.FILES.get('file')
        # save, create document, run OCR sync
    else:
        # Existing pre-signed S3 flow
```

But this mixes concerns. Better: separate views or dispatch in the view.

Actually the simplest approach: just modify the existing views minimally. The backend abstraction handles the storage/OCR difference.

For desktop upload:
- `DocumentUploadView.post()` → if desktop, accept multipart upload, save file, create document, trigger sync OCR
- `DocumentConfirmUploadView` → if desktop, this is a no-op (file already saved)

### `apps/documents/serializers.py`
For desktop, add a `file` field to `DocumentUploadSerializer` (FileField).

### `Dockerfile`
Add `collectstatic` step.

### `docker-compose.yml`
Add `FIXATE_MODE=cloud` env var explicitly.

### `requirements/base.txt`
Add:
```
pytesseract>=0.3
pdf2image>=1.16
Pillow>=10.0
```

## Migration Strategy
- No new models — no migrations needed for backend abstraction
- The existing migrations work for both PostgreSQL and SQLite
- For desktop, run `python manage.py migrate` on first launch

## Testing
- Test database switching (SQLite backend creates db.sqlite3)
- Test Tesseract OCR on a sample PDF
- Test local file storage (upload, download, delete)
- Test auto-login middleware (first request creates user, subsequent requests reuse)
- Test that cloud mode is unchanged (regression)

## Success Criteria
1. `FIXATE_MODE=cloud`: App behaves exactly as before (no regressions)
2. `FIXATE_MODE=desktop`: 
   - App starts with SQLite (no PostgreSQL needed)
   - Visiting any page auto-creates and logs in a local user
   - Uploading a PDF saves locally and runs Tesseract OCR synchronously
   - Reader displays extracted text
   - No Celery, Redis, S3, or Textract required
