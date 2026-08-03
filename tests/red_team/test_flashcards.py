"""
RED TEAM: Flashcards Adversarial Tests.

Tests FlashcardDeck and Flashcard models and APIs.
URLs: /api/reader/flashcards/decks/, /api/reader/flashcards/cards/, /api/reader/flashcards/review/

P0 = crash/security | P1 = data loss | P2 = wrong behavior | P3 = UX/error handling
"""

import json
import pytest
from django.test import Client
from django.utils import timezone

from apps.documents.models import Document
from apps.reader.models import FlashcardDeck, Flashcard
from apps.users.models import User


@pytest.fixture
def user(db):
    return User.objects.create(email="flashcards_redteam@test.com")


@pytest.fixture
def client(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def document(db, user):
    return Document.objects.create(
        user=user,
        title="Flashcard Doc",
        file_key="uploads/99/flashcard_test.pdf",
        file_type=Document.FILE_TYPE_PDF,
        status=Document.STATUS_READY,
        raw_text="Flashcard source content. " * 50,
        page_count=1,
        word_count=100,
    )


@pytest.fixture
def deck(db, user, document):
    return FlashcardDeck.objects.create(
        user=user, name="Test Deck", document=document
    )


# =============================================================================
# P0 — SECURITY / CRASH TESTS
# =============================================================================

@pytest.mark.django_db
class TestFlashcardsP0:
    """Security and crash tests for flashcards."""

    def test_create_deck_nonexistent_document__P0(self, client):
        """SCORE: P0 — Creating deck with non-existent document ID should error clearly."""
        response = client.post(
            "/api/reader/flashcards/decks/",
            {"name": "Ghost Deck", "document": 99999},
            content_type="application/json",
        )
        # The FlashcardDeckSerializer doesn't validate document existence.
        # The ForeignKey `document` has on_delete=SET_NULL, so it should
        # accept NULL (blank). Actually serializer has 'document' in fields.
        # If document 99999 doesn't exist, Django will raise IntegrityError or
        # the serializer will let it through because null=True.
        # This could be 201 (document set to null) OR 400 (validation).
        assert response.status_code != 500, (
            f"P0: Non-existent document ID caused 500"
        )

    def test_create_card_empty_front__P0(self, client, deck):
        """SCORE: P0 — Creating card with empty front (question/prompt) should work or error."""
        response = client.post(
            "/api/reader/flashcards/cards/",
            {"deck": deck.id, "front": "", "back": "Some answer"},
            content_type="application/json",
        )
        # front is TextField with no constraints — could accept empty
        assert response.status_code != 500, (
            f"P0: Empty front caused 500"
        )

    def test_create_card_empty_back__P0(self, client, deck):
        """SCORE: P0 — Creating card with empty back (answer)."""
        response = client.post(
            "/api/reader/flashcards/cards/",
            {"deck": deck.id, "front": "Question?", "back": ""},
            content_type="application/json",
        )
        # back has blank=True, default=""
        assert response.status_code != 500, (
            f"P0: Empty back caused 500"
        )

    def test_create_card_empty_both__P0(self, client, deck):
        """SCORE: P0 — Card with both front and back empty."""
        response = client.post(
            "/api/reader/flashcards/cards/",
            {"deck": deck.id, "front": "", "back": ""},
            content_type="application/json",
        )
        assert response.status_code != 500, f"P0: Empty card caused 500"

    def test_create_card_nonexistent_deck__P0(self, client):
        """SCORE: P0 — Creating card in non-existent deck must 404."""
        response = client.post(
            "/api/reader/flashcards/cards/",
            {"deck": 99999, "front": "Q", "back": "A"},
            content_type="application/json",
        )
        assert response.status_code == 404, (
            f"P0 VULN: Card created in non-existent deck! Got {response.status_code}"
        )

    def test_create_card_other_users_deck__P0(self, client):
        """SCORE: P0 — Cannot create card in another user's deck."""
        other = User.objects.create(email="deck_owner@test.com")
        other_deck = FlashcardDeck.objects.create(user=other, name="Their Deck")

        response = client.post(
            "/api/reader/flashcards/cards/",
            {"deck": other_deck.id, "front": "Q", "back": "A"},
            content_type="application/json",
        )
        assert response.status_code == 404, (
            f"P0 VULN: Created card in another user's deck! Got {response.status_code}"
        )

    def test_review_nonexistent_card__P0(self, client):
        """SCORE: P0 — Reviewing non-existent card must 404."""
        response = client.post(
            "/api/reader/flashcards/review/99999/",
            {"quality": 3},
            content_type="application/json",
        )
        assert response.status_code == 404, (
            f"P0: Review of non-existent card returned {response.status_code}"
        )

    def test_review_other_users_card__P0(self, client):
        """SCORE: P0 — Cannot review another user's card."""
        other = User.objects.create(email="card_owner@test.com")
        other_deck = FlashcardDeck.objects.create(user=other, name="Deck")
        card = Flashcard.objects.create(deck=other_deck, front="Q", back="A")

        response = client.post(
            f"/api/reader/flashcards/review/{card.id}/",
            {"quality": 5},
            content_type="application/json",
        )
        assert response.status_code == 404, (
            f"P0 VULN: Reviewed another user's card! Got {response.status_code}"
        )

    def test_review_invalid_quality__P0(self, client, deck):
        """SCORE: P0 — Quality must be 0-5 (ReviewFlashcardSerializer min=0, max=5)."""
        card = Flashcard.objects.create(deck=deck, front="Q", back="A")

        for bad_quality in [-1, 6, 999, -100, "abc", None]:
            response = client.post(
                f"/api/reader/flashcards/review/{card.id}/",
                {"quality": bad_quality},
                content_type="application/json",
            )
            assert response.status_code == 400, (
                f"P0: Invalid quality {bad_quality} accepted. Got {response.status_code}"
            )

    def test_xss_in_flashcard_content__P0(self, client, deck):
        """SCORE: P0 — XSS payloads in front/back should be stored as-is."""
        xss = '<script>alert("XSS")</script>'
        response = client.post(
            "/api/reader/flashcards/cards/",
            {"deck": deck.id, "front": xss, "back": xss},
            content_type="application/json",
        )
        assert response.status_code == 201
        card = Flashcard.objects.get(id=response.json()["id"])
        assert card.front == xss, "P0: XSS front was modified"
        assert card.back == xss, "P0: XSS back was modified"

    def test_massive_card_content__P0(self, client, deck):
        """SCORE: P0 — Extremely large front/back should not crash."""
        huge = "A" * 500_000  # 500KB
        response = client.post(
            "/api/reader/flashcards/cards/",
            {"deck": deck.id, "front": huge, "back": huge},
            content_type="application/json",
        )
        assert response.status_code != 500, f"P0: 500KB card caused 500"

    def test_delete_nonexistent_card__P0(self, client):
        """SCORE: P0 — Deleting non-existent card must 404."""
        response = client.delete("/api/reader/flashcards/cards/99999/")
        assert response.status_code == 404

    def test_delete_other_users_deck__P0(self, client, deck):
        """SCORE: P0 — Cannot delete another user's deck."""
        other = User.objects.create(email="other_deck@test.com")
        other_deck = FlashcardDeck.objects.create(user=other, name="Other Deck")

        response = client.delete(f"/api/reader/flashcards/decks/{other_deck.id}/")
        assert response.status_code == 404, (
            f"P0 VULN: Deleted another user's deck!"
        )


# =============================================================================
# P2 — WRONG BEHAVIOR TESTS
# =============================================================================

@pytest.mark.django_db
class TestFlashcardsP2:
    """Tests for incorrect behavior."""

    def test_flashcard_schedule_review__P2(self, deck):
        """SCORE: P2 — Verify spaced repetition scheduling works."""
        card = Flashcard.objects.create(deck=deck, front="Q1", back="A1")

        # First review with quality 5 (perfect)
        card.schedule_review(5)
        card.refresh_from_db()

        assert card.review_count == 1
        assert card.last_reviewed is not None
        assert card.next_review is not None
        # Interval should be 1 day for first review with quality >= 3
        from datetime import timedelta
        expected_next = card.last_reviewed + timedelta(days=1)
        delta = abs((card.next_review - expected_next).total_seconds())
        assert delta < 10, f"P2: Expected 1-day interval, got {card.next_review}"

    def test_flashcard_quality_zero_resets__P2(self, deck):
        """SCORE: P2 — Quality 0 should reset interval to 1 day."""
        card = Flashcard.objects.create(deck=deck, front="Q", back="A")
        card.schedule_review(0)
        card.refresh_from_db()
        assert card.review_count == 1
        # Quality 0 (< 3) resets to 1 day
        from datetime import timedelta
        expected = card.last_reviewed + timedelta(days=1)
        delta = abs((card.next_review - expected).total_seconds())
        assert delta < 10, f"P2: Quality 0 didn't reset to 1 day"

    def test_flashcard_ease_factor_bounds__P2(self, deck):
        """SCORE: P2 — Ease factor should have a lower bound of 1.3."""
        card = Flashcard.objects.create(deck=deck, front="Q", back="A")
        original_ease = card.ease_factor

        # Bomb the card with quality 0 repeatedly
        for _ in range(20):
            card.schedule_review(0)
            card.refresh_from_db()

        assert card.ease_factor >= 1.3, (
            f"P2: Ease factor dropped below 1.3: {card.ease_factor}"
        )

    def test_review_next_card_returns_due_cards__P2(self, client, deck):
        """SCORE: P2 — GET /flashcards/review/ should return oldest due card."""
        # Create cards with different next_review dates
        now = timezone.now()
        card1 = Flashcard.objects.create(
            deck=deck, front="Old due", back="A",
            next_review=now - timezone.timedelta(days=5)
        )
        card2 = Flashcard.objects.create(
            deck=deck, front="Recently due", back="B",
            next_review=now - timezone.timedelta(days=1)
        )
        card3 = Flashcard.objects.create(
            deck=deck, front="Not due yet", back="C",
            next_review=now + timezone.timedelta(days=10)
        )

        response = client.get("/api/reader/flashcards/review/")
        assert response.status_code == 200
        data = response.json()

        assert data["done"] is False
        # Should return card1 (oldest due)
        assert data["card"]["id"] == card1.id, (
            f"P2: Expected oldest due card (id={card1.id}), got id={data['card']['id']}"
        )

    def test_no_cards_due_returns_done__P2(self, client, deck):
        """SCORE: P2 — When no cards are due, review endpoint returns done=True."""
        Flashcard.objects.create(
            deck=deck, front="Future", back="A",
            next_review=timezone.now() + timezone.timedelta(days=365)
        )

        response = client.get("/api/reader/flashcards/review/")
        assert response.status_code == 200
        data = response.json()
        assert data["done"] is True, (
            f"P2: Expected done=True for no due cards, got {data}"
        )

    def test_card_count_and_due_count__P2(self, client, deck):
        """SCORE: P2 — Deck list should include card_count and due_count."""
        now = timezone.now()
        Flashcard.objects.create(deck=deck, front="Due", back="A", next_review=now)
        Flashcard.objects.create(deck=deck, front="Future", back="B",
                                 next_review=now + timezone.timedelta(days=30))
        Flashcard.objects.create(deck=deck, front="Also Due", back="C",
                                 next_review=now - timezone.timedelta(days=1))

        response = client.get("/api/reader/flashcards/decks/")
        data = response.json()
        assert len(data) == 1
        assert data[0]["card_count"] == 3
        assert data[0]["due_count"] == 2, (
            f"P2: Expected 2 due cards, got {data[0]['due_count']}"
        )


# =============================================================================
# P3 — UX TESTS
# =============================================================================

@pytest.mark.django_db
class TestFlashcardsP3:
    """UX and error handling tests."""

    def test_create_deck_duplicate_name__P3(self, client, deck):
        """SCORE: P3 — Creating deck with same name should error clearly (unique_together)."""
        response = client.post(
            "/api/reader/flashcards/decks/",
            {"name": "Test Deck"},
            content_type="application/json",
        )
        assert response.status_code == 400, (
            f"P3: Duplicate deck name returned {response.status_code}"
        )

    def test_get_deck_detail_includes_cards__P3(self, client, deck):
        """SCORE: P3 — Deck detail should include cards array."""
        Flashcard.objects.create(deck=deck, front="Q1", back="A1")
        Flashcard.objects.create(deck=deck, front="Q2", back="A2")

        response = client.get(f"/api/reader/flashcards/decks/{deck.id}/")
        assert response.status_code == 200
        data = response.json()
        assert "deck" in data
        assert "cards" in data
        assert len(data["cards"]) == 2

    def test_unauthenticated_access__P3(self):
        """SCORE: P3 — Desktop mode auto-authenticates; verify no 500 on unauthed access."""
        anon = Client()
        for url in [
            "/api/reader/flashcards/decks/",
            "/api/reader/flashcards/cards/",
            "/api/reader/flashcards/review/",
        ]:
            response = anon.get(url)
            assert response.status_code != 500, (
                f"P3: Unauthenticated access to {url} caused 500"
            )
