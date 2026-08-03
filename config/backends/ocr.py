"""Backend abstraction for OCR processing.

Cloud mode: AWS Textract async job.
Desktop mode: Tesseract OCR (sync).
"""

import logging
import sys

from django.conf import settings

logger = logging.getLogger(__name__)


def extract_text(file_path_or_key, mode=None):
    """Extract text from a document.

    Args:
        file_path_or_key: Local file path (desktop) or S3 key (cloud).
        mode: Override FIXATE_MODE. Defaults to settings.FIXATE_MODE.

    Returns:
        dict with keys: text, pages, word_count

    Raises:
        ValueError: if extracted text is insufficient.
    """
    if mode is None:
        mode = settings.FIXATE_MODE

    if mode == "desktop":
        return _extract_text_tesseract(file_path_or_key)
    else:
        return _extract_text_textract(file_path_or_key)


def _extract_text_tesseract(file_path):
    """Use Tesseract OCR via pytesseract + pdf2image.

    The file_path should be a local PDF file path.
    Resolves tesseract binary from PATH, bundled location, or common install dirs.
    """
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError as e:
        raise ImportError(
            "pytesseract and pdf2image are required for desktop OCR. "
            "Install with: pip install pytesseract pdf2image"
        ) from e

    # Resolve tesseract binary path for offline/bundled desktop use
    _resolve_tesseract_path(pytesseract)

    try:
        images = convert_from_path(file_path, dpi=300)
    except Exception as e:
        raise ValueError(f"Failed to convert PDF to images: {e}") from e

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
        "word_count": len(full_text.split()),
    }


def _resolve_tesseract_path(pytesseract):
    """Find and configure the tesseract binary path for desktop bundles.

    Checks (in order):
      1. System PATH (default pytesseract behavior)
      2. Bundled next to the executable (PyInstaller onefile)
      3. Common Linux install locations
    """
    import shutil
    from pathlib import Path

    # 1. Already on PATH? Let pytesseract handle it.
    if shutil.which("tesseract"):
        return

    # 2. Check bundled location (next to the PyInstaller binary)
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        bundled = exe_dir / "tesseract" / "tesseract"
        if bundled.exists():
            pytesseract.pytesseract.tesseract_cmd = str(bundled)
            # Also set TESSDATA_PREFIX for bundled traineddata
            tessdata = exe_dir / "tesseract" / "tessdata"
            if tessdata.exists():
                import os as _os
                _os.environ.setdefault("TESSDATA_PREFIX", str(tessdata))
            return

    # 3. Check common install locations
    common_paths = [
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/snap/bin/tesseract",
    ]
    for path in common_paths:
        if Path(path).exists():
            pytesseract.pytesseract.tesseract_cmd = path
            return

    # 4. Not found — pytesseract will raise TesseractNotFoundError later


def _extract_text_textract(file_path_or_key):
    """Placeholder — Textract extraction happens asynchronously via Celery tasks.

    This function is not called directly; the tasks.py module handles the
    Textract flow (start job, poll, collect results). This exists for
    interface completeness.
    """
    raise NotImplementedError(
        "Textract extraction is asynchronous. Use the Celery task flow."
    )
