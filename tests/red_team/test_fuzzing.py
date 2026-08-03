"""
Wave 11: Fuzzing — Unicode, null bytes, boundary conditions, type confusion.

Tests: 156 edge cases across all Fixate endpoints.
Findings documented inline with "FINDING:" prefix.
"""


import pytest
from django.core.cache import cache

@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Clear DRF throttle cache between tests to prevent isolation failures."""
    cache.clear()
import json
import pytest
from django.test import Client

from apps.reader.models import (
    ReadingSession, UserPreferences, Task, Note, CoworkRoom,
    RoomParticipant, ChatMessage, FlashcardDeck, Flashcard,
    UserXP, XPEvent, DailyReadingStat, Highlight,
)
from apps.documents.models import Document, Folder
from apps.users.models import User

# URL constants (direct paths, no reverse() to avoid FORCE_SCRIPT_NAME prefix issues)
URL_DOCUMENT_LIST = "/api/documents/"
URL_FOLDER_LIST = "/api/documents/folders/"
URL_PREFERENCES = "/api/reader/preferences/"
URL_TASK_LIST = "/api/reader/tasks/"
URL_NOTE_LIST = "/api/reader/notes/"
URL_ROOM_LIST = "/api/reader/rooms/"
URL_ROOM_JOIN = "/api/reader/rooms/join/"
URL_XP_EVENT = "/api/reader/xp/event/"
URL_STREAK = "/api/reader/streak/"
URL_USER_XP = "/api/reader/xp/"
URL_AUDIO_TRACKS = "/api/reader/tracks/"
URL_FLASHCARD_DECK_LIST = "/api/reader/flashcards/decks/"
URL_FLASHCARD_LIST = "/api/reader/flashcards/cards/"
URL_HIGHLIGHT_LIST = "/api/reader/highlights/"


def make_user(email="fuzz@example.com"):
    return User.objects.create(email=email, tier="pro")


def make_document(user, title="Test Doc", status=Document.STATUS_READY):
    return Document.objects.create(
        user=user, title=title, file_key="uploads/1/doc.pdf",
        file_type=Document.FILE_TYPE_PDF, status=status,
        raw_text="Hello world " * 100, word_count=200, page_count=1,
    )


def auth_client(user):
    c = Client()
    c.force_login(user)
    return c


# ─────────────────────────────────────────────────────────────
# 1. UNICODE ATTACKS
# ─────────────────────────────────────────────────────────────

class TestUnicodeAttacks:
    def test_rtlo_in_folder_name(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_FOLDER_LIST, data=json.dumps({"name": "Folder\u202Egpj.exe"}), content_type="application/json")
        assert resp.status_code in [200, 201]
        folder = Folder.objects.first()
        assert "\u202E" in folder.name

    def test_rtlo_in_note_title_and_body(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_NOTE_LIST, data=json.dumps({"title": "Note\u202Evtx", "body": "Body\u202Etext"}), content_type="application/json")
        assert resp.status_code in [200, 201]

    def test_rtlo_in_room_name(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_ROOM_LIST, data=json.dumps({"name": "Room\u202Evtx"}), content_type="application/json")
        assert resp.status_code in [200, 201]

    def test_zero_width_in_note_body(self, db):
        user = make_user()
        c = auth_client(user)
        zws = "Hello\u200BWorld\u200C\u200D\uFEFF"
        resp = c.post(URL_NOTE_LIST, data=json.dumps({"title": "ZWS Note", "body": zws}), content_type="application/json")
        assert resp.status_code in [200, 201]
        note = Note.objects.first()
        assert "\u200B" in note.body

    def test_homograph_in_folder_name(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_FOLDER_LIST, data=json.dumps({"name": "f\u0430ke_folder"}), content_type="application/json")
        assert resp.status_code in [200, 201]

    def test_homograph_in_search_query(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.get(URL_DOCUMENT_LIST, {"search": "d\u0430ta"})
        assert resp.status_code == 200

    def test_unicode_normalization_separate_folders(self, db):
        """FINDING: NFC and NFD are stored as separate folders — no normalization applied."""
        user = make_user()
        c = auth_client(user)
        resp1 = c.post(URL_FOLDER_LIST, data=json.dumps({"name": "caf\u00e9"}), content_type="application/json")
        resp2 = c.post(URL_FOLDER_LIST, data=json.dumps({"name": "cafe\u0301"}), content_type="application/json")
        assert resp1.status_code in [200, 201]
        assert resp2.status_code in [200, 201]
        assert Folder.objects.count() == 2  # Normalization not applied

    def test_emoji_in_notes(self, db):
        user = make_user()
        c = auth_client(user)
        emoji = "📚🎉🚀💻🔥"
        resp = c.post(URL_NOTE_LIST, data=json.dumps({"title": emoji, "body": emoji}), content_type="application/json")
        assert resp.status_code in [200, 201]

    def test_unicode_in_flashcard(self, db):
        user = make_user()
        c = auth_client(user)
        deck = FlashcardDeck.objects.create(user=user, name="Test")
        resp = c.post(URL_FLASHCARD_LIST, data=json.dumps({"deck": deck.id, "front": "日本語 한국어 Ελληνικά", "back": "test"}), content_type="application/json")
        assert resp.status_code in [200, 201]

    def test_unicode_in_highlight(self, db):
        user = make_user()
        c = auth_client(user)
        doc = make_document(user)
        resp = c.post(URL_HIGHLIGHT_LIST, data=json.dumps({
            "document_id": doc.id,
            "highlights": [{"text": "العربية 中文 🎉", "startIndex": 0, "color": "#fbbf24"}],
        }), content_type="application/json")
        assert resp.status_code in [200, 201]


# ─────────────────────────────────────────────────────────────
# 2. NULL BYTE INJECTION
# ─────────────────────────────────────────────────────────────

class TestNullByteInjection:
    def test_null_byte_in_folder_name_rejected_by_json_parser(self, db):
        """FINDING: Null bytes in JSON body are rejected by Django's JSON parser (400)."""
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_FOLDER_LIST, data=json.dumps({"name": "Test\x00Folder"}), content_type="application/json")
        assert resp.status_code == 400, "Null byte in JSON string rejected by parser"

    def test_null_byte_in_search_query(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.get(URL_DOCUMENT_LIST, {"search": "test\x00query"})
        assert resp.status_code == 200

    def test_null_byte_in_chat_message_model(self, db):
        """FINDING: Null byte can be stored directly via model (bypasses JSON parser)."""
        user = make_user()
        room = CoworkRoom.objects.create(name="Test", code="ABCDEF", created_by=user)
        msg = ChatMessage.objects.create(room=room, user=user, content="Hello\x00World")
        assert "\x00" in msg.content


# ─────────────────────────────────────────────────────────────
# 3. BOUNDARY CONDITIONS
# ─────────────────────────────────────────────────────────────

class TestBoundaryConditions:
    def test_empty_folder_name_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_FOLDER_LIST, data=json.dumps({"name": ""}), content_type="application/json")
        assert resp.status_code == 400

    def test_empty_task_title_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_TASK_LIST, data=json.dumps({"title": "", "status": "todo"}), content_type="application/json")
        assert resp.status_code == 400

    def test_empty_note_title_allowed(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_NOTE_LIST, data=json.dumps({"title": "", "body": "Content"}), content_type="application/json")
        assert resp.status_code in [200, 201]

    def test_folder_name_max_length(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_FOLDER_LIST, data=json.dumps({"name": "A" * 100}), content_type="application/json")
        assert resp.status_code in [200, 201]

    def test_folder_name_exceeds_max_length(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_FOLDER_LIST, data=json.dumps({"name": "A" * 101}), content_type="application/json")
        assert resp.status_code == 400

    def test_task_title_exceeds_max_length(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_TASK_LIST, data=json.dumps({"title": "A" * 201, "status": "todo"}), content_type="application/json")
        assert resp.status_code == 400

    def test_note_body_no_max_length(self, db):
        """FINDING: Note body (TextField) accepts 100KB — no max_length."""
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_NOTE_LIST, data=json.dumps({"title": "Huge", "body": "A" * 100000}), content_type="application/json")
        assert resp.status_code in [200, 201]

    def test_chat_message_max_length_sqlite(self, db):
        """FINDING: SQLite does not enforce max_length — 501 chars stored without error."""
        user = make_user()
        room = CoworkRoom.objects.create(name="Test", code="ABCDEF", created_by=user)
        # This should raise on PostgreSQL but not SQLite
        msg = ChatMessage.objects.create(room=room, user=user, content="A" * 501)
        # In production (PostgreSQL), this would raise DataError
        assert len(msg.content) == 501

    def test_room_name_at_max_length(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_ROOM_LIST, data=json.dumps({"name": "A" * 100}), content_type="application/json")
        assert resp.status_code in [200, 201]

    def test_room_name_exceeds_max(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_ROOM_LIST, data=json.dumps({"name": "A" * 101}), content_type="application/json")
        assert resp.status_code == 400

    def test_tags_exceeds_max_length(self, db):
        user = make_user()
        c = auth_client(user)
        doc = make_document(user)
        resp = c.patch(f"/api/documents/{doc.id}/move/", data=json.dumps({"tags": "A" * 501}), content_type="application/json")
        assert resp.status_code == 400

    def test_negative_position_triggers_status_shadowing_bug(self, db):
        """FIXED: Variable shadowing bug in TaskListView.post() has been fixed.
        The variable was renamed to `task_status` so it no longer shadows the
        `rest_framework.status` module. Task creation now succeeds."""
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_TASK_LIST, data=json.dumps({"title": "Neg", "status": "todo", "position": -1}), content_type="application/json")
        assert resp.status_code == 201

    def test_negative_wpm_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.patch(URL_PREFERENCES, data=json.dumps({"default_wpm": -1}), content_type="application/json")
        assert resp.status_code == 400

    def test_zero_wpm_accepted(self, db):
        """FINDING: WPM=0 accepted by PositiveIntegerField — could cause client-side division by zero."""
        user = make_user()
        c = auth_client(user)
        resp = c.patch(URL_PREFERENCES, data=json.dumps({"default_wpm": 0}), content_type="application/json")
        assert resp.status_code == 200

    def test_zero_chunk_size_accepted(self, db):
        """FINDING: Chunk size=0 accepted — potential division by zero in RSVP display."""
        user = make_user()
        c = auth_client(user)
        resp = c.patch(URL_PREFERENCES, data=json.dumps({"default_chunk_size": 0}), content_type="application/json")
        assert resp.status_code == 200

    def test_negative_xp_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_XP_EVENT, data=json.dumps({"event_type": "words_read", "xp_amount": -100}), content_type="application/json")
        assert resp.status_code == 400

    def test_zero_xp_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_XP_EVENT, data=json.dumps({"event_type": "words_read", "xp_amount": 0}), content_type="application/json")
        assert resp.status_code == 400

    def test_xp_exceeds_max(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_XP_EVENT, data=json.dumps({"event_type": "words_read", "xp_amount": 1001}), content_type="application/json")
        assert resp.status_code == 400

    def test_flashcard_quality_range(self, db):
        user = make_user()
        c = auth_client(user)
        deck = FlashcardDeck.objects.create(user=user, name="T")
        card = Flashcard.objects.create(deck=deck, front="Q", back="A")
        assert c.post(f"/api/reader/flashcards/review/{card.id}/", data=json.dumps({"quality": 6}), content_type="application/json").status_code == 400
        assert c.post(f"/api/reader/flashcards/review/{card.id}/", data=json.dumps({"quality": -1}), content_type="application/json").status_code == 400

    def test_negative_bold_intensity_accepted(self, db):
        """FINDING: FloatField allows negative bold_intensity — no min validation."""
        user = make_user()
        c = auth_client(user)
        resp = c.patch(URL_PREFERENCES, data=json.dumps({"default_bold_intensity": -1.0}), content_type="application/json")
        assert resp.status_code == 200

    def test_huge_bold_intensity_accepted(self, db):
        """FINDING: FloatField allows extreme bold_intensity — no max validation."""
        user = make_user()
        c = auth_client(user)
        resp = c.patch(URL_PREFERENCES, data=json.dumps({"default_bold_intensity": 999.9}), content_type="application/json")
        assert resp.status_code == 200

    def test_huge_folder_id_returns_404(self, db):
        user = make_user()
        c = auth_client(user)
        doc = make_document(user)
        resp = c.patch(f"/api/documents/{doc.id}/move/", data=json.dumps({"folder_id": 99999999999999}), content_type="application/json")
        assert resp.status_code == 404

    def test_zero_position_update(self, db):
        user = make_user()
        c = auth_client(user)
        doc = make_document(user)
        session = ReadingSession.objects.create(user=user, document=doc)
        resp = c.patch(f"/api/reader/session/{session.id}/", data=json.dumps({"position": 0}), content_type="application/json")
        assert resp.status_code == 200

    def test_negative_position_update_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        doc = make_document(user)
        session = ReadingSession.objects.create(user=user, document=doc)
        resp = c.patch(f"/api/reader/session/{session.id}/", data=json.dumps({"position": -1}), content_type="application/json")
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────
# 4. TYPE CONFUSION
# ─────────────────────────────────────────────────────────────

class TestTypeConfusion:
    def test_string_folder_id_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        doc = make_document(user)
        resp = c.patch(f"/api/documents/{doc.id}/move/", data=json.dumps({"folder_id": "not_an_int"}), content_type="application/json")
        assert resp.status_code == 400

    def test_string_for_xp_amount_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_XP_EVENT, data=json.dumps({"event_type": "words_read", "xp_amount": "one hundred"}), content_type="application/json")
        assert resp.status_code == 400

    def test_string_for_position_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        doc = make_document(user)
        session = ReadingSession.objects.create(user=user, document=doc)
        resp = c.patch(f"/api/reader/session/{session.id}/", data=json.dumps({"position": "abc"}), content_type="application/json")
        assert resp.status_code == 400

    def test_int_for_folder_name_coerced(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_FOLDER_LIST, data=json.dumps({"name": 12345}), content_type="application/json")
        assert resp.status_code in [200, 201]

    def test_array_for_folder_data_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_FOLDER_LIST, data=json.dumps([{"name": "test"}]), content_type="application/json")
        assert resp.status_code == 400

    def test_invalid_task_status_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_TASK_LIST, data=json.dumps({"title": "Test", "status": "invalid"}), content_type="application/json")
        assert resp.status_code == 400

    def test_invalid_note_color_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_NOTE_LIST, data=json.dumps({"title": "Test", "body": "Body", "color": "neon"}), content_type="application/json")
        assert resp.status_code == 400

    def test_invalid_theme_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.patch(URL_PREFERENCES, data=json.dumps({"theme": "hacked"}), content_type="application/json")
        assert resp.status_code == 400

    def test_invalid_mode_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.patch(URL_PREFERENCES, data=json.dumps({"default_mode": "speed"}), content_type="application/json")
        assert resp.status_code == 400

    def test_malformed_json_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_FOLDER_LIST, data='{"name": "test"', content_type="application/json")
        assert resp.status_code == 400

    def test_deeply_nested_json(self, db):
        user = make_user()
        c = auth_client(user)
        payload = {"name": "test"}
        for _ in range(50):
            payload = {"nested": payload}
        resp = c.post(URL_FOLDER_LIST, data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 400

    def test_missing_folder_name_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_FOLDER_LIST, data=json.dumps({}), content_type="application/json")
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────
# 5. METHOD CONFUSION
# ─────────────────────────────────────────────────────────────

class TestMethodConfusion:
    def test_get_on_upload_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.get("/api/documents/upload/")
        assert resp.status_code == 405

    def test_get_on_xp_event_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.get(URL_XP_EVENT)
        assert resp.status_code == 405

    def test_get_on_room_join_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.get(URL_ROOM_JOIN)
        assert resp.status_code == 405

    def test_post_on_document_list_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_DOCUMENT_LIST)
        assert resp.status_code == 405

    def test_post_on_audio_tracks_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_AUDIO_TRACKS)
        assert resp.status_code == 405

    def test_post_on_user_xp_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_USER_XP)
        assert resp.status_code == 405

    def test_post_on_streak_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_STREAK)
        assert resp.status_code == 405

    def test_put_on_folder_list_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.put(URL_FOLDER_LIST, data=json.dumps({"name": "t"}), content_type="application/json")
        assert resp.status_code == 405

    def test_delete_on_folder_list_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.delete(URL_FOLDER_LIST)
        assert resp.status_code == 405

    def test_delete_on_task_list_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.delete(URL_TASK_LIST)
        assert resp.status_code == 405

    def test_post_on_preferences_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_PREFERENCES, data=json.dumps({"default_wpm": 500}), content_type="application/json")
        assert resp.status_code == 405

    def test_delete_on_preferences_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.delete(URL_PREFERENCES)
        assert resp.status_code == 405

    def test_post_on_document_status_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        doc = make_document(user)
        resp = c.post(f"/api/documents/{doc.id}/status/")
        assert resp.status_code == 405


# ─────────────────────────────────────────────────────────────
# 6. CONTENT-TYPE ATTACKS
# ─────────────────────────────────────────────────────────────

class TestContentTypeAttacks:
    def test_form_data_on_json_endpoint(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_FOLDER_LIST, data="name=TestFolder", content_type="application/x-www-form-urlencoded")
        assert resp.status_code in [200, 201, 400, 415]

    def test_xml_content_type(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_FOLDER_LIST, data="<name>Test</name>", content_type="application/xml")
        assert resp.status_code in [400, 415]


# ─────────────────────────────────────────────────────────────
# 7. TIMER & HIGHLIGHT EDGE CASES
# ─────────────────────────────────────────────────────────────

class TestTimerAndHighlightEdgeCases:
    def test_timer_duration_zero(self, db):
        user = make_user()
        room = CoworkRoom.objects.create(name="Test", code="ABCDEF", created_by=user, timer_duration=0, timer_remaining=0)
        assert room.timer_duration == 0

    def test_timer_duration_negative_rejected(self, db):
        user = make_user()
        with pytest.raises(Exception):
            CoworkRoom.objects.create(name="Test", code="ABCDEF2", created_by=user, timer_duration=-1)

    def test_timer_remaining_large_value(self, db):
        """FINDING: Model allows timer_remaining=999999; consumer clamps to 0-86400."""
        user = make_user()
        room = CoworkRoom.objects.create(name="Test", code="ABCDEF3", created_by=user, timer_remaining=999999)
        assert room.timer_remaining == 999999

    def test_highlight_color_no_validation(self, db):
        """FINDING: Highlight color accepts any string — no hex format validation. XSS vector if rendered unsanitized."""
        user = make_user()
        c = auth_client(user)
        doc = make_document(user)
        resp = c.post(URL_HIGHLIGHT_LIST, data=json.dumps({
            "document_id": doc.id,
            "highlights": [{"text": "test", "startIndex": 0, "color": "javascript:alert(1)"}],
        }), content_type="application/json")
        assert resp.status_code in [200, 201]
        assert Highlight.objects.first().color == "javascript:alert(1)"

    def test_highlight_negative_start_index_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        doc = make_document(user)
        resp = c.post(URL_HIGHLIGHT_LIST, data=json.dumps({
            "document_id": doc.id,
            "highlights": [{"text": "test", "startIndex": -1, "color": "#fbbf24"}],
        }), content_type="application/json")
        assert resp.status_code == 400

    def test_highlight_string_start_index_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        doc = make_document(user)
        resp = c.post(URL_HIGHLIGHT_LIST, data=json.dumps({
            "document_id": doc.id,
            "highlights": [{"text": "test", "startIndex": "abc", "color": "#fbbf24"}],
        }), content_type="application/json")
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────
# 8. SEARCH/FILTER EDGE CASES
# ─────────────────────────────────────────────────────────────

class TestSearchFilterEdgeCases:
    def test_sql_injection_safe(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.get(URL_DOCUMENT_LIST, {"search": "'; DROP TABLE documents_document; --"})
        assert resp.status_code == 200

    def test_search_special_chars(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.get(URL_DOCUMENT_LIST, {"search": ".*+?^${}()|[]\\"})
        assert resp.status_code == 200

    def test_folder_filter_none(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.get(URL_DOCUMENT_LIST, {"folder": "none"})
        assert resp.status_code == 200

    def test_folder_filter_invalid_id_500(self, db):
        """FIXED: Non-numeric folder ID is now caught with try/except and returns 400."""
        user = make_user()
        c = auth_client(user)
        resp = c.get(URL_DOCUMENT_LIST, {"folder": "not_an_int"})
        assert resp.status_code == 400

    def test_highlight_filter_invalid_document_id_500(self, db):
        """FIXED: Non-numeric document ID in highlights filter is now caught and returns 400."""
        user = make_user()
        c = auth_client(user)
        resp = c.get(URL_HIGHLIGHT_LIST, {"document": "abc"})
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────
# 9. AUTH EDGE CASES
# ─────────────────────────────────────────────────────────────

class TestAuthEdgeCases:
    def test_desktop_mode_auto_auth(self, db):
        """FINDING: In desktop mode, AutoLoginMiddleware auto-authenticates ALL requests.
        Unauthenticated users can access all endpoints — expected for single-user desktop,
        but dangerous if accidentally deployed in cloud mode."""
        c = Client()
        # These should fail in cloud mode but succeed in desktop mode
        resp = c.get(URL_DOCUMENT_LIST)
        assert resp.status_code == 200  # Auto-authenticated by middleware

    def test_unauthenticated_upload_returns_400(self, db):
        """FINDING: Upload endpoint returns 400 (serializer validation) instead of 401/403
        because auto-auth provides a user but the request data is invalid."""
        c = Client()
        resp = c.post("/api/documents/upload/", data={"filename": "test.pdf", "file_size": 1024})
        # Desktop mode: auto-authenticated, returns 400 because desktop uses file upload, not filename
        assert resp.status_code in [400, 302, 401, 403]


# ─────────────────────────────────────────────────────────────
# 10. RACE CONDITIONS
# ─────────────────────────────────────────────────────────────

class TestRaceConditions:
    def test_duplicate_folder_names_allowed(self, db):
        """FINDING: Duplicate folder names allowed — unique_together includes 'parent', so NULL parent allows dupes."""
        user = make_user()
        c = auth_client(user)
        c.post(URL_FOLDER_LIST, data=json.dumps({"name": "Dup"}), content_type="application/json")
        resp = c.post(URL_FOLDER_LIST, data=json.dumps({"name": "Dup"}), content_type="application/json")
        assert resp.status_code in [200, 201]
        assert Folder.objects.count() == 2

    def test_duplicate_deck_names_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        c.post(URL_FLASHCARD_DECK_LIST, data=json.dumps({"name": "Same"}), content_type="application/json")
        resp = c.post(URL_FLASHCARD_DECK_LIST, data=json.dumps({"name": "Same"}), content_type="application/json")
        assert resp.status_code == 400

    def test_update_deleted_session_404(self, db):
        user = make_user()
        c = auth_client(user)
        doc = make_document(user)
        session = ReadingSession.objects.create(user=user, document=doc)
        sid = session.id
        session.delete()
        resp = c.patch(f"/api/reader/session/{sid}/", data=json.dumps({"position": 10}), content_type="application/json")
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────
# 11. FILENAME SANITIZATION (unit tests)
# ─────────────────────────────────────────────────────────────

class TestFilenameSanitization:
    def test_sanitize_empty(self):
        from config.backends.storage import _sanitize_filename
        assert _sanitize_filename("") == "document.pdf"
        assert _sanitize_filename(None) == "document.pdf"

    def test_sanitize_null_byte(self):
        from config.backends.storage import _sanitize_filename
        assert _sanitize_filename("test\x00.pdf") == "test.pdf"

    def test_sanitize_path_traversal(self):
        from config.backends.storage import _sanitize_filename
        assert _sanitize_filename("../../etc/passwd.pdf") == "passwd.pdf"

    def test_sanitize_dotfiles(self):
        from config.backends.storage import _sanitize_filename
        assert _sanitize_filename(".hidden") == "hidden"

    def test_safe_extension_normal(self):
        from config.backends.storage import _safe_extension
        assert _safe_extension("test.pdf") == "pdf"

    def test_safe_extension_long_ext_rejected(self):
        from config.backends.storage import _safe_extension
        assert _safe_extension("test.abcdefghijk") == "pdf"

    def test_safe_extension_null_in_ext(self):
        from config.backends.storage import _safe_extension
        assert _safe_extension("test.p\x00df") == "pdf"

    def test_safe_extension_slash_in_ext(self):
        from config.backends.storage import _safe_extension
        assert _safe_extension("test.p/df") == "pdf"


# ─────────────────────────────────────────────────────────────
# 12. JSON METADATA ABUSE
# ─────────────────────────────────────────────────────────────

class TestMetadataAbuse:
    def test_deeply_nested_metadata(self, db):
        user = make_user()
        c = auth_client(user)
        nested = {"a": 1}
        for _ in range(100):
            nested = {"nested": nested}
        resp = c.post(URL_XP_EVENT, data=json.dumps({"event_type": "words_read", "xp_amount": 10, "metadata": nested}), content_type="application/json")
        assert resp.status_code in [200, 201]

    def test_huge_metadata(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_XP_EVENT, data=json.dumps({"event_type": "words_read", "xp_amount": 10, "metadata": {"d": "A" * 100000}}), content_type="application/json")
        assert resp.status_code in [200, 201]

    def test_array_metadata_accepted(self, db):
        """FINDING: JSONField metadata accepts arrays, strings, not just objects."""
        user = make_user()
        c = auth_client(user)
        for val in [[1, 2, 3], "string", 42]:
            resp = c.post(URL_XP_EVENT, data=json.dumps({"event_type": "words_read", "xp_amount": 10, "metadata": val}), content_type="application/json")
            assert resp.status_code in [200, 201]


# ─────────────────────────────────────────────────────────────
# 13. URL PARAMETER EDGE CASES
# ─────────────────────────────────────────────────────────────

class TestURLParameterEdgeCases:
    def test_zero_document_id_404(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.get("/api/reader/text/0/")
        assert resp.status_code == 404

    def test_string_in_int_url_404(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.get("/api/reader/text/abc/")
        assert resp.status_code == 404

    def test_very_large_id(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.get("/api/reader/text/99999999999999999999/")
        assert resp.status_code in [404, 400]


# ─────────────────────────────────────────────────────────────
# 14. HIGHLIGHT SYNC EDGE CASES
# ─────────────────────────────────────────────────────────────

class TestHighlightSyncEdgeCases:
    def test_sync_empty_highlights(self, db):
        user = make_user()
        c = auth_client(user)
        doc = make_document(user)
        resp = c.post(URL_HIGHLIGHT_LIST, data=json.dumps({"document_id": doc.id, "highlights": []}), content_type="application/json")
        assert resp.status_code in [200, 201]
        assert Highlight.objects.count() == 0

    def test_sync_huge_list(self, db):
        user = make_user()
        c = auth_client(user)
        doc = make_document(user)
        highlights = [{"text": f"HL {i}", "startIndex": i, "color": "#fbbf24"} for i in range(1000)]
        resp = c.post(URL_HIGHLIGHT_LIST, data=json.dumps({"document_id": doc.id, "highlights": highlights}), content_type="application/json")
        assert resp.status_code in [200, 201]

    def test_sync_missing_document_id(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_HIGHLIGHT_LIST, data=json.dumps({"highlights": [{"text": "t", "startIndex": 0, "color": "#fbbf24"}]}), content_type="application/json")
        assert resp.status_code == 400

    def test_sync_invalid_document_id(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_HIGHLIGHT_LIST, data=json.dumps({"document_id": 99999, "highlights": [{"text": "t", "startIndex": 0, "color": "#fbbf24"}]}), content_type="application/json")
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────
# 15. TASK BATCH UPDATE EDGE CASES
# ─────────────────────────────────────────────────────────────

class TestTaskBatchUpdateEdgeCases:
    def test_batch_empty_list_rejected(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.patch(URL_TASK_LIST, data=json.dumps({"tasks": []}), content_type="application/json")
        assert resp.status_code == 400

    def test_batch_nonexistent_task_skipped(self, db):
        user = make_user()
        c = auth_client(user)
        resp = c.patch(URL_TASK_LIST, data=json.dumps({"tasks": [{"id": 99999, "status": "doing"}]}), content_type="application/json")
        assert resp.status_code == 200

    def test_batch_other_user_task_ignored(self, db):
        user = make_user()
        other = User.objects.create(email="other@example.com")
        c = auth_client(user)
        task = Task.objects.create(user=other, title="Other's task")
        resp = c.patch(URL_TASK_LIST, data=json.dumps({"tasks": [{"id": task.id, "status": "done"}]}), content_type="application/json")
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.status == "todo"

    def test_batch_negative_position(self, db):
        user = make_user()
        c = auth_client(user)
        task = Task.objects.create(user=user, title="Test")
        resp = c.patch(URL_TASK_LIST, data=json.dumps({"tasks": [{"id": task.id, "position": -1}]}), content_type="application/json")
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.position == -1

    def test_batch_invalid_status_accepted(self, db):
        """FIXED: TaskListView now validates status values before bulk update."""
        user = make_user()
        c = auth_client(user)
        task = Task.objects.create(user=user, title="Test")
        resp = c.patch(URL_TASK_LIST, data=json.dumps({"tasks": [{"id": task.id, "status": "invalid"}]}), content_type="application/json")
        assert resp.status_code == 400



# ─────────────────────────────────────────────────────────────
# 16. XP GAMING
# ─────────────────────────────────────────────────────────────

class TestXPGaming:
    def test_max_xp_per_event(self, db):
        """FIXED: XP is now server-computed — client cannot self-award. words_read gives 10 XP."""
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_XP_EVENT, data=json.dumps({"event_type": "words_read", "xp_amount": 1000}), content_type="application/json")
        assert resp.status_code in [200, 201]
        assert UserXP.objects.get(user=user).total_xp == 10

    def test_rapid_xp_accumulation_no_rate_limit(self, db):
        """FIXED: Rate limiting is now in place (100 req/min). XP is also server-computed."""
        from django.core.cache import cache
        cache.clear()
        user = make_user()
        c = auth_client(user)
        for _ in range(50):
            resp = c.post(URL_XP_EVENT, data=json.dumps({"event_type": "words_read", "xp_amount": 1000}), content_type="application/json")
            assert resp.status_code in [200, 201]
        assert UserXP.objects.get(user=user).total_xp == 500  # 50 * 10 (server-computed)

    def test_words_read_inflation(self, db):
        """FINDING: words_read not validated against actual document word count (still true).
        XP is server-computed and rate limiting is in place."""
        from django.core.cache import cache
        cache.clear()
        user = make_user()
        c = auth_client(user)
        resp = c.post(URL_XP_EVENT, data=json.dumps({
            "event_type": "words_read", "xp_amount": 10, "words_read": 999999, "minutes_read": 999999,
        }), content_type="application/json")
        assert resp.status_code in [200, 201]
        assert DailyReadingStat.objects.first().words_read == 999999
