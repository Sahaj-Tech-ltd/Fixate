"""Backend abstraction for OCR processing.

Cloud mode: AWS Textract async job.
Desktop mode: Tesseract OCR (sync).
"""

import logging

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
    """
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError as e:
        raise ImportError(
            "pytesseract and pdf2image are required for desktop OCR. "
            "Install with: pip install pytesseract pdf2image"
        ) from e

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


def _extract_text_textract(file_path_or_key):
    """Placeholder — Textract extraction happens asynchronously via Celery tasks.

    This function is not called directly; the tasks.py module handles the
    Textract flow (start job, poll, collect results). This exists for
    interface completeness.
    """
    raise NotImplementedError(
        "Textract extraction is asynchronous. Use the Celery task flow."
    )
