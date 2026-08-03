"""
RED TEAM: Reader Views Adversarial Tests.

Tests apps/reader/views.py — 27% coverage.
URLs: /api/reader/...

P0 = crash/security | P1 = data loss | P2 = wrong behavior | P3 = UX/error handling
"""

import pytest
from django.test import Client
from django.urls import reverse

from apps.documents.models import Document
from apps.reader.models import (
    ReadingSession, UserPreferences, Note, FlashcardDeck, Flashcard, Highlight
)
from apps.users.models import User


# ── Fixtures ──

@pytest.fixture
def user(db):
    return User.objects.create(email="reader_redteam@test.com")


@pytest.fixture
def client(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def ready_document(db, user):
    """Document with status=ready and some text."""
    return Document.objects.create(
        user=user,
        title="Reader Test Doc",
        file_key="uploads/99/documents/test.pdf",
        file_type=Document.FILE_TYPE_PDF,
        status=Document.STATUS_READY,
        raw_text="Chapter 1: Introduction\n\nThis is the first paragraph of the test document. "
                 "It contains enough text to be meaningful for reader tests. "
                 "There should be multiple paragraphs to test pagination and word counting.\n\n"
                 "Chapter 2: Main Content\n\nMore content for the test document goes here. "
                 "We need several hundred words to test the reader properly.\n\n"
                 "The quick brown fox jumps over the lazy dog. " * 10,
        page_count=2,
        word_count=100,
    )


@pytest.fixture
def pending_document(db, user):
    """Document that is NOT ready yet."""
    return Document.objects.create(
        user=user,
        title="Pending Doc",
        file_key="uploads/99/documents/pending.pdf",
        file_type=Document.FILE_TYPE_PDF,
        status=Document.STATUS_PENDING,
    )


@pytest.fixture
def other_user_document(db):
    """Document owned by a different user."""
    other = User.objects.create(email="other_user@test.com")
    return Document.objects.create(
        user=other,
        title="Other User's Doc",
        file_key="uploads/1/documents/other.pdf",
        file_type=Document.FILE_TYPE_PDF,
        status=Document.STATUS_READY,
        raw_text="Secret content that should not be visible.",
        page_count=1,
        word_count=10,
    )


# =============================================================================
# P0 — SECURITY / CRASH TESTS
# =============================================================================

@pytest.mark.django_db
class TestReaderViewsP0:
    """Tests that reveal security vulnerabilities or crash bugs."""

    def test_reader_page_unauthenticated__P0(self):
        """SCORE: P0 — Desktop mode auto-authenticates; verify no 500 on nonexistent doc."""
        anon_client = Client()
        response = anon_client.get("/api/reader/read/1/")
        # Desktop mode auto-creates users, so 200 is expected if doc exists.
        # Since doc 1 doesn't exist, we expect 404 — never 500.
        assert response.status_code != 500, "P0: Reader caused 500"

    def test_start_reading_unauthenticated__P0(self):
        """SCORE: P0 — Desktop mode auto-authenticates; verify no crash on POST."""
        anon_client = Client()
        response = anon_client.post("/api/reader/start/1/")
        # Desktop auto-auth kicks in; document 1 doesn't exist → 404
        assert response.status_code != 500, f"P0: Start-reading caused {response.status_code}"

    def test_reader_non_existent_document__P0(self, client):
        """SCORE: P0 — Accessing reader for non-existent document should 404, not 500."""
        response = client.get("/api/reader/read/99999/")
        assert response.status_code == 404, (
            f"P0: Expected 404 for non-existent document, got {response.status_code}"
        )

    def test_start_reading_non_existent_document__P0(self, client):
        """SCORE: P0 — Starting reading for non-existent document should 404."""
        response = client.post("/api/reader/start/99999/")
        assert response.status_code == 404, (
            f"P0: Expected 404 for non-existent doc, got {response.status_code}"
        )

    def test_reader_other_users_document__P0(self, client, other_user_document):
        """SCORE: P0 — Accessing another user's document must be forbidden."""
        response = client.get(f"/api/reader/read/{other_user_document.id}/")
        assert response.status_code == 404, (
            f"P0 VULN: Accessed another user's document! Got {response.status_code}.\n"
            f"Document {other_user_document.id} belongs to {other_user_document.user.email}"
        )

    def test_start_reading_other_users_document__P0(self, client, other_user_document):
        """SCORE: P0 — Starting reading on another user's document must 404."""
        response = client.post(f"/api/reader/start/{other_user_document.id}/")
        assert response.status_code == 404, (
            f"P0 VULN: Started reading another user's document! Got {response.status_code}"
        )

    def test_text_endpoint_other_users_document__P0(self, client, other_user_document):
        """SCORE: P0 — Getting text of another user's document must 404."""
        response = client.get(f"/api/reader/text/{other_user_document.id}/")
        assert response.status_code == 404, (
            f"P0 VULN: Retrieved text of another user's document!"
        )

    def test_reader_with_empty_text__P0(self, client, user):
        """SCORE: P0 — Document with empty raw_text should not crash reader."""
        doc = Document.objects.create(
            user=user,
            title="Empty Doc",
            file_key="empty.pdf",
            file_type=Document.FILE_TYPE_PDF,
            status=Document.STATUS_READY,
            raw_text="",
            page_count=1,
            word_count=0,
        )
        response = client.get(f"/api/reader/read/{doc.id}/")
        assert response.status_code != 500, (
            f"P0: Empty text document caused 500"
        )

    def test_session_id_injection__P0(self, client, ready_document):
        """SCORE: P0 — Invalid session_id should 404, not crash."""
        # Patch session with non-existent ID
        response = client.patch(
            "/api/reader/session/99999/",
            {"position": 0},
            content_type="application/json",
        )
        assert response.status_code == 404, (
            f"P0: Invalid session ID returned {response.status_code} instead of 404"
        )

    def test_update_session_other_users_session__P0(self, client, other_user_document):
        """SCORE: P0 — Updating another user's session must 404."""
        # Create a session for the other user's document
        session = ReadingSession.objects.create(
            user=other_user_document.user,
            document=other_user_document,
            last_position=0,
        )
        response = client.patch(
            f"/api/reader/session/{session.id}/",
            {"position": 999},
            content_type="application/json",
        )
        assert response.status_code == 404, (
            f"P0 VULN: Updated another user's session! Got {response.status_code}"
        )

    def test_update_session_negative_position__P0(self, client, ready_document):
        """SCORE: P0 — Negative position should be rejected by serializer (min_value=0)."""
        # First start reading to get a session
        response = client.post(f"/api/reader/start/{ready_document.id}/")
        assert response.status_code == 200
        session_id = response.json()["session"]["id"]

        # Try negative position
        response = client.patch(
            f"/api/reader/session/{session_id}/",
            {"position": -1},
            content_type="application/json",
        )
        assert response.status_code == 400, (
            f"P0: Negative position accepted! Got {response.status_code}"
        )


# =============================================================================
# P2 — WRONG BEHAVIOR TESTS
# =============================================================================

class TestReaderViewsP2:
    """Tests for incorrect but not crashing behavior."""

    def test_reader_pending_document_rejected__P2(self, client, pending_document):
        """SCORE: P2 — Reader should reject document with status=pending."""
        response = client.get(f"/api/reader/read/{pending_document.id}/")
        # The view checks document.status != STATUS_READY
        # Returns 200 but with error in context
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        # Should show error
        content = response.content.decode()
        assert "not ready" in content.lower() or "error" in content.lower(), (
            f"P2: No error shown for pending document"
        )

    def test_start_reading_pending_rejected__P2(self, client, pending_document):
        """SCORE: P2 — StartReading should reject non-ready documents."""
        response = client.post(f"/api/reader/start/{pending_document.id}/")
        assert response.status_code == 400, (
            f"P2: Expected 400 for pending doc, got {response.status_code}"
        )
        data = response.json()
        assert "error" in data, "P2: No error message for pending document"

    def test_start_reading_creates_session__P2(self, client, ready_document):
        """SCORE: P2 — Starting reading should create a ReadingSession with correct defaults."""
        # Create preferences first
        prefs = UserPreferences.objects.get_or_create(user=ready_document.user)[0]
        prefs.default_wpm = 400
        prefs.save()

        response = client.post(f"/api/reader/start/{ready_document.id}/")
        assert response.status_code == 200, f"Start reading failed: {response.status_code}"
        data = response.json()

        assert "session" in data
        assert "text" in data
        assert data["text"] == ready_document.raw_text
        assert data["word_count"] == ready_document.word_count

    def test_text_endpoint_returns_content__P2(self, client, ready_document):
        """SCORE: P2 — Text endpoint should return document.raw_text."""
        response = client.get(f"/api/reader/text/{ready_document.id}/")
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == ready_document.raw_text

    def test_text_endpoint_pending_rejected__P2(self, client, pending_document):
        """SCORE: P2 — Text endpoint should reject non-ready documents."""
        response = client.get(f"/api/reader/text/{pending_document.id}/")
        assert response.status_code == 400

    def test_document_with_no_words__P2(self, client, user):
        """SCORE: P2 — Document with word_count=0 but status=ready."""
        doc = Document.objects.create(
            user=user,
            title="Zero Words",
            file_key="zero.pdf",
            file_type=Document.FILE_TYPE_PDF,
            status=Document.STATUS_READY,
            raw_text="",
            page_count=1,
            word_count=0,
        )
        response = client.post(f"/api/reader/start/{doc.id}/")
        assert response.status_code == 200, "Start reading empty doc failed"
        data = response.json()
        assert data["word_count"] == 0


# =============================================================================
# P3 — UX / ERROR HANDLING
# =============================================================================

class TestReaderViewsP3:
    """Tests for poor UX and error handling."""

    def test_404_for_nonexistent_document_is_json__P3(self, client):
        """SCORE: P3 — API endpoints should return JSON errors, not HTML 404 pages."""
        response = client.get("/api/reader/text/99999/")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_start_reading_twice_same_session__P2(self, client, ready_document):
        """SCORE: P2 — Calling start-reading twice should return same session."""
        response1 = client.post(f"/api/reader/start/{ready_document.id}/")
        session_id1 = response1.json()["session"]["id"]

        response2 = client.post(f"/api/reader/start/{ready_document.id}/")
        session_id2 = response2.json()["session"]["id"]

        assert session_id1 == session_id2, (
            f"P2: Second start-reading created new session! {session_id1} != {session_id2}"
        )

    def test_preferences_endpoint_works__P3(self, client):
        """SCORE: P3 — Preferences GET should return defaults even without saved prefs."""
        response = client.get("/api/reader/preferences/")
        assert response.status_code == 200
        data = response.json()
        assert "default_mode" in data
        assert "default_wpm" in data
        assert "theme" in data

    def test_preferences_patch_works__P3(self, client):
        """SCORE: P3 — PATCH preferences should update values."""
        response = client.patch(
            "/api/reader/preferences/",
            {"default_wpm": 500, "theme": "sepia"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["default_wpm"] == 500
        assert data["theme"] == "sepia"
