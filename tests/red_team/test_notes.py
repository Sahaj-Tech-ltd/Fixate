"""
RED TEAM: Notes/Sticky Notes Adversarial Tests.

Tests Note model and CRUD APIs at /api/reader/notes/
URLs: notes/ (GET list, POST create), notes/<id>/ (GET, PATCH, DELETE)

P0 = crash/security | P1 = data loss | P2 = wrong behavior | P3 = UX/error handling
"""

import json
import pytest
from django.test import Client

from apps.reader.models import Note
from apps.users.models import User


@pytest.fixture
def user(db):
    return User.objects.create(email="notes_redteam@test.com")


@pytest.fixture
def client(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def auth_headers():
    """JSON content type header."""
    return {"content_type": "application/json"}


# =============================================================================
# P0 — SECURITY / CRASH TESTS
# =============================================================================

@pytest.mark.django_db
class TestNotesP0:
    """Security and crash tests for notes."""

    def test_xss_in_note_body__P0(self, client):
        """SCORE: P0 — XSS payload in note body should be stored but the API
        should be neutral (it's the template's job to escape).

        This tests that the API doesn't crash or strip content unexpectedly.
        """
        payloads = [
            '<script>alert("XSS")</script>',
            '<img src=x onerror=alert(1)>',
            '<svg/onload=alert(1)>',
            '"><script>alert(document.cookie)</script>',
            '<a href="javascript:alert(1)">click</a>',
            '<iframe src="evil.com"></iframe>',
            '<style>body{display:none}</style>',
        ]

        stored_ids = []
        for i, payload in enumerate(payloads):
            response = client.post(
                "/api/reader/notes/",
                {"title": f"XSS Test {i}", "body": payload},
                content_type="application/json",
            )
            assert response.status_code == 201, (
                f"P0: XSS payload #{i} caused creation failure: {response.status_code}"
            )
            data = response.json()
            stored_ids.append(data["id"])

            # Verify the content is stored as-is (not stripped by API)
            note = Note.objects.get(id=data["id"])
            assert note.body == payload, (
                f"P0: XSS payload was modified during storage:\n"
                f"  Sent: {payload}\n"
                f"  Got:  {note.body}"
            )

        # Cleanup
        Note.objects.filter(id__in=stored_ids).delete()

    def test_extremely_long_note_body__P0(self, client):
        """SCORE: P0 — Extremely long note body should not crash or cause OOM.

        Note.body is TextField (no max_length). Test with 100KB of text.
        """
        long_text = "A" * 100_000
        response = client.post(
            "/api/reader/notes/",
            {"title": "Long Note", "body": long_text},
            content_type="application/json",
        )
        assert response.status_code != 500, (
            f"P0: 100KB note body caused 500"
        )
        if response.status_code == 201:
            note = Note.objects.get(id=response.json()["id"])
            assert len(note.body) == 100_000, (
                f"P0: Long body truncated: {len(note.body)} != 100000"
            )
            note.delete()

    def test_null_bytes_in_note_content__P0(self, client):
        """SCORE: P0 — Null bytes in title/body should not cause DB corruption."""
        null_title = "test\x00title"
        null_body = "body\x00with\x00nulls"

        response = client.post(
            "/api/reader/notes/",
            {"title": null_title, "body": null_body},
            content_type="application/json",
        )
        # JSON shouldn't allow null bytes, but if it gets through...
        assert response.status_code != 500, f"P0: Null bytes caused 500"

    def test_note_title_max_length__P0(self, client):
        """SCORE: P0 — Title beyond CharField max_length=200 should be rejected cleanly."""
        long_title = "T" * 250
        response = client.post(
            "/api/reader/notes/",
            {"title": long_title, "body": "test"},
            content_type="application/json",
        )
        assert response.status_code == 400, (
            f"P0: 250-char title accepted (max 200). Got {response.status_code}"
        )

    def test_create_note_with_invalid_color__P0(self, client):
        """SCORE: P0 — Invalid color value should be rejected."""
        response = client.post(
            "/api/reader/notes/",
            {"title": "Bad Color", "body": "test", "color": "invisible"},
            content_type="application/json",
        )
        assert response.status_code == 400, (
            f"P0: Invalid color value accepted. Got {response.status_code}"
        )

    def test_create_note_with_invalid_json__P0(self, client):
        """SCORE: P0 — Malformed JSON in body should not crash."""
        response = client.post(
            "/api/reader/notes/",
            "this is not json {{{",
            content_type="application/json",
        )
        assert response.status_code != 500, (
            f"P0: Malformed JSON caused 500"
        )
        assert response.status_code in (400, 415), (
            f"P0: Expected 400/415 for malformed JSON, got {response.status_code}"
        )

    def test_update_nonexistent_note__P0(self, client):
        """SCORE: P0 — PATCH non-existent note should 404, not 500."""
        response = client.patch(
            "/api/reader/notes/99999/",
            {"body": "updated"},
            content_type="application/json",
        )
        assert response.status_code == 404, (
            f"P0: Non-existent note PATCH returned {response.status_code}, expected 404"
        )

    def test_delete_nonexistent_note__P0(self, client):
        """SCORE: P0 — DELETE non-existent note should 404."""
        response = client.delete("/api/reader/notes/99999/")
        assert response.status_code == 404, (
            f"P0: Non-existent note DELETE returned {response.status_code}"
        )

    def test_unauthenticated_note_access__P0(self):
        """SCORE: P0 — Desktop mode auto-authenticates; verify no crashes."""
        anon = Client()
        for url in ["/api/reader/notes/", "/api/reader/notes/1/"]:
            response = anon.get(url)
            assert response.status_code != 500, (
                f"P0: Unauthenticated GET {url} caused 500"
            )

            response = anon.post(url, {}, content_type="application/json")
            assert response.status_code != 500, (
                f"P0: Unauthenticated POST {url} caused 500"
            )

    def test_other_users_note_not_accessible__P0(self, client, user):
        """SCORE: P0 — Cannot access another user's note."""
        other = User.objects.create(email="note_thief@test.com")
        note = Note.objects.create(user=other, title="Mine", body="Secret")

        response = client.get(f"/api/reader/notes/{note.id}/")
        assert response.status_code == 404, (
            f"P0 VULN: Accessed another user's note!"
        )

        response = client.patch(
            f"/api/reader/notes/{note.id}/",
            {"body": "stolen"},
            content_type="application/json",
        )
        assert response.status_code == 404, (
            f"P0 VULN: Modified another user's note!"
        )

    def test_emoji_in_note_content__P0(self, client):
        """SCORE: P0 — Emoji in title and body should not crash."""
        response = client.post(
            "/api/reader/notes/",
            {"title": "📝✨ Note with Emoji 🎉", "body": "Content: 🚀🔥💯"},
            content_type="application/json",
        )
        assert response.status_code == 201, f"P0: Emoji note creation failed with {response.status_code}"
        data = response.json()
        assert "📝" in data["title"], "P0: Emoji stripped from title"
        note = Note.objects.get(id=data["id"])
        note.delete()

    def test_empty_note_create__P0(self, client):
        """SCORE: P0 — Creating a note with absolutely no content should work or error clearly."""
        response = client.post(
            "/api/reader/notes/",
            {"title": "", "body": ""},
            content_type="application/json",
        )
        # Note model allows blank title and body
        assert response.status_code != 500, f"P0: Empty note caused 500"
        if response.status_code == 201:
            note = Note.objects.get(id=response.json()["id"])
            note.delete()


# =============================================================================
# P2 — WRONG BEHAVIOR TESTS
# =============================================================================

@pytest.mark.django_db
class TestNotesP2:
    """Tests for incorrect behavior."""

    def test_note_list_filters_archived__P2(self, client, user):
        """SCORE: P2 — GET /notes/ should only show non-archived by default."""
        active = Note.objects.create(user=user, title="Active", body="show")
        archived = Note.objects.create(user=user, title="Archived", body="hide", is_archived=True)

        response = client.get("/api/reader/notes/")
        assert response.status_code == 200
        data = response.json()
        note_ids = [n["id"] for n in data]

        assert active.id in note_ids, "P2: Active note missing from list"
        assert archived.id not in note_ids, "P2: Archived note shown in default list"

        # Get archived notes
        response = client.get("/api/reader/notes/?archived=1")
        data = response.json()
        note_ids = [n["id"] for n in data]
        assert archived.id in note_ids, "P2: Archived note missing when ?archived=1"

        active.delete()
        archived.delete()

    def test_note_update_preserves_fields__P2(self, client, user):
        """SCORE: P2 — Patching one field shouldn't wipe others."""
        note = Note.objects.create(
            user=user, title="Original Title", body="Original Body", color=Note.COLOR_BLUE
        )
        response = client.patch(
            f"/api/reader/notes/{note.id}/",
            {"body": "Updated Body"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Original Title", "P2: Title was wiped during partial update"
        assert data["body"] == "Updated Body"
        assert data["color"] == Note.COLOR_BLUE, "P2: Color was wiped during partial update"

        note.delete()

    def test_note_delete_actually_deletes__P2(self, client, user):
        """SCORE: P2 — Deleting a note removes it from DB."""
        note = Note.objects.create(user=user, title="To Delete")
        response = client.delete(f"/api/reader/notes/{note.id}/")
        assert response.status_code == 204
        assert not Note.objects.filter(id=note.id).exists(), "P2: Note not deleted from DB"


# =============================================================================
# P3 — UX TESTS
# =============================================================================

@pytest.mark.django_db
class TestNotesP3:
    """UX and error handling quality tests."""

    def test_created_note_has_default_color__P3(self, client):
        """SCORE: P3 — Notes should get default color if not specified."""
        response = client.post(
            "/api/reader/notes/",
            {"title": "Default", "body": "test"},
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["color"] == Note.COLOR_DEFAULT, (
            f"P3: Unexpected default color: {data['color']}"
        )
        note = Note.objects.get(id=data["id"])
        note.delete()

    def test_created_note_has_color_hex__P3(self, client):
        """SCORE: P3 — Response should include color_hex for UI rendering."""
        response = client.post(
            "/api/reader/notes/",
            {"title": "Colored", "body": "test", "color": Note.COLOR_YELLOW},
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.json()
        assert "color_hex" in data, "P3: color_hex missing"
        assert data["color_hex"] == Note.COLOR_HEX[Note.COLOR_YELLOW], (
            f"P3: Wrong color_hex: {data['color_hex']}"
        )
        note = Note.objects.get(id=data["id"])
        note.delete()

    def test_unicode_body_not_corrupted__P3(self, client):
        """SCORE: P3 — Unicode text in note body should roundtrip correctly."""
        unicode_text = (
            "日本語测试한국어العربيةрусский язык\n"
            "Emoji: 🎉🎊🎈🎁\n"
            "Math: ∑∫∂√∞\n"
            "RTL: مرحبا بكم"
        )
        response = client.post(
            "/api/reader/notes/",
            {"title": "Unicode Test", "body": unicode_text},
            content_type="application/json",
        )
        assert response.status_code == 201
        note = Note.objects.get(id=response.json()["id"])
        assert note.body == unicode_text, "P3: Unicode text corrupted in roundtrip"
        note.delete()
