from rest_framework import serializers
from apps.reader.models import ReadingSession, UserPreferences, AudioTrack, Task, Note, CoworkRoom, ChatMessage, UserXP, XPEvent, DailyReadingStat, FlashcardDeck, Flashcard, Highlight


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreferences
        fields = [
            'default_mode', 'default_wpm', 'default_font',
            'default_bold_intensity', 'default_chunk_size', 'theme',
            'noise_enabled', 'default_noise_slug',
            'adhd_subtype', 'sensory_sensitivity'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class ReadingSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingSession
        fields = [
            'id', 'document', 'mode', 'wpm', 'bold_intensity',
            'font', 'chunk_size', 'last_position', 'completed',
            'started_at', 'updated_at'
        ]
        read_only_fields = ['id', 'started_at', 'updated_at']


class UpdatePositionSerializer(serializers.Serializer):
    position = serializers.IntegerField(min_value=0)
    completed = serializers.BooleanField(required=False, default=False)


class AudioTrackSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    noise_type_display = serializers.CharField(source='get_noise_type_display', read_only=True)
    tag_list = serializers.ListField(child=serializers.CharField(), read_only=True)

    class Meta:
        model = AudioTrack
        fields = [
            'id', 'name', 'slug', 'category', 'category_display',
            'noise_type', 'noise_type_display', 'audio_url',
            'icon', 'description', 'volume_default', 'tag_list',
        ]


class TaskSerializer(serializers.ModelSerializer):
    priority_color = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'status', 'priority',
            'priority_color', 'position', 'due_date',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_priority_color(self, obj):
        return Task.PRIORITY_COLORS.get(obj.priority, '#6b7280')


class NoteSerializer(serializers.ModelSerializer):
    color_hex = serializers.SerializerMethodField()
    color_border = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = [
            'id', 'title', 'body', 'color', 'color_hex', 'color_border',
            'is_archived', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_color_hex(self, obj):
        return Note.COLOR_HEX.get(obj.color, Note.COLOR_HEX[Note.COLOR_DEFAULT])

    def get_color_border(self, obj):
        return Note.COLOR_BORDER.get(obj.color, Note.COLOR_BORDER[Note.COLOR_DEFAULT])


class CoworkRoomSerializer(serializers.ModelSerializer):
    participant_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CoworkRoom
        fields = [
            'id', 'name', 'code', 'created_by_name', 'participant_count',
            'timer_duration', 'timer_running', 'timer_remaining',
            'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'code', 'created_at']

    def get_participant_count(self, obj):
        return obj.participants.filter(is_active=True).count()

    def get_created_by_name(self, obj):
        return obj.created_by.first_name or obj.created_by.email.split("@")[0]


class ChatMessageSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = ['id', 'user_name', 'content', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_user_name(self, obj):
        return obj.user.first_name or obj.user.email.split("@")[0]


class UserXPSerializer(serializers.ModelSerializer):
    level_progress_pct = serializers.IntegerField(read_only=True)

    class Meta:
        model = UserXP
        fields = [
            'total_xp', 'current_level', 'xp_to_next_level',
            'level_progress_pct',
        ]


class XPEventSerializer(serializers.ModelSerializer):
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)

    class Meta:
        model = XPEvent
        fields = ['id', 'event_type', 'event_type_display', 'xp_amount', 'metadata', 'created_at']
        read_only_fields = ['id', 'created_at']


class RecordXPEventSerializer(serializers.Serializer):
    event_type = serializers.ChoiceField(choices=XPEvent.EVENT_CHOICES)
    xp_amount = serializers.IntegerField(min_value=1, max_value=1000)
    metadata = serializers.JSONField(required=False, default=dict)
    words_read = serializers.IntegerField(required=False, min_value=0, default=0)
    minutes_read = serializers.IntegerField(required=False, min_value=0, default=0)


class DailyReadingStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyReadingStat
        fields = ['date', 'words_read', 'minutes_read', 'xp_earned', 'sessions_count']


class StreakResponseSerializer(serializers.Serializer):
    current_streak = serializers.IntegerField()
    longest_streak = serializers.IntegerField()
    today_words = serializers.IntegerField()
    today_xp = serializers.IntegerField()
    heatmap = serializers.ListField(child=serializers.DictField())


class FlashcardDeckSerializer(serializers.ModelSerializer):
    card_count = serializers.IntegerField(read_only=True)
    due_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = FlashcardDeck
        fields = ['id', 'name', 'document', 'card_count', 'due_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'document', 'created_at', 'updated_at']


class FlashcardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Flashcard
        fields = ['id', 'deck', 'front', 'back', 'source_text', 'source_index',
                  'last_reviewed', 'next_review', 'review_count', 'ease_factor',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'deck', 'ease_factor', 'created_at', 'updated_at', 'last_reviewed', 'next_review', 'review_count']


class ReviewFlashcardSerializer(serializers.Serializer):
    quality = serializers.IntegerField(min_value=0, max_value=5)


class UpdateSessionSerializer(serializers.Serializer):
    """Validate session field updates with proper types and ranges."""
    mode = serializers.ChoiceField(
        choices=ReadingSession.MODE_CHOICES, required=False
    )
    wpm = serializers.IntegerField(min_value=1, max_value=2000, required=False)
    bold_intensity = serializers.FloatField(min_value=0.0, max_value=1.0, required=False)
    font = serializers.CharField(max_length=20, required=False)
    chunk_size = serializers.IntegerField(min_value=1, max_value=50, required=False)


class HighlightSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source='document.title', read_only=True)

    class Meta:
        model = Highlight
        fields = ['id', 'document', 'document_title', 'text', 'start_index', 'color', 'created_at']
        read_only_fields = ['id', 'created_at']


class HighlightSyncSerializer(serializers.Serializer):
    highlights = serializers.ListField(child=serializers.DictField())
