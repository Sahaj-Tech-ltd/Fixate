from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.db import IntegrityError
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta
import logging

from apps.documents.models import Document
from apps.reader.models import ReadingSession, UserPreferences, AudioTrack, Task, Note, CoworkRoom, RoomParticipant, UserXP, XPEvent, DailyReadingStat, FlashcardDeck, Flashcard, Highlight
from apps.reader.serializers import (
    UserPreferencesSerializer,
    ReadingSessionSerializer,
    UpdatePositionSerializer,
    AudioTrackSerializer,
    TaskSerializer,
    NoteSerializer,
    CoworkRoomSerializer,
    ChatMessageSerializer,
    UserXPSerializer,
    XPEventSerializer,
    RecordXPEventSerializer,
    FlashcardDeckSerializer,
    FlashcardSerializer,
    ReviewFlashcardSerializer,
    UpdateSessionSerializer,
    HighlightSerializer,
    HighlightSyncSerializer,
)
from config.adhd_profile import get_profile_defaults
from config.backends import storage

logger = logging.getLogger(__name__)


class UserPreferencesView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
        serializer = UserPreferencesSerializer(preferences)
        return Response(serializer.data)
    
    def patch(self, request):
        preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
        serializer = UserPreferencesSerializer(preferences, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class StartReadingView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, document_id):
        document = get_object_or_404(Document, id=document_id, user=request.user)
        
        if document.status != Document.STATUS_READY:
            return Response(
                {'error': 'Document is not ready for reading'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
        
        from django.db import IntegrityError

        try:
            session, created = ReadingSession.objects.get_or_create(
                user=request.user,
                document=document,
                defaults={
                    'mode': preferences.default_mode,
                    'wpm': preferences.default_wpm,
                    'bold_intensity': preferences.default_bold_intensity,
                    'font': preferences.default_font,
                    'chunk_size': preferences.default_chunk_size,
                }
            )
        except IntegrityError:
            session = ReadingSession.objects.get(user=request.user, document=document)
        
        return Response({
            'session': ReadingSessionSerializer(session).data,
            'text': document.raw_text,
            'word_count': document.word_count,
        })


class UpdateSessionView(APIView):
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, session_id):
        session = get_object_or_404(ReadingSession, id=session_id, user=request.user)
        
        if 'position' in request.data:
            serializer = UpdatePositionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            session.last_position = serializer.validated_data['position']
            session.completed = serializer.validated_data.get('completed', False)
        
        # Validate session fields with proper types and ranges
        session_data = {
            k: v for k, v in request.data.items()
            if k in ['mode', 'wpm', 'bold_intensity', 'font', 'chunk_size']
        }
        if session_data:
            session_serializer = UpdateSessionSerializer(data=session_data)
            session_serializer.is_valid(raise_exception=True)
            for field, value in session_serializer.validated_data.items():
                setattr(session, field, value)
        
        session.save()
        return Response(ReadingSessionSerializer(session).data)


class DocumentTextView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, document_id):
        document = get_object_or_404(Document, id=document_id, user=request.user)
        
        if document.status != Document.STATUS_READY:
            return Response(
                {'error': 'Document is not ready'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'text': document.raw_text,
            'word_count': document.word_count,
        })


class ReaderView(LoginRequiredMixin, TemplateView):
    template_name = "reader.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        document_id = kwargs.get('document_id')
        document = get_object_or_404(Document, id=document_id, user=self.request.user)
        
        if document.status != Document.STATUS_READY:
            context['error'] = 'Document is not ready for reading'
            return context
        
        preferences, _ = UserPreferences.objects.get_or_create(user=self.request.user)
        
        from django.db import IntegrityError

        try:
            session, created = ReadingSession.objects.get_or_create(
                user=self.request.user,
                document=document,
                defaults={
                    'mode': preferences.default_mode,
                    'wpm': preferences.default_wpm,
                    'bold_intensity': preferences.default_bold_intensity,
                    'font': preferences.default_font,
                    'chunk_size': preferences.default_chunk_size,
                }
            )
        except IntegrityError:
            session = ReadingSession.objects.get(user=self.request.user, document=document)
        
        context['document'] = document
        context['session'] = session
        context['text'] = document.raw_text
        context['word_count'] = document.word_count
        context['profile_defaults'] = get_profile_defaults(
            preferences.adhd_subtype,
            preferences.sensory_sensitivity,
        )
        
        return context


class AudioTrackListView(APIView):
    """List all active audio tracks, grouped by category."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        tracks = AudioTrack.objects.filter(is_active=True).order_by('sort_order', 'name')
        serializer = AudioTrackSerializer(tracks, many=True)
        
        # Group by category for easier client-side consumption
        data = {"noise": [], "ambient": [], "all": serializer.data}
        for track in serializer.data:
            if track["category"] == "noise":
                data["noise"].append(track)
            else:
                data["ambient"].append(track)
        
        return Response(data)


class TaskListView(APIView):
    """List all tasks for user, or create a new one."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tasks = Task.objects.filter(user=request.user)
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = TaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Auto-assign position: put at top of its column
        task_status = serializer.validated_data.get('status', Task.STATUS_TODO)
        max_pos = Task.objects.filter(user=request.user, status=task_status).count()
        serializer.save(user=request.user, position=max_pos)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def patch(self, request):
        """Batch update: reorder tasks within/between columns.

        Expects: {"tasks": [{"id": 1, "status": "doing", "position": 0}, ...]}
        """
        updates = request.data.get('tasks', [])
        if not updates:
            return Response({"error": "No tasks provided"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate status values before bulk update
        valid_statuses = {s[0] for s in Task.STATUS_CHOICES}
        task_ids = [u.get('id') for u in updates if u.get('id')]
        tasks = {t.id: t for t in Task.objects.filter(user=request.user, id__in=task_ids)}

        for u in updates:
            task = tasks.get(u.get('id'))
            if task:
                if 'status' in u:
                    new_status = u['status']
                    if new_status not in valid_statuses:
                        return Response(
                            {"error": f"Invalid status: {new_status}"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    task.status = new_status
                if 'position' in u:
                    task.position = u['position']

        Task.objects.bulk_update([t for t in tasks.values()], ['status', 'position'])

        # Return updated list
        all_tasks = Task.objects.filter(user=request.user)
        serializer = TaskSerializer(all_tasks, many=True)
        return Response(serializer.data)


class TaskDetailView(APIView):
    """Get, update, or delete a single task."""
    permission_classes = [IsAuthenticated]

    def _get_task(self, user, task_id):
        return get_object_or_404(Task, id=task_id, user=user)

    def get(self, request, task_id):
        task = self._get_task(request.user, task_id)
        serializer = TaskSerializer(task)
        return Response(serializer.data)

    def patch(self, request, task_id):
        task = self._get_task(request.user, task_id)
        serializer = TaskSerializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, task_id):
        task = self._get_task(request.user, task_id)
        task.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class KanbanView(LoginRequiredMixin, TemplateView):
    """Render the full kanban board page (web only)."""
    template_name = "kanban.html"


class NoteListView(APIView):
    """List all active notes for user, or create a new one."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        show_archived = request.query_params.get('archived', '0') == '1'
        notes = Note.objects.filter(user=request.user, is_archived=show_archived)
        serializer = NoteSerializer(notes, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = NoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class NoteDetailView(APIView):
    """Get, update, or delete a single note."""
    permission_classes = [IsAuthenticated]

    def _get_note(self, user, note_id):
        return get_object_or_404(Note, id=note_id, user=user)

    def get(self, request, note_id):
        note = self._get_note(request.user, note_id)
        serializer = NoteSerializer(note)
        return Response(serializer.data)

    def patch(self, request, note_id):
        note = self._get_note(request.user, note_id)
        serializer = NoteSerializer(note, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, note_id):
        note = self._get_note(request.user, note_id)
        note.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotesPageView(LoginRequiredMixin, TemplateView):
    """Render the sticky notes page (web only)."""
    template_name = "notes.html"


class CoworkView(LoginRequiredMixin, TemplateView):
    """Unified co-working workspace (C1-C5 — web only).

    Sidebar-driven layout: background, music, tasks, notes panels
    with a central focus area and video background layer.
    """
    template_name = "cowork.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from config.quotes import get_daily_quote, get_time_greeting
        greeting, emoji = get_time_greeting()
        ctx["greeting_emoji"] = emoji
        ctx["greeting"] = greeting
        ctx["daily_quote"] = get_daily_quote()
        return ctx


class RoomListView(APIView):
    """List my rooms or create a new one."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Show rooms where user is a participant (active or inactive)
        participant_room_ids = RoomParticipant.objects.filter(
            user=request.user
        ).values_list("room_id", flat=True)
        rooms = CoworkRoom.objects.filter(
            id__in=participant_room_ids, is_active=True
        ).order_by("-created_at")
        serializer = CoworkRoomSerializer(rooms, many=True)
        return Response(serializer.data)

    def post(self, request):
        from apps.reader.consumers import generate_room_code

        name = request.data.get("name", "").strip()
        if not name:
            return Response({"error": "Room name required"}, status=status.HTTP_400_BAD_REQUEST)
        if len(name) > 100:
            return Response({"error": "Name too long (max 100)"}, status=status.HTTP_400_BAD_REQUEST)

        # Generate unique code
        for _ in range(10):
            code = generate_room_code()
            if not CoworkRoom.objects.filter(code=code).exists():
                break
        else:
            return Response({"error": "Could not generate unique code"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        room = CoworkRoom.objects.create(name=name, code=code, created_by=request.user)
        # Auto-join creator
        RoomParticipant.objects.create(room=room, user=request.user)

        serializer = CoworkRoomSerializer(room)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RoomJoinView(APIView):
    """Join a room by invite code."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get("code", "").strip().upper()
        if not code:
            return Response({"error": "Room code required"}, status=status.HTTP_400_BAD_REQUEST)

        room = get_object_or_404(CoworkRoom, code=code, is_active=True)

        # Join or re-activate
        participant, created = RoomParticipant.objects.update_or_create(
            room=room,
            user=request.user,
            defaults={"is_active": True},
        )

        serializer = CoworkRoomSerializer(room)
        return Response(serializer.data)


class RoomDetailView(APIView):
    """Get room details + recent messages."""
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        room = get_object_or_404(CoworkRoom, id=room_id, is_active=True)

        # Authorization: verify requesting user is a participant of the room
        if not RoomParticipant.objects.filter(room=room, user=request.user).exists():
            return Response(
                {"error": "You are not a participant of this room."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CoworkRoomSerializer(room)

        # Recent 50 messages
        messages = room.messages.select_related("user").order_by("-created_at")[:50]
        msg_serializer = ChatMessageSerializer(reversed(messages), many=True)

        # Active participants
        participants = room.participants.filter(is_active=True).select_related("user")
        presence = [
            {
                "id": p.user.id,
                "name": p.user.first_name or p.user.email.split("@")[0],
                "email": p.user.email,
            }
            for p in participants
        ]

        return Response({
            "room": serializer.data,
            "messages": msg_serializer.data,
            "presence": presence,
        })


class UserXPView(APIView):
    """Get current XP, level, and recent event history."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        xp, _ = UserXP.objects.get_or_create(user=request.user)
        events = XPEvent.objects.filter(user=request.user).order_by("-created_at")[:20]
        return Response({
            "xp": UserXPSerializer(xp).data,
            "recent_events": XPEventSerializer(events, many=True).data,
        })


class RecordXPEventView(APIView):
    """Record an XP event and update daily stats.
    
    XP amounts are SERVER-COMPUTED based on event_type — the client
    cannot control how much XP is awarded.
    """
    permission_classes = [IsAuthenticated]

    XP_BY_EVENT = {
        "words_read": 10,
        "minutes_read": 10,
        "sprint_completed": 50,
        "daily_streak": 100,
        "chapter_completed": 30,
        "document_completed": 100,
        "highlight_created": 5,
        "flashcard_created": 10,
        "note_created": 10,
        "room_joined": 5,
    }

    def post(self, request):
        serializer = RecordXPEventSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user = request.user
        event_type = data["event_type"]

        # XP amount is server-computed — client cannot self-award
        xp_amount = self.XP_BY_EVENT.get(event_type, 10)

        # Record XP event
        event = XPEvent.objects.create(
            user=user,
            event_type=event_type,
            xp_amount=xp_amount,
            metadata=data.get("metadata", {}),
        )

        # Update UserXP
        xp, _ = UserXP.objects.get_or_create(user=user)
        leveled_up = xp.add_xp(xp_amount)

        # Update daily reading stat atomically
        today = timezone.now().date()
        words = data.get("words_read", 0)
        minutes = data.get("minutes_read", 0)

        from django.db.models import F
        from django.db import IntegrityError

        updated = DailyReadingStat.objects.filter(user=user, date=today).update(
            words_read=F('words_read') + words,
            minutes_read=F('minutes_read') + minutes,
            xp_earned=F('xp_earned') + xp_amount,
            sessions_count=F('sessions_count') + 1,
        )
        if not updated:
            try:
                DailyReadingStat.objects.create(
                    user=user, date=today,
                    words_read=words, minutes_read=minutes,
                    xp_earned=xp_amount, sessions_count=1,
                )
            except IntegrityError:
                DailyReadingStat.objects.filter(user=user, date=today).update(
                    words_read=F('words_read') + words,
                    minutes_read=F('minutes_read') + minutes,
                    xp_earned=F('xp_earned') + xp_amount,
                    sessions_count=F('sessions_count') + 1,
                )

        return Response({
            "event": XPEventSerializer(event).data,
            "xp": UserXPSerializer(xp).data,
            "leveled_up": leveled_up,
        })


class StreakView(APIView):
    """Get streak info and heatmap data for the last 6 months."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()

        # Get all daily stats for last ~180 days
        cutoff = today - timedelta(days=180)
        stats = DailyReadingStat.objects.filter(
            user=user, date__gte=cutoff
        ).order_by("-date")

        # Calculate current streak
        current_streak = 0
        check_date = today
        stat_dates = set(s.date for s in stats)

        # Check if read today
        if today in stat_dates:
            current_streak = 1
            check_date = today - timedelta(days=1)
            while check_date in stat_dates:
                current_streak += 1
                check_date -= timedelta(days=1)
        else:
            # Check if read yesterday (streak might still be alive)
            yesterday = today - timedelta(days=1)
            if yesterday in stat_dates:
                current_streak = 1
                check_date = yesterday - timedelta(days=1)
                while check_date in stat_dates:
                    current_streak += 1
                    check_date -= timedelta(days=1)

        # Calculate longest streak ever
        all_dates = sorted(stat_dates)
        longest_streak = 0
        temp = 0
        prev = None
        for d in all_dates:
            if prev is None:
                temp = 1
            elif (d - prev).days == 1:
                temp += 1
            else:
                longest_streak = max(longest_streak, temp)
                temp = 1
            prev = d
        longest_streak = max(longest_streak, temp)

        # Today's stats
        today_stat = DailyReadingStat.objects.filter(user=user, date=today).first()
        today_words = today_stat.words_read if today_stat else 0
        today_xp = today_stat.xp_earned if today_stat else 0

        # Heatmap: last 180 days as [{date, count}]
        heatmap = []
        for s in stats[:180]:
            # Color intensity based on words_read (0-5 scale)
            intensity = 0
            if s.words_read > 0:
                intensity = 1
            if s.words_read > 500:
                intensity = 2
            if s.words_read > 1500:
                intensity = 3
            if s.words_read > 3000:
                intensity = 4
            if s.words_read > 6000:
                intensity = 5

            heatmap.append({
                "date": s.date.isoformat(),
                "words": s.words_read,
                "intensity": intensity,
                "xp": s.xp_earned,
            })

        return Response({
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "today_words": today_words,
            "today_xp": today_xp,
            "heatmap": heatmap,
        })


class FlashcardDeckListView(APIView):
    """List and create flashcard decks."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        decks = FlashcardDeck.objects.filter(user=request.user)
        serializer = FlashcardDeckSerializer(decks, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = FlashcardDeckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Validate that the linked document belongs to request.user
        document = serializer.validated_data.get('document')
        if document is not None and document.user != request.user:
            return Response(
                {"error": "Document does not belong to you."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            deck = serializer.save(user=request.user)
        except IntegrityError:
            return Response(
                {"error": "A deck with this name already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(FlashcardDeckSerializer(deck).data, status=status.HTTP_201_CREATED)


class FlashcardDeckDetailView(APIView):
    """Get deck details, cards, or delete deck."""
    permission_classes = [IsAuthenticated]

    def get(self, request, deck_id):
        deck = get_object_or_404(FlashcardDeck, id=deck_id, user=request.user)
        cards = deck.cards.all()
        return Response({
            "deck": FlashcardDeckSerializer(deck).data,
            "cards": FlashcardSerializer(cards, many=True).data,
        })

    def delete(self, request, deck_id):
        deck = get_object_or_404(FlashcardDeck, id=deck_id, user=request.user)
        deck.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FlashcardListView(APIView):
    """Create flashcards (typically from highlights)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FlashcardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        deck_id = request.data.get("deck")
        deck = get_object_or_404(FlashcardDeck, id=deck_id, user=request.user)
        card = serializer.save(deck=deck)
        return Response(FlashcardSerializer(card).data, status=status.HTTP_201_CREATED)


class FlashcardDetailView(APIView):
    """Update or delete a single flashcard."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, card_id):
        card = get_object_or_404(Flashcard, id=card_id, deck__user=request.user)

        # Prevent deck reassignment to another user's deck
        if 'deck' in request.data:
            new_deck_id = request.data.get('deck')
            if new_deck_id is not None and str(new_deck_id) != str(card.deck_id):
                if not FlashcardDeck.objects.filter(id=new_deck_id, user=request.user).exists():
                    return Response(
                        {"error": "Target deck does not belong to you."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

        serializer = FlashcardSerializer(card, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, card_id):
        card = get_object_or_404(Flashcard, id=card_id, deck__user=request.user)
        card.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FlashcardReviewView(APIView):
    """Submit a review quality rating and get next due card."""
    permission_classes = [IsAuthenticated]

    def post(self, request, card_id):
        card = get_object_or_404(Flashcard, id=card_id, deck__user=request.user)
        serializer = ReviewFlashcardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        card.schedule_review(serializer.validated_data["quality"])
        return Response(FlashcardSerializer(card).data)

    def get(self, request):
        """Get next due card across all decks."""
        from django.utils import timezone
        card = Flashcard.objects.filter(
            deck__user=request.user,
            next_review__lte=timezone.now()
        ).order_by("next_review").first()

        if not card:
            return Response({"done": True, "message": "All caught up! No cards due for review."})

        return Response({
            "done": False,
            "card": FlashcardSerializer(card).data,
            "deck_name": card.deck.name,
        })


class FlashcardsPageView(TemplateView):
    """The flashcard review SPA page."""
    template_name = "flashcards.html"


class HighlightListView(APIView):
    """List all highlights across documents, or batch-sync from client."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        highlights = Highlight.objects.filter(user=request.user).select_related("document")
        document_id = request.query_params.get("document")
        if document_id:
            try:
                doc_id_int = int(document_id)
            except (ValueError, TypeError):
                return Response(
                    {"error": "Invalid document ID"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            highlights = highlights.filter(document_id=doc_id_int)
        search = request.query_params.get("search", "").strip()
        if search:
            highlights = highlights.filter(
                Q(text__icontains=search) | Q(document__title__icontains=search)
            )
        serializer = HighlightSerializer(highlights[:200], many=True)
        return Response(serializer.data)

    def post(self, request):
        """Batch sync highlights from client localStorage to server."""
        serializer = HighlightSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doc_id = request.data.get("document_id")
        if not doc_id:
            return Response({"error": "document_id required"}, status=400)

        document = get_object_or_404(Document, id=doc_id, user=request.user)

        # Delete existing highlights for this doc, re-create
        Highlight.objects.filter(user=request.user, document=document).delete()

        created = []
        for h in serializer.validated_data["highlights"]:
            start_idx = h.get("startIndex", 0)
            if not isinstance(start_idx, int) or start_idx < 0:
                return Response(
                    {"error": f"startIndex must be a non-negative integer, got {start_idx}"},
                    status=400,
                )
            created.append(Highlight(
                user=request.user,
                document=document,
                text=h.get("text", ""),
                start_index=start_idx,
                color=h.get("color", "#fbbf24"),
            ))

        Highlight.objects.bulk_create(created)
        return Response({"synced": len(created)})


class HighlightJournalView(TemplateView):
    """The highlight journal / notebook page."""
    template_name = "journal.html"


class OutlineView(APIView):
    """Generate a hierarchical outline of a document based on headings and highlights."""
    permission_classes = [IsAuthenticated]

    def get(self, request, document_id):
        document = get_object_or_404(Document, id=document_id, user=request.user)
        text = document.raw_text or ""

        # Extract headings (lines that look like headers)
        lines = text.split("\n")
        headings = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            # Heading heuristics: all caps, short, numbered, or starts with "Chapter/Section/Part"
            is_heading = False
            level = 2
            if stripped.isupper() and len(stripped) < 80:
                is_heading = True
                level = 1
            elif any(stripped.startswith(p) for p in ["Chapter", "Section", "Part", "CHAPTER", "SECTION"]):
                is_heading = True
                level = 1
            elif (stripped[0].isdigit() and "." in stripped[:6]):
                is_heading = True
                level = 2
            elif len(stripped) < 60 and not stripped.endswith("."):
                is_heading = True
                level = 3

            if is_heading:
                headings.append({
                    "text": stripped,
                    "line": i,
                    "level": level,
                    "highlights": [],
                })

        # Get highlights for this document
        highlights = Highlight.objects.filter(
            user=request.user, document=document
        ).order_by("start_index")

        # Map highlights to nearest preceding heading
        for h in highlights:
            # Find which heading this highlight falls under
            assigned = False
            for heading in reversed(headings):
                heading_words = len(text[:text.find(heading["text"])].split()) if heading["text"] in text else 0
                if h.start_index >= heading_words:
                    heading["highlights"].append({
                        "text": h.text[:200],
                        "start_index": h.start_index,
                        "color": h.color,
                    })
                    assigned = True
                    break
            if not assigned and headings:
                headings[0]["highlights"].append({
                    "text": h.text[:200],
                    "start_index": h.start_index,
                    "color": h.color,
                })

        # Remove headings with no highlights (unless they're top-level)
        outline = [h for h in headings if h["highlights"] or h["level"] == 1]

        return Response({
            "document_title": document.title,
            "outline": outline,
            "total_highlights": highlights.count(),
        })


class ExportAnnotatedPDFView(APIView):
    """Export original PDF with highlights and notes appended as new pages."""
    permission_classes = [IsAuthenticated]

    def get(self, request, document_id):
        document = get_object_or_404(Document, id=document_id, user=request.user)

        if document.status != Document.STATUS_READY:
            return Response(
                {"error": "Document is not ready for export."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1. Read original file
        try:
            file_path = storage.get_local_path(document.file_key)
        except Exception as e:
            logger.error("Cannot read file for export, doc %d: %s", document.id, e)
            return Response(
                {"error": "Cannot read original file."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 2. Get highlights for this document
        highlights = document.highlights.all().order_by("start_index")

        # 3. Build merged PDF
        try:
            from io import BytesIO
            from pypdf import PdfReader, PdfWriter
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas as rl_canvas

            writer = PdfWriter()

            # Append original pages
            if document.file_type == Document.FILE_TYPE_PDF:
                reader = PdfReader(file_path)
                for page in reader.pages:
                    writer.add_page(page)
            else:
                # EPUB: create a title page with the extracted text summary
                buf = BytesIO()
                c = rl_canvas.Canvas(buf, pagesize=A4)
                c.setFont("Helvetica-Bold", 18)
                c.drawString(50, 750, document.title)
                c.setFont("Helvetica", 11)
                c.drawString(50, 720, f"EPUB document — {document.word_count} words")
                c.drawString(50, 700, f"Read on Fixate — {document.created_at.strftime('%B %d, %Y')}")
                c.save()
                buf.seek(0)
                epub_reader = PdfReader(buf)
                writer.add_page(epub_reader.pages[0])

                # Add the extracted text pages
                if document.raw_text:
                    text_buf = BytesIO()
                    c2 = rl_canvas.Canvas(text_buf, pagesize=A4)
                    c2.setFont("Helvetica", 10)
                    y = 780
                    for line in document.raw_text.split("\n")[:100]:  # cap at ~2 pages
                        if y < 50:
                            c2.showPage()
                            c2.setFont("Helvetica", 10)
                            y = 780
                        c2.drawString(50, y, line[:120])
                        y -= 14
                    c2.save()
                    text_buf.seek(0)
                    text_reader = PdfReader(text_buf)
                    for page in text_reader.pages:
                        writer.add_page(page)

            # Append highlights appendix page(s)
            if highlights.exists():
                highlights_buf = BytesIO()
                ch = rl_canvas.Canvas(highlights_buf, pagesize=A4)
                ch.setFont("Helvetica-Bold", 16)
                ch.drawString(50, 750, "Your Highlights")
                ch.setFont("Helvetica", 10)
                y = 720
                for i, h in enumerate(highlights, 1):
                    text = h.text[:200]
                    if y < 80:
                        ch.showPage()
                        ch.setFont("Helvetica", 10)
                        y = 780
                    ch.setFont("Helvetica-Bold", 9)
                    ch.drawString(50, y, f"#{i}")
                    ch.setFont("Helvetica", 9)
                    ch.drawString(70, y, text)
                    y -= 20
                ch.save()
                highlights_buf.seek(0)
                h_reader = PdfReader(highlights_buf)
                for page in h_reader.pages:
                    writer.add_page(page)

            # 4. Return merged PDF
            output = BytesIO()
            writer.write(output)
            output.seek(0)

            response = HttpResponse(output.read(), content_type="application/pdf")
            safe_title = "".join(c for c in document.title if c.isalnum() or c in " _-").rstrip()
            response["Content-Disposition"] = f'attachment; filename="fixate-{safe_title or "document"}.pdf"'
            return response

        except ImportError as e:
            logger.error("Missing dependency for PDF export: %s", e)
            return Response(
                {"error": "PDF export is not available. Please contact support."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.error("PDF export failed for doc %d: %s", document.id, e)
            return Response(
                {"error": "PDF export failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
