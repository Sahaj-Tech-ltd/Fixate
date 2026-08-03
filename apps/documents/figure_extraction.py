"""
Figure extraction from PDFs using PyMuPDF (fitz).

Extracts embedded images, detects figure captions, maps "Figure N"
references in OCR text to extracted images.
"""

import re
import logging
from io import BytesIO

import fitz  # PyMuPDF
from PIL import Image
from django.core.files.base import ContentFile

from apps.documents.models import Document, Figure

logger = logging.getLogger(__name__)

FIGURE_REF_PATTERNS = [
    re.compile(r"Figure\s+(\d+(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"Fig\.\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"Fig\s+(\d+(?:\.\d+)?)", re.IGNORECASE),
]

MIN_FIGURE_WIDTH = 150
MIN_FIGURE_HEIGHT = 100


def extract_figures(document: Document, pdf_path: str = None) -> int:
    """Extract figures from a document's PDF. Idempotent (deletes existing first)."""
    if pdf_path is None:
        from config.backends import storage
        pdf_path = storage.get_local_path(document.file_key)

    document.figures.all().delete()

    doc = fitz.open(pdf_path)
    figures = []

    try:
        full_text = document.raw_text

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_figs = _extract_page(doc, document, page, page_num, full_text)
            figures.extend(page_figs)

        figures.sort(key=_sort_key)

        for i, fig in enumerate(figures):
            fig.sort_order = i
            fig.save(update_fields=["sort_order"])

        logger.info("Extracted %d figures from doc %d", len(figures), document.id)

    finally:
        doc.close()

    return len(figures)


def _extract_page(doc, document, page, page_num, full_text):
    """Extract figures from one page."""
    figures = []
    image_list = page.get_images(full=True)

    for img_index, img_info in enumerate(image_list):
        xref = img_info[0]
        width = img_info[2]
        height = img_info[3]

        if width < MIN_FIGURE_WIDTH and height < MIN_FIGURE_HEIGHT:
            continue

        try:
            base_image = doc.extract_image(xref)
            if not base_image:
                continue

            image_bytes = base_image["image"]
            pil_image = Image.open(BytesIO(image_bytes))
            if pil_image.mode in ("RGBA", "LA", "P"):
                pil_image = pil_image.convert("RGBA")
            else:
                pil_image = pil_image.convert("RGB")

            caption, figure_number = _detect_caption(page, img_info, full_text)
            reference_text = _find_reference(figure_number, full_text, caption)

            img_buffer = BytesIO()
            pil_image.save(img_buffer, format="PNG", optimize=True)
            img_buffer.seek(0)

            fig = Figure(
                document=document,
                page_number=page_num + 1,
                figure_number=figure_number,
                reference_text=reference_text,
                caption=caption,
                width=width,
                height=height,
                sort_order=img_index,
                bounding_box=_bbox(img_info),
            )

            filename = f"figure_{document.id}_p{page_num+1}_{img_index}.png"
            fig.image.save(filename, ContentFile(img_buffer.read()), save=False)
            img_buffer.close()

            thumb = _thumbnail(pil_image)
            thumb_buf = BytesIO()
            thumb.save(thumb_buf, format="PNG", optimize=True)
            thumb_buf.seek(0)
            fig.thumbnail.save(f"thumb_{filename}", ContentFile(thumb_buf.read()), save=False)
            thumb_buf.close()

            fig.save()
            figures.append(fig)

        except Exception as e:
            logger.warning("Failed image %d on page %d doc %d: %s", img_index, page_num + 1, document.id, e)
            continue

    return figures


def _detect_caption(page, img_info, full_text):
    """Find caption text near an image on the page."""
    caption = ""
    figure_number = ""

    bbox = img_info[1:5]
    if not bbox or len(bbox) < 4:
        return caption, figure_number

    x0, y0, x1, y1 = bbox[:4]
    blocks = page.get_text("blocks")

    candidates = []
    for block in blocks:
        bx0, by0, bx1, by1, text, block_type, _ = block
        if block_type != 0:
            continue
        # Text below image
        vdist = by0 - y1
        if -10 < vdist < 100:
            candidates.append((vdist, text.strip()))
        # Text above image
        if -100 < (y0 - by1) < 10:
            candidates.append((y0 - by1, text.strip()))

    candidates.sort(key=lambda x: abs(x[0]))

    for _, text in candidates[:3]:
        if not text:
            continue
        for pat in FIGURE_REF_PATTERNS:
            m = pat.search(text)
            if m:
                return text[:300], m.group(1)

    if candidates:
        caption = candidates[0][1][:300]

    return caption, figure_number


def _find_reference(figure_number, full_text, caption):
    """Find the reference string in the full text."""
    if not figure_number:
        return ""
    for pat in FIGURE_REF_PATTERNS:
        for m in pat.finditer(full_text):
            if m.group(1) == figure_number:
                return m.group(0)
    return ""


def _bbox(img_info):
    b = img_info[1:5]
    if len(b) >= 4:
        return {"x0": b[0], "y0": b[1], "x1": b[2], "y1": b[3]}
    return {}


def _thumbnail(pil_image, size=(200, 200)):
    t = pil_image.copy()
    t.thumbnail(size, Image.LANCZOS)
    return t


def _sort_key(fig):
    num = fig.figure_number
    if num:
        try:
            parts = [int(p) for p in num.split(".")]
            return (0, tuple(parts), fig.page_number)
        except ValueError:
            return (1, 0, ord(num[0]) if num else 0, fig.page_number)
    return (2, 0, 0, fig.page_number)
