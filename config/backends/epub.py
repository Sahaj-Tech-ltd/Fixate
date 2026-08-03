"""EPUB text extraction backend.

Uses ebooklib (pure Python) to read EPUB files and extract text
from all XHTML chapters. EPUB files are ZIP archives containing
XHTML content — no OCR needed, just parse and extract.

Pattern matches config/backends/ocr.py for interface consistency.
"""

import logging
import zipfile

logger = logging.getLogger(__name__)

# Max uncompressed EPUB size (100MB) — prevents zip bomb attacks
MAX_UNCOMPRESSED_SIZE = 100 * 1024 * 1024


def extract_text(file_path):
    """Extract text from an EPUB file.

    Args:
        file_path: Local path to the .epub file.

    Returns:
        dict with keys: text, pages (chapters), word_count

    Raises:
        ImportError: if ebooklib is not installed.
        ValueError: if extracted text is insufficient.
    """
    try:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup
    except ImportError as e:
        raise ImportError(
            "ebooklib and beautifulsoup4 are required for EPUB support. "
            "Install with: pip install ebooklib beautifulsoup4"
        ) from e

    try:
        # Check for zip bombs before decompressing
        with zipfile.ZipFile(file_path) as zf:
            total = sum(info.file_size for info in zf.infolist())
            if total > MAX_UNCOMPRESSED_SIZE:
                raise ValueError(
                    f"EPUB uncompressed size {total} exceeds max {MAX_UNCOMPRESSED_SIZE}"
                )

        # Defuse XML parsing to prevent XXE attacks via crafted EPUBs
        try:
            import defusedxml
            defusedxml.defuse_stdlib()
        except ImportError:
            pass

        book = epub.read_epub(file_path)
    except Exception as e:
        raise ValueError(f"Failed to read EPUB file: {e}") from e

    chapters = []
    total_words = 0

    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            try:
                content = item.get_content().decode("utf-8", errors="replace")
            except Exception:
                continue

            soup = BeautifulSoup(content, "html.parser")

            # Remove script/style tags
            for tag in soup(["script", "style", "nav", "header", "footer"]):
                tag.decompose()

            text = soup.get_text(separator="\n")
            # Clean up: collapse multiple newlines, strip
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            cleaned = "\n".join(lines)

            if len(cleaned) > 100:  # skip tiny chapters (TOC, copyright, etc.)
                chapters.append(cleaned)
                total_words += len(cleaned.split())

    if not chapters:
        raise ValueError("No readable text content found in EPUB file")

    # Join chapters with double newline + chapter marker
    full_text_parts = []
    for i, chapter_text in enumerate(chapters, 1):
        # Try to extract a title from the first line
        first_line = chapter_text.split("\n")[0] if "\n" in chapter_text else chapter_text[:80]
        full_text_parts.append(f"Chapter {i}: {first_line}\n\n{chapter_text}")

    full_text = "\n\n---\n\n".join(full_text_parts)

    return {
        "text": full_text,
        "pages": len(chapters),
        "word_count": total_words,
    }
