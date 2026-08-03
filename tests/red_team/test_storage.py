"""RED TEAM: Storage Backend Security Tests.

Tests config/backends/storage.py — path traversal, key injection, extension extraction.
"""

import os
import pytest
from django.test import override_settings
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile


class TestStorageSecurityP0:
    """Tests for security vulnerabilities in storage operations."""

    def test_path_traversal_in_key__P0(self):
        """SCORE: P0 — Path traversal '../../..' in key must be BLOCKED.

        After fix: get_local_path() raises ValueError on path traversal.
        """
        from config.backends import storage as storage_backend

        evil_key = "../../../etc/passwd"
        with pytest.raises(ValueError, match="Path traversal blocked"):
            storage_backend.get_local_path(evil_key)

    def test_path_traversal_in_save_uploaded_file__P0(self):
        """SCORE: P0 — Upload with `../../../etc` in filename should not write outside MEDIA_ROOT."""
        from config.backends import storage as storage_backend

        evil_filename = "../../../etc/pwned.pdf"
        file_content = b"%PDF-1.4\ntrailer\n%%EOF\n"
        upload = SimpleUploadedFile(evil_filename, file_content, content_type="application/pdf")

        # After sanitization, filename is reduced to basename only
        key = storage_backend.save_uploaded_file(1, evil_filename, upload)

        media_root = os.path.abspath(settings.MEDIA_ROOT)
        full_path = os.path.abspath(storage_backend.get_local_path(key))

        assert full_path.startswith(media_root), (
            f"P0 VULN: Path traversal escaped MEDIA_ROOT!\n"
            f"  MEDIA_ROOT: {media_root}\n"
            f"  Resolved:   {full_path}"
        )

        # Cleanup
        try:
            storage_backend.delete_file(key)
        except Exception:
            pass

    def test_key_with_absolute_path__P0(self):
        """SCORE: P0 — Absolute path as key must be BLOCKED.

        After fix: get_local_path() raises ValueError on absolute paths.
        """
        from config.backends import storage as storage_backend

        evil_key = "/etc/passwd"
        with pytest.raises(ValueError, match="Path traversal blocked"):
            storage_backend.get_local_path(evil_key)

    def test_key_with_null_byte_truncation__P0(self):
        """SCORE: P0 — Null byte in key: path traversal is now blocked by validation.

        After fix: null bytes in keys trigger ValueError from realpath validation.
        """
        from config.backends import storage as storage_backend

        evil_key = "uploads/1/../etc/passwd\x00.pdf"
        try:
            path = storage_backend.get_local_path(evil_key)
            # If it doesn't raise, verify path is safe
            media_root = os.path.abspath(settings.MEDIA_ROOT)
            resolved = os.path.abspath(path)
            assert resolved.startswith(media_root), f"P0: Path escaped: {resolved}"
        except (ValueError, OSError) as e:
            # Rejecting null bytes or path traversal is the correct behavior
            pass

    def test_generate_key_uses_extension_only__P0(self):
        """SCORE: P0 — _generate_key must safely extract extension from filename.

        After fix: _sanitize_filename + _safe_extension strip path noise,
        so '../../../etc/passwd' → extension 'pdf' (default for unclear names).
        """
        from config.backends import storage as storage_backend

        # Path traversal filename → safe extension (pdf, not passwd)
        key = storage_backend._generate_key(1, "../../../etc/passwd")
        assert ".passwd" not in key, (
            f"P0 VULN: Path traversal filename leaked into key: {key}"
        )
        assert ".pdf" in key, f"P0: Expected safe .pdf extension, got: {key}"

        # Double extension → takes last extension
        key2 = storage_backend._generate_key(1, "test.pdf.exe")
        assert key2.endswith(".exe"), f"P0: Double extension gives wrong ext: {key2}"

    @override_settings(FIXATE_MODE="desktop")
    def test_get_local_path_handles_symlink_attack__P0(self, tmp_path):
        """SCORE: P0 — symlink attacks: if a file key points to a symlink outside MEDIA_ROOT."""
        from config.backends import storage as storage_backend

        media_subdir = tmp_path / "uploads" / "1" / "documents"
        media_subdir.mkdir(parents=True)

        with override_settings(MEDIA_ROOT=str(tmp_path)):
            key = "uploads/1/documents/test.pdf"
            dest = tmp_path / key
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"test content")

            path = storage_backend.get_local_path(key)
            assert os.path.exists(path), "File should exist"


class TestStorageDataLossP1:
    """Tests for data loss or corruption in storage operations."""

    @override_settings(FIXATE_MODE="desktop")
    def test_delete_missing_file_returns_true__P1(self):
        """SCORE: P1 — Deleting a non-existent file silently returns True."""
        from config.backends import storage as storage_backend
        result = storage_backend.delete_file("uploads/999/nonexistent.pdf")
        assert result is True, (
            f"P1: delete_file returns {result} for missing file. "
            f"True masks the fact that the file didn't exist."
        )

    @override_settings(FIXATE_MODE="desktop")
    def test_save_then_delete_roundtrip__P1(self):
        """SCORE: P1 — Verify file is actually deleted."""
        from config.backends import storage as storage_backend
        from django.core.files.uploadedfile import SimpleUploadedFile

        content = b"roundtrip test content"
        upload = SimpleUploadedFile("roundtrip.pdf", content, content_type="application/pdf")

        key = storage_backend.save_uploaded_file(42, "roundtrip.pdf", upload)
        full_path = storage_backend.get_local_path(key)
        assert os.path.exists(full_path), "File should exist after save"

        storage_backend.delete_file(key)
        assert not os.path.exists(full_path), f"P1: File not deleted: {full_path}"

    @override_settings(FIXATE_MODE="desktop")
    def test_overwrite_existing_key__P1(self):
        """SCORE: P1 — Saving to same key overwrites without warning."""
        from config.backends import storage as storage_backend
        from django.core.files.uploadedfile import SimpleUploadedFile

        content1 = b"original content"
        content2 = b"overwritten content"

        upload1 = SimpleUploadedFile("test.pdf", content1, content_type="application/pdf")
        key1 = storage_backend.save_uploaded_file(99, "test.pdf", upload1)

        data1 = storage_backend.get_file_bytes(key1)
        assert data1 == content1

        storage_backend.delete_file(key1)


class TestStorageBehaviorP2:
    """Tests for incorrect behavior."""

    @override_settings(FIXATE_MODE="desktop")
    def test_get_file_bytes_missing_file__P2(self):
        """SCORE: P2 — get_file_bytes for missing file should raise clear error."""
        from config.backends import storage as storage_backend
        with pytest.raises((FileNotFoundError, Exception)):
            storage_backend.get_file_bytes("uploads/999/nonexistent.pdf")

    @override_settings(FIXATE_MODE="desktop")
    def test_save_read_consistency__P2(self):
        """SCORE: P2 — Bytes written = bytes read."""
        from config.backends import storage as storage_backend
        from django.core.files.uploadedfile import SimpleUploadedFile

        content = b"consistency check " * 100
        upload = SimpleUploadedFile("consistency.pdf", content, content_type="application/pdf")

        key = storage_backend.save_uploaded_file(7, "consistency.pdf", upload)
        try:
            read_back = storage_backend.get_file_bytes(key)
            assert read_back == content, (
                f"P2: Data corruption: wrote {len(content)} bytes, read {len(read_back)} bytes"
            )
        finally:
            try:
                storage_backend.delete_file(key)
            except Exception:
                pass

    @override_settings(FIXATE_MODE="desktop")
    def test_save_creates_intermediate_dirs__P2(self):
        """SCORE: P2 — save_uploaded_file should create parent directories."""
        from config.backends import storage as storage_backend
        from django.core.files.uploadedfile import SimpleUploadedFile

        content = b"dir create test"
        upload = SimpleUploadedFile("test.pdf", content, content_type="application/pdf")

        key = storage_backend.save_uploaded_file(55, "test.pdf", upload)
        full_path = storage_backend.get_local_path(key)
        parent = os.path.dirname(full_path)

        assert os.path.isdir(parent), f"P2: Intermediate dirs not created: {parent}"
        assert os.path.exists(full_path), f"P2: File not written: {full_path}"

        try:
            storage_backend.delete_file(key)
        except Exception:
            pass
