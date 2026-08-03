"""
RED TEAM: EPUB Extraction Backend Adversarial Tests.

Tests config/backends/epub.py — 0% coverage.

P0 = crash/security | P1 = data loss | P2 = wrong behavior | P3 = UX/error handling
"""

import io
import os
import tempfile
import zipfile
import struct

import pytest
from django.conf import settings


def create_epub_file(chapters=None, mimetype="application/epub+zip", extra_files=None):
    """Create an EPUB (ZIP) in a temp file, return the path.

    chapters: list of (filename, content) tuples for XHTML chapters
    extra_files: list of (filename, content) tuples for other files
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".epub", delete=False)
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('mimetype', mimetype)
        zf.writestr(
            'META-INF/container.xml',
            '<?xml version="1.0"?><container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>'
        )

        # Build manifest and spine from chapters
        manifest_items = []
        spine_items = []
        for i, (name, content) in enumerate(chapters or []):
            item_id = f"ch{i}"
            manifest_items.append(
                f'<item id="{item_id}" href="{name}" media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'<itemref idref="{item_id}"/>')
            zf.writestr(name, content)

        zf.writestr(
            'content.opf',
            '<?xml version="1.0"?><package version="2.0" xmlns="http://www.idpf.org/2007/opf">'
            '<metadata><dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">Test EPUB</dc:title></metadata>'
            f'<manifest>{"".join(manifest_items)}</manifest>'
            f'<spine>{"".join(spine_items)}</spine></package>'
        )

        if extra_files:
            for name, content in extra_files:
                zf.writestr(name, content)

    return tmp.name


def make_chapter_xhtml(title, body_text, paragraph_count=3):
    """Create a valid XHTML chapter with given body text."""
    paragraphs = "".join(f"<p>{body_text}</p>" for _ in range(paragraph_count))
    return (
        f'<html xmlns="http://www.w3.org/1999/xhtml">'
        f'<head><title>{title}</title></head>'
        f'<body><h1>{title}</h1>{paragraphs}</body></html>'
    )


# ── FIXTURES ──

@pytest.fixture
def valid_epub_path():
    """Create a valid EPUB with 2 chapters, return path."""
    chapters = [
        ("ch1.xhtml", make_chapter_xhtml(
            "Introduction",
            "This is the introduction chapter with substantial text content that exceeds "
            "the 100 character minimum threshold required for chapter extraction in the "
            "EPUB backend. We need to make sure there is enough text here for it to work.",
            paragraph_count=2
        )),
        ("ch2.xhtml", make_chapter_xhtml(
            "Main Content",
            "The main content chapter also needs substantial text. The EPUB backend "
            "requires at least 100 characters per chapter to include it. This chapter "
            "has more than enough text to pass that threshold without any issues.",
            paragraph_count=3
        )),
    ]
    return create_epub_file(chapters=chapters)


# =============================================================================
# P0 — SECURITY / CRASH TESTS
# =============================================================================

class TestEPUBExtractionP0:
    """Tests that target crash and security vulnerabilities in EPUB backend."""

    def test_zip_bomb__P0(self):
        """SCORE: P0 — Zip bomb with massive uncompressed size should be caught.

        The code checks `sum(info.file_size for info in zf.infolist())` against
        MAX_UNCOMPRESSED_SIZE (100MB). A zip bomb with high compression ratio
        should be rejected before decompressing.
        """
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".epub", delete=False)
        # Create a valid EPUB with a small chapter, then add extra entries
        # with inflated uncompressed sizes by patching the ZIP central directory
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zf:
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
                '<metadata><dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">Bomb</dc:title></metadata>'
                '<manifest><item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/></manifest>'
                '<spine><itemref idref="ch1"/></spine></package>'
            )
            zf.writestr(
                'ch1.xhtml',
                make_chapter_xhtml("Real Chapter", "Valid content " * 20, paragraph_count=3)
            )
            # Add payload entries with tiny compressed data
            huge_data = b"x" * 100
            for i in range(5):
                info = zipfile.ZipInfo(f"payload{i}.bin")
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, huge_data)

        # Post-process: patch central directory to inflate uncompressed sizes
        with open(tmp.name, 'r+b') as f:
            data = bytearray(f.read())
            # Find all central directory entries (PK\01\02 signature)
            signature = b'PK\x01\x02'
            pos = 0
            patched = 0
            while True:
                pos = data.find(signature, pos)
                if pos < 0:
                    break
                filename_len = struct.unpack('<H', data[pos+28:pos+30])[0]
                filename = data[pos+46:pos+46+filename_len].decode('latin-1')
                if filename.startswith('payload'):
                    # Set uncompressed size to 50MB (offset 24, 4 bytes LE)
                    struct.pack_into('<I', data, pos + 24, 50 * 1024 * 1024)
                    # Also update compressed size to match (avoid inconsistency)
                    struct.pack_into('<I', data, pos + 20, 50 * 1024 * 1024)
                    patched += 1
                # Move to next entry
                extra_len = struct.unpack('<H', data[pos+30:pos+32])[0]
                comment_len = struct.unpack('<H', data[pos+32:pos+34])[0]
                pos += 46 + filename_len + extra_len + comment_len
            f.seek(0)
            f.write(data)
            f.truncate()

        from config.backends import epub as epub_backend
        try:
            with pytest.raises(ValueError, match="uncompressed"):
                epub_backend.extract_text(tmp.name)
        finally:
            os.unlink(tmp.name)
            os.unlink(tmp.name) if os.path.exists(tmp.name) else None

    def test_empty_epub__P0(self):
        """SCORE: P0 — Empty EPUB (no chapters) should raise, not crash."""
        tmp = create_epub_file(chapters=[])  # No chapters
        from config.backends import epub as epub_backend
        try:
            with pytest.raises(ValueError, match="No readable text"):
                epub_backend.extract_text(tmp)
        finally:
            os.unlink(tmp)

    def test_corrupted_zip__P0(self):
        """SCORE: P0 — Corrupted ZIP file (random bytes) should be handled."""
        tmp = tempfile.NamedTemporaryFile(suffix=".epub", delete=False)
        tmp.write(b"this is not a zip file at all, just random garbage bytes")
        tmp.close()

        from config.backends import epub as epub_backend
        try:
            with pytest.raises(ValueError, match="Failed to read EPUB"):
                epub_backend.extract_text(tmp.name)
        finally:
            os.unlink(tmp.name)

    def test_drm_locked_epub__P0(self):
        """SCORE: P0 — EPUB with DRM-encrypted content shouldn't crash.

        DRM-locked EPUBs have encrypted content entries. ebooklib may still
        parse the structure but content will be encrypted bytes.
        """
        chapters = [
            ("ch1.xhtml", "This is encrypted content that ebooklib can't decode properly"),
        ]
        # Simulate DRM by using an encryption.xml in META-INF
        tmp = create_epub_file(
            chapters=chapters,
            extra_files=[
                ("META-INF/encryption.xml",
                 '<?xml version="1.0"?>'
                 '<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<EncryptedData><EncryptionMethod Algorithm="http://www.w3.org/2001/04/xmlenc#aes256-cbc"/>'
                 '<CipherData><CipherReference URI="ch1.xhtml"/></CipherData></EncryptedData>'
                 '</encryption>'),
                ("META-INF/rights.xml",
                 '<rights xmlns="http://www.idpf.org/2007/ Epub">DRM content</rights>'),
            ]
        )

        from config.backends import epub as epub_backend
        try:
            # Should handle gracefully — either extract what it can or raise
            result = epub_backend.extract_text(tmp)
            # If it succeeds, text should be minimal or empty
            assert isinstance(result, dict)
        except ValueError as e:
            # Acceptable: raises about no readable text
            assert "No readable text" in str(e) or "Failed to read" in str(e)
        finally:
            os.unlink(tmp)

    def test_malformed_xml_in_chapter__P0(self):
        """SCORE: P0 — Malformed XML should not crash parsing.

        BeautifulSoup with html.parser is forgiving, but let's test edge cases.
        """
        chapters = [
            ("ch1.xhtml", make_chapter_xhtml("Good", "Valid content " * 30, paragraph_count=3)),
            ("ch2.xhtml", (
                '<html xmlns="http://www.w3.org/1999/xhtml">'
                '<head><title>Broken</title></head>'
                '<body><p>Valid start</p>'
                '<p><unclosed>Broken tag nesting <<<>>></p>'  # Malformed
                '<p>More text to reach 100 char minimum for chapter extraction through '
                'the EPUB backend which filters out short chapters that are typically '
                'table of contents or copyright pages</p>'
                '</body></html>'
            )),
        ]
        tmp = create_epub_file(chapters=chapters)

        from config.backends import epub as epub_backend
        try:
            result = epub_backend.extract_text(tmp)
            assert isinstance(result, dict)
            assert result["pages"] >= 1
            assert result["text"]
        finally:
            os.unlink(tmp)

    def test_non_utf8_encoding_in_chapter__P0(self):
        """SCORE: P0 — Chapter content with non-UTF-8 encoding."""
        # Create content with bytes that can't be decoded as UTF-8
        bad_bytes = b'\x80\x81\x82\xfe\xff\x00'
        # Use ISO-8859-1 encoding of the bad bytes
        bad_text = bad_bytes.decode('latin-1')

        chapters = [
            ("ch1.xhtml", (
                '<html xmlns="http://www.w3.org/1999/xhtml">'
                '<head><title>Encoding Test</title></head>'
                '<body><p>'
                + bad_text +
                '</p><p>Additional text padding to reach the hundred character minimum '
                'required by the EPUB extraction backend for chapter inclusion.</p>'
                '</body></html>'
            )),
        ]
        tmp = create_epub_file(chapters=chapters)
        # Corrupt the file so the content can't decode as utf-8
        with open(tmp, 'rb') as f:
            data = bytearray(f.read())
        # Find and corrupt the ch1.xhtml content
        idx = data.find(b'Encoding Test')
        if idx > 0:
            # Insert invalid UTF-8 bytes
            for offset in range(5):
                if idx + 50 + offset < len(data):
                    data[idx + 50 + offset] = 0xFF

        with open(tmp, 'wb') as f:
            f.write(data)

        from config.backends import epub as epub_backend
        try:
            result = epub_backend.extract_text(tmp)
            # Should handle via errors="replace" in decode
            assert isinstance(result, dict)
        except ValueError as e:
            # Also acceptable: raises about no readable text
            pass
        finally:
            os.unlink(tmp)

    def test_epub_with_no_xhtml_items__P0(self):
        """SCORE: P0 — EPUB zip without any ITEM_DOCUMENT type entries.

        The code only processes items with ebooklib.ITEM_DOCUMENT type.
        An EPUB with only images should raise ValueError.
        """
        tmp = tempfile.NamedTemporaryFile(suffix=".epub", delete=False)
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zf:
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
                '<metadata><dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">Image Only</dc:title></metadata>'
                '<manifest><item id="img1" href="cover.jpg" media-type="image/jpeg"/></manifest>'
                '<spine></spine></package>'
            )
            # Add a dummy image (not an XHTML document)
            zf.writestr('cover.jpg', b'\xff\xd8\xff\xe0\x00\x10JFIF')

        from config.backends import epub as epub_backend
        try:
            with pytest.raises(ValueError, match="No readable text"):
                epub_backend.extract_text(tmp.name)
        finally:
            os.unlink(tmp.name)

    def test_epub_with_massive_images_P0(self):
        """SCORE: P0 — EPUB with huge embedded images, actual text content is small.

        The uncompressed size check sums ALL file sizes. Large images could
        trigger the 100MB limit even though text extraction is fine.
        """
        chapters = [
            ("ch1.xhtml", make_chapter_xhtml(
                "With Images",
                "This chapter has text but also large images. " * 20,
                paragraph_count=3
            )),
        ]
        tmp = tempfile.NamedTemporaryFile(suffix=".epub", delete=False)
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zf:
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
                '<metadata><dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">Heavy</dc:title></metadata>'
                '<manifest>'
                '<item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>'
                '<item id="img1" href="big_image.jpg" media-type="image/jpeg"/>'
                '</manifest>'
                '<spine><itemref idref="ch1"/></spine></package>'
            )
            zf.writestr("ch1.xhtml", chapters[0][1])
            # Create a very large image entry (but compressible)
            big_img = b'\x00' * (2 * 1024 * 1024)  # 2MB of zeros — highly compressible
            zf.writestr("big_image.jpg", big_img)

        from config.backends import epub as epub_backend
        try:
            result = epub_backend.extract_text(tmp.name)
            assert isinstance(result, dict)
            assert result["pages"] >= 1
        except ValueError as e:
            # Might trigger size limit if image pushes total over 100MB
            assert "uncompressed" in str(e).lower() or "No readable" in str(e)
        finally:
            os.unlink(tmp.name)


# =============================================================================
# P1 — DATA LOSS / CORRUPTION
# =============================================================================

class TestEPUBExtractionP1:
    """Tests for data loss or corruption."""

    def test_short_chapters_dropped__P1(self):
        """SCORE: P1 — Chapters under 100 chars are silently dropped.

        This is by design in the code (`len(cleaned) > 100`), but means
        content like chapter titles, poems, or short sections are lost.
        """
        short_chapter = make_chapter_xhtml("Short", "Tiny.", paragraph_count=1)
        long_chapter = make_chapter_xhtml(
            "Long",
            "This chapter is long enough to pass the threshold. " * 15,
            paragraph_count=3
        )

        chapters = [("ch1.xhtml", short_chapter), ("ch2.xhtml", long_chapter)]
        tmp = create_epub_file(chapters=chapters)

        from config.backends import epub as epub_backend
        try:
            result = epub_backend.extract_text(tmp)
            assert result["pages"] == 1, (
                f"P1: Short chapter dropped, but pages should still show as 1 "
                f"(got {result['pages']}). The short chapter content is lost."
            )
        finally:
            os.unlink(tmp)


# =============================================================================
# P2 — WRONG BEHAVIOR
# =============================================================================

class TestEPUBExtractionP2:
    """Tests for incorrect behavior."""

    def test_valid_epub_extraction__P2(self, valid_epub_path):
        """SCORE: P2 — Baseline: valid EPUB should extract correctly."""
        from config.backends import epub as epub_backend
        result = epub_backend.extract_text(valid_epub_path)
        assert result["pages"] == 2, f"Expected 2 chapters, got {result['pages']}"
        assert result["word_count"] > 0
        assert "Chapter 1" in result["text"]
        assert "Chapter 2" in result["text"]
        os.unlink(valid_epub_path)

    def test_chapter_with_scripts_and_styles_stripped__P2(self):
        """SCORE: P2 — Script/style/nav/header/footer tags should be stripped."""
        chapters = [
            ("ch1.xhtml", (
                '<html xmlns="http://www.w3.org/1999/xhtml">'
                '<head>'
                '<title>Test</title>'
                '<style>body { color: red; }</style>'
                '<script>alert("xss")</script>'
                '</head>'
                '<body>'
                '<nav>Skip this nav</nav>'
                '<header>Skip header</header>'
                '<footer>Skip footer</footer>'
                '<p>This is real content that should remain after stripping '
                'all the script tags style tags nav tags header tags and footer '
                'tags. We need enough text to pass the hundred character minimum.</p>'
                '</body></html>'
            )),
        ]
        tmp = create_epub_file(chapters=chapters)

        from config.backends import epub as epub_backend
        try:
            result = epub_backend.extract_text(tmp)
            text = result["text"]
            assert "alert" not in text, "P2: Script content not stripped"
            assert "body { color" not in text, "P2: Style content not stripped"
            assert "real content" in text, "P2: Real content was lost"
        finally:
            os.unlink(tmp)


# =============================================================================
# P3 — UX / ERROR HANDLING
# =============================================================================

class TestEPUBExtractionP3:
    """Tests for UX and error message quality."""

    def test_error_message_descriptive__P3(self):
        """SCORE: P3 — Error messages should be descriptive, not raw exceptions."""
        tmp = create_epub_file(chapters=[])  # empty, no chapters
        from config.backends import epub as epub_backend
        try:
            with pytest.raises(ValueError) as exc:
                epub_backend.extract_text(tmp)
            msg = str(exc.value)
            assert len(msg) > 0
            # Should not be a raw Python traceback
            assert "Traceback" not in msg, "P3: Raw traceback in error message"
        finally:
            os.unlink(tmp)

    def test_bare_minimum_epub__P3(self):
        """SCORE: P3 — EPUB with exactly one chapter at exactly 100 chars boundary."""
        # Build text that's comfortably above 100 chars after cleaning
        base = "x" * 105  # 105 chars, more than the 100-char threshold
        # The chapter heading "Test" becomes 4 chars plus whitespace
        content = make_chapter_xhtml("Test", base, paragraph_count=1)
        chapters = [("ch1.xhtml", content)]
        tmp = create_epub_file(chapters=chapters)

        from config.backends import epub as epub_backend
        try:
            result = epub_backend.extract_text(tmp)
            # Just check it doesn't crash on boundary
            assert isinstance(result, dict)
        finally:
            os.unlink(tmp)
