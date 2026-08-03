"""
RED TEAM: Document Upload Flow Adversarial Tests.

P0 = crash/security | P1 = data loss | P2 = wrong behavior | P3 = UX/error handling

Upload surface: multipart file POST to /api/documents/upload/
Desktop mode: saves locally, runs OCR/EPUB sync.
"""

import io
import os
import tempfile
import uuid
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from rest_framework import status

from apps.documents.models import Document
from apps.users.models import User


# ── Fixtures ──

@pytest.fixture
def user(db):
    return User.objects.create(email="redteam@test.com")


@pytest.fixture
def client(user):
    c = Client()
    c.force_login(user)
    return c


# ── Helper ──

def make_pdf_bytes(num_pages=1):
    """Create a minimal valid PDF in memory."""
    pages = []
    for i in range(num_pages):
        pages.append(
            f"{i + 1} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {3 + i * 2} 0 R >>\nendobj\n"
        )
    content_streams = []
    for i in range(num_pages):
        content_streams.append(
            f"{3 + i * 2} 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 72 720 Td "
            f"(Page {i + 1}) Tj ET\nendstream\nendobj\n"
        )
    font_obj = (
        f"{3 + num_pages * 2} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    )
    xref_offset = sum(len(p) for p in pages) + sum(len(c) for c in content_streams) + len(font_obj) + 200

    header = "%PDF-1.4\n%€µ\n"
    catalog = "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    pages_tree = f"2 0 obj\n<< /Type /Pages /Kids [{' '.join(str(i+1) + ' 0 R' for i in range(num_pages))}] /Count {num_pages} >>\nendobj\n"

    body = header + catalog + pages_tree + "".join(pages) + "".join(content_streams) + font_obj
    xref = f"xref\n0 {3 + num_pages * 2 + 1}\n0000000000 65535 f \n"
    trailer = f"trailer\n<< /Root 1 0 R /Size {3 + num_pages * 2 + 1} >>\nstartxref\n{xref_offset}\n%%EOF\n"

    return bytes(body + xref + trailer, "utf-8")


def make_epub_bytes():
    """Create a minimal valid EPUB in memory (ZIP with mimetype + content)."""
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as zf:
        zf.writestr('mimetype', 'application/epub+zip')
        zf.writestr(
            'META-INF/container.xml',
            '<?xml version="1.0"?><container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>'
        )
        zf.writestr(
            'content.opf',
            '<?xml version="1.0"?><package version="2.0" xmlns="http://www.idpf.org/2007/opf">'
            '<metadata><dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">Test</dc:title></metadata>'
            '<manifest><item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/></manifest>'
            '<spine><itemref idref="ch1"/></spine></package>'
        )
        zf.writestr(
            'ch1.xhtml',
            '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Ch1</title></head>'
            '<body><h1>Chapter One</h1><p>'
            'This is a test chapter with enough text to pass the 100-char minimum threshold '
            'for chapter extraction. We need more text here to make sure it all works correctly '
            'and the EPUB backend can actually parse this properly.</p></body></html>'
        )
    return buf.getvalue()


# =============================================================================
# P0 — SECURITY / CRASH TESTS
# =============================================================================

@pytest.mark.django_db
class TestDocumentUploadSecurityP0:
    """Tests that MUST crash or be blocked — failures here are critical."""

    def test_upload_null_byte_in_filename__P0(self, client):
        """SCORE: P0 — filename with null byte could cause path truncation."""
        pdf_bytes = make_pdf_bytes()
        evil_name = "test\x00hidden.exe.pdf"
        upload = SimpleUploadedFile(evil_name, pdf_bytes, content_type="application/pdf")
        response = client.post("/api/documents/upload/", {"file": upload})

        # Should either 400 (reject) or sanitize the filename. 500 = P0.
        response_data = response.json() if response.content else {}
        assert response.status_code != 500, (
            f"P0 VULN: Null byte in filename caused 500 crash. Response: {response_data}"
        )
        # At minimum, should not create a document with the null byte path
        if response.status_code == 201:
            doc = Document.objects.order_by("-id").first()
            assert "\x00" not in doc.file_key, (
                f"P0 VULN: Null byte preserved in file_key: {doc.file_key}"
            )

    def test_upload_path_traversal_in_filename__P0(self, client):
        """SCORE: P0 — ../../../etc/passwd in filename could escape MEDIA_ROOT."""
        pdf_bytes = make_pdf_bytes()
        evil_name = "../../../etc/passwd.pdf"
        upload = SimpleUploadedFile(evil_name, pdf_bytes, content_type="application/pdf")
        response = client.post("/api/documents/upload/", {"file": upload})

        response_data = response.json() if response.content else {}
        assert response.status_code != 500, (
            f"P0 VULN: Path traversal filename caused 500 crash. Response: {response_data}"
        )
        if response.status_code == 201:
            doc = Document.objects.order_by("-id").first()
            assert ".." not in doc.file_key, (
                f"P0 VULN: Path traversal preserved in file_key: {doc.file_key}"
            )
            # Check no file was written outside MEDIA_ROOT
            from django.conf import settings
            import shutil
            media = os.path.abspath(settings.MEDIA_ROOT)
            for root, dirs, files in os.walk(media):
                for f in files:
                    abs_path = os.path.abspath(os.path.join(root, f))
                    assert abs_path.startswith(media), (
                        f"P0 VULN: File escaped MEDIA_ROOT: {abs_path}"
                    )

    def test_upload_malicious_file_with_pdf_extension__P0(self, client):
        """SCORE: P0 — Uploading a shell script disguised as .pdf feeds it to OCR."""
        shell_script = b"#!/bin/bash\necho 'pwned' > /tmp/pwned.txt\n"
        upload = SimpleUploadedFile("innocent.pdf", shell_script, content_type="application/pdf")
        response = client.post("/api/documents/upload/", {"file": upload})

        response_data = response.json() if response.content else {}
        # If it reaches OCR, pdf2image will crash — should be handled gracefully
        assert response.status_code != 500, (
            f"P0 VULN: Malicious file with .pdf extension caused 500. "
            f"Response: {response_data}"
        )
        # Document should be in error state, not crashed
        if "document_id" in response_data or "id" in response_data:
            doc_id = response_data.get("document_id") or response_data.get("id")
            if doc_id:
                doc = Document.objects.get(id=doc_id)
                assert doc.status in (Document.STATUS_ERROR, Document.STATUS_READY), (
                    f"P0 VULN: Malicious file left doc in state: {doc.status}"
                )

    def test_upload_massive_oversized_file__P0(self, client):
        """SCORE: P0 — 51MB+ file should be rejected BEFORE reading to memory."""
        # Mock CONTENT_LENGTH to simulate large file before body is read
        response = client.post(
            "/api/documents/upload/",
            {},
            CONTENT_LENGTH=str(100 * 1024 * 1024),  # 100MB
        )
        assert response.status_code in [400, 413], (
            f"P0 VULN: Oversized file not rejected before parsing. Got {response.status_code}"
        )

    def test_upload_empty_file__P0(self, client):
        """SCORE: P0 — Empty file fed to OCR/EPUB backend will crash."""
        upload = SimpleUploadedFile("empty.pdf", b"", content_type="application/pdf")
        response = client.post("/api/documents/upload/", {"file": upload})

        # Empty PDF should be caught at validation or processing error level
        # Must not 500
        response_data = response.json() if response.content else {}
        assert response.status_code != 500, (
            f"P0 VULN: Empty file caused 500 crash. Response: {response_data}"
        )
        if response.status_code == 201:
            doc = Document.objects.order_by("-id").first()
            # If processing happened, should be error, not stuck
            assert doc.status != Document.STATUS_PROCESSING, (
                f"P0 VULN: Empty file left document stuck in processing"
            )

    def test_upload_emoji_only_filename__P0(self, client):
        """SCORE: P0 — Emoji-only filename should not break filesystem."""
        pdf_bytes = make_pdf_bytes()
        evil_name = "📚✨📖🔥.pdf"
        upload = SimpleUploadedFile(evil_name, pdf_bytes, content_type="application/pdf")
        response = client.post("/api/documents/upload/", {"file": upload})

        assert response.status_code != 500, (
            f"P0 VULN: Emoji filename caused 500 crash."
        )
        if response.status_code == 201:
            doc = Document.objects.order_by("-id").first()
            # File should have been saved without issues
            from django.conf import settings
            assert doc.file_key, "No file_key set"
            full_path = os.path.join(settings.MEDIA_ROOT, doc.file_key)
            assert os.path.exists(full_path), f"P0: Emoji-named file not saved: {full_path}"

    def test_concurrent_upload_same_user__P0(self, client):
        """SCORE: P0 — Concurrent uploads should not corrupt DB or files.

        This tests the _desktop_upload flow for race conditions.
        Since SQLite serializes writes, this won't truly be concurrent,
        but it verifies no integrity errors from multiple rapid uploads.
        """
        pdf_bytes = make_pdf_bytes()
        docs_created = []
        for i in range(3):
            upload = SimpleUploadedFile(f"concurrent_{i}.pdf", pdf_bytes, content_type="application/pdf")
            response = client.post("/api/documents/upload/", {"file": upload})
            assert response.status_code == 201, f"Upload {i} failed with {response.status_code}"
            docs_created.append(response.json().get("id"))

        # All documents should exist and be distinct
        assert len(set(docs_created)) == 3, "P0: Documents overwritten during concurrent uploads"
        all_docs = Document.objects.filter(id__in=docs_created)
        assert all_docs.count() == 3, f"P0: Expected 3 docs, got {all_docs.count()}"

    def test_upload_control_characters_filename__P0(self, client):
        """SCORE: P0 — Control characters in filename: \r, \n, \t, \x01-\x1f."""
        pdf_bytes = make_pdf_bytes()
        evil_names = [
            "test\r\ninjection.pdf",
            "test\x01control.pdf",
            "test\x1bescape.pdf",
        ]
        for name in evil_names:
            upload = SimpleUploadedFile(name, pdf_bytes, content_type="application/pdf")
            response = client.post("/api/documents/upload/", {"file": upload})
            assert response.status_code != 500, (
                f"P0 VULN: Control char filename '{repr(name)}' caused 500."
            )

    def test_upload_unicode_normalization_attack__P0(self, client):
        """SCORE: P0 — Unicode confusables: lookalike extension .pdf vs .рdf (Cyrillic 'r')."""
        pdf_bytes = make_pdf_bytes()
        # Cyrillic 'r' in .pdf extension
        evil_name = "test.рdf"  # U+0440 Cyrillic small ER instead of U+0070 'p'
        upload = SimpleUploadedFile(evil_name, pdf_bytes, content_type="application/pdf")
        response = client.post("/api/documents/upload/", {"file": upload})

        # Serializer should reject this as not a valid PDF/EPUB extension
        # because it checks .lower().endswith(".pdf") — Cyrillic р doesn't match
        response_data = response.json() if response.content else {}
        if response.status_code == 201:
            # It got through! Check it was actually saved
            doc = Document.objects.order_by("-id").first()
            # This is a P0 if it passes validation but the file_key contains
            # unicode that could confuse downstream systems
            assert doc.file_key, "No file_key"

    def test_upload_double_extension_attack__P0(self, client):
        """SCORE: P0 — double extension like test.pdf.exe should be handled."""
        # `filename.lower().endswith(".epub")` — "test.pdf.exe" ends with ".exe"
        # but "test.exe.pdf" ends with ".pdf". Let's test both.
        pdf_bytes = make_pdf_bytes()

        # Case 1: ends with .pdf, valid
        upload = SimpleUploadedFile("test.exe.pdf", pdf_bytes, content_type="application/pdf")
        response = client.post("/api/documents/upload/", {"file": upload})
        assert response.status_code != 500, f"P0: double ext .exe.pdf caused 500"

        # Case 2: ends with .exe, should be rejected
        upload2 = SimpleUploadedFile("test.pdf.exe", pdf_bytes, content_type="application/pdf")
        response2 = client.post("/api/documents/upload/", {"file": upload2})
        # Should reject because extension check fails
        assert response2.status_code in (400, 422), (
            f"P0 VULN: .exe extension passed validation, got {response2.status_code}"
        )


# =============================================================================
# P2 — WRONG BEHAVIOR TESTS
# =============================================================================

@pytest.mark.django_db
class TestDocumentUploadBehaviorP2:
    """Tests for incorrect behavior that doesn't crash but is wrong."""

    def test_non_pdf_uploaded_as_pdf__P2(self, client):
        """SCORE: P2 — Uploading an EPUB with .pdf extension — OCR will fail silently."""
        epub_bytes = make_epub_bytes()
        upload = SimpleUploadedFile("totally_not_epub.pdf", epub_bytes, content_type="application/pdf")
        response = client.post("/api/documents/upload/", {"file": upload})

        response_data = response.json() if response.content else {}
        # The serializer checks extension only, so .pdf passes.
        # Then OCR tries pdf2image on an EPUB — should error gracefully.
        if response.status_code == 201:
            doc = Document.objects.order_by("-id").first()
            assert doc.file_type == Document.FILE_TYPE_PDF, (
                f"P2: EPUB disguised as PDF was classified as {doc.file_type}"
            )
            assert doc.status == Document.STATUS_ERROR, (
                f"P2: EPUB-as-PDF should end in error state, got {doc.status}"
            )
            assert doc.error_message, (
                f"P2: No error_message set for failed OCR of EPUB-as-PDF"
            )

    def test_upload_creates_document_title_from_filename__P2(self, client):
        """SCORE: P2 — Title extraction: rsplit('.', 1)[0] on edge cases."""
        pdf_bytes = make_pdf_bytes()

        edge_cases = {
            "no_extension": "no_extension",  # No extension in name
            "...": "..",  # Triple dot
            ".hidden.pdf": ".hidden",  # Leading dot
            "my.file.name.pdf": "my.file.name",
        }

        for filename, expected_title in edge_cases.items():
            upload = SimpleUploadedFile(filename, pdf_bytes, content_type="application/pdf")
            response = client.post("/api/documents/upload/", {"file": upload})
            if response.status_code == 201:
                response_data = response.json()
                doc = Document.objects.get(id=response_data["id"])
                # Just document that this is what happens — it's P2 because
                # title sanitization from filename is weak
                print(f"  Filename: '{filename}' -> Title: '{doc.title}'")
                assert doc.title, f"P2: Empty title extracted from '{filename}'"

    def test_upload_max_valid_size__P2(self, client):
        """SCORE: P2 — File right at 50MB boundary should work or give clear error."""
        # We can't easily create a 50MB valid PDF, but we can check
        # that the size validation works at the boundary
        pdf_bytes = make_pdf_bytes()
        upload = SimpleUploadedFile("boundary.pdf", pdf_bytes, content_type="application/pdf")
        # Mock the size to be exactly at limit
        upload.size = 50 * 1024 * 1024  # 50MB exactly
        response = client.post("/api/documents/upload/", {"file": upload})

        # The serializer validator uses `value.size > 50*1024*1024`
        # So exactly 50MB should pass
        response_data = response.json() if response.content else {}
        if response.status_code == 400:
            # If rejected, error should be about size
            assert "size" in str(response_data).lower() or "50" in str(response_data), (
                f"P2: Rejected 50MB file without clear reason: {response_data}"
            )

    def test_upload_sets_correct_file_type_epub__P2(self, client):
        """SCORE: P2 — EPUB upload should set file_type correctly."""
        epub_bytes = make_epub_bytes()
        upload = SimpleUploadedFile("book.epub", epub_bytes, content_type="application/epub+zip")
        response = client.post("/api/documents/upload/", {"file": upload})

        if response.status_code == 201:
            response_data = response.json()
            doc = Document.objects.get(id=response_data["id"])
            assert doc.file_type == Document.FILE_TYPE_EPUB, (
                f"P2: EPUB upload got file_type={doc.file_type}, expected {Document.FILE_TYPE_EPUB}"
            )


# =============================================================================
# P3 — UX / ERROR HANDLING TESTS
# =============================================================================

@pytest.mark.django_db
class TestDocumentUploadUXP3:
    """Tests for poor UX and error handling."""

    def test_upload_no_file_field__P3(self, client):
        """SCORE: P3 — POST without file field should give clear error."""
        response = client.post("/api/documents/upload/", {})
        assert response.status_code in (400, 422), (
            f"P3: Missing file field returned {response.status_code}"
        )
        response_data = response.json() if response.content else {}
        # Error should be understandable
        assert response_data, "P3: Empty response body for missing file error"

    def test_upload_wrong_content_type__P3(self, client):
        """SCORE: P3 — Uploading a text file with .pdf extension."""
        txt = b"This is not a PDF file at all, just plain text."
        upload = SimpleUploadedFile("notes.pdf", txt, content_type="text/plain")
        response = client.post("/api/documents/upload/", {"file": upload})

        # Shouldn't 500
        assert response.status_code != 500, f"P3: Non-PDF content caused 500"

    def test_upload_no_extension__P3(self, client):
        """SCORE: P3 — File with no extension should be rejected clearly."""
        pdf_bytes = make_pdf_bytes()
        upload = SimpleUploadedFile("just_a_file", pdf_bytes, content_type="application/pdf")
        response = client.post("/api/documents/upload/", {"file": upload})

        # Serializer should reject — extension check fails
        assert response.status_code == 400, (
            f"P3: No-extension file should be rejected. Got {response.status_code}"
        )

    def test_upload_filename_very_long__P3(self, client):
        """SCORE: P3 — Extremely long filename (1000+ chars)."""
        pdf_bytes = make_pdf_bytes()
        long_name = "a" * 1000 + ".pdf"
        upload = SimpleUploadedFile(long_name, pdf_bytes, content_type="application/pdf")
        response = client.post("/api/documents/upload/", {"file": upload})

        # Should not 500. Either accept (OS/filesystem handles) or reject.
        assert response.status_code != 500, (
            f"P3: 1000-char filename caused 500 crash"
        )
