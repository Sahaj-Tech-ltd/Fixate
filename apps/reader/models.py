from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings

from apps.documents.models import Document


class UserPreferences(models.Model):
    # Font choices auto-generated from config/fonts.py — single source of truth
    @classmethod
    def _font_choices(cls):
        from config.fonts import get_font_choices
        return get_font_choices()
    
    MODE_RSVP = "rsvp"
    MODE_BIONIC = "bionic"
    MODE_CHOICES = [
        (MODE_RSVP, "RSVP"),
        (MODE_BIONIC, "Bionic"),
    ]

    THEME_DARK = "dark"
    THEME_LIGHT = "light"
    THEME_SEPIA = "sepia"
    THEME_HIGH_CONTRAST = "high-contrast"
    THEME_DYSLEXIA = "dyslexia"
    THEME_LOW_STIM = "low-stim"
    THEME_WARM_NIGHT = "warm-night"
    THEME_COOL_FOCUS = "cool-focus"
    THEME_SOLARIZED_DARK = "solarized-dark"
    THEME_SOLARIZED_LIGHT = "solarized-light"
    THEME_CATPPUCCIN_MOCHA = "catppuccin-mocha"
    THEME_CATPPUCCIN_LATTE = "catppuccin-latte"
    THEME_GRUVBOX_DARK = "gruvbox-dark"
    THEME_GRUVBOX_LIGHT = "gruvbox-light"
    THEME_NORD = "nord"
    THEME_DRACULA = "dracula"
    THEME_EVERFOREST = "everforest"
    THEME_TOKYO_NIGHT = "tokyo-night"
    THEME_CHOICES = [
        (THEME_DARK, "Dark"),
        (THEME_LIGHT, "Light"),
        (THEME_SEPIA, "Sepia"),
        (THEME_HIGH_CONTRAST, "High Contrast"),
        (THEME_DYSLEXIA, "Dyslexia-Friendly"),
        (THEME_LOW_STIM, "Low Stimulation"),
        (THEME_WARM_NIGHT, "Warm Night"),
        (THEME_COOL_FOCUS, "Cool Focus"),
        (THEME_SOLARIZED_DARK, "Solarized Dark"),
        (THEME_SOLARIZED_LIGHT, "Solarized Light"),
        (THEME_CATPPUCCIN_MOCHA, "Catppuccin Mocha"),
        (THEME_CATPPUCCIN_LATTE, "Catppuccin Latte"),
        (THEME_GRUVBOX_DARK, "Gruvbox Dark"),
        (THEME_GRUVBOX_LIGHT, "Gruvbox Light"),
        (THEME_NORD, "Nord"),
        (THEME_DRACULA, "Dracula"),
        (THEME_EVERFOREST, "Everforest"),
        (THEME_TOKYO_NIGHT, "Tokyo Night"),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preferences")
    default_mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_RSVP)
    default_wpm = models.PositiveIntegerField(default=300)
    default_font = models.CharField(max_length=20, choices=(), default="inter")
    default_bold_intensity = models.FloatField(default=0.5)
    default_chunk_size = models.PositiveIntegerField(default=1)
    theme = models.CharField(max_length=30, choices=THEME_CHOICES, default=THEME_DARK)
    noise_enabled = models.BooleanField(default=True, help_text="Auto-play background noise when reading")
    default_noise_slug = models.CharField(max_length=100, blank=True, default="pink-noise", help_text="Default noise track slug")
    
    # ADHD Profile — per-type adaptation
    ADHD_NONE = "none"
    ADHD_INATTENTIVE = "inattentive"
    ADHD_HYPERACTIVE = "hyperactive"
    ADHD_COMBINED = "combined"
    ADHD_SUBTYPE_CHOICES = [
        (ADHD_NONE, "No ADHD / Prefer not to say"),
        (ADHD_INATTENTIVE, "ADHD — Inattentive (easily distracted, lose focus)"),
        (ADHD_HYPERACTIVE, "ADHD — Hyperactive (restless, fidgety)"),
        (ADHD_COMBINED, "ADHD — Combined (both)"),
    ]
    
    SENSORY_LOW = "low"
    SENSORY_MEDIUM = "medium"
    SENSORY_HIGH = "high"
    SENSORY_SENSITIVITY_CHOICES = [
        (SENSORY_LOW, "Low — loud/bright is fine"),
        (SENSORY_MEDIUM, "Medium — average sensitivity"),
        (SENSORY_HIGH, "High — easily overstimulated"),
    ]
    
    adhd_subtype = models.CharField(max_length=12, choices=ADHD_SUBTYPE_CHOICES, default=ADHD_NONE, help_text="Used for per-type noise and focus adaptation")
    sensory_sensitivity = models.CharField(max_length=6, choices=SENSORY_SENSITIVITY_CHOICES, default=SENSORY_MEDIUM, help_text="Affects noise volume, nudge intensity, and theme defaults")
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(default_wpm__gte=1) & models.Q(default_wpm__lte=2000),
                name="userprefs_wpm_range",
            ),
            models.CheckConstraint(
                condition=models.Q(default_bold_intensity__gte=0.0) & models.Q(default_bold_intensity__lte=1.0),
                name="userprefs_bold_intensity_range",
            ),
            models.CheckConstraint(
                condition=models.Q(default_chunk_size__gte=1) & models.Q(default_chunk_size__lte=50),
                name="userprefs_chunk_size_range",
            ),
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Patch choices at runtime from the registry
        self._meta.get_field('default_font').choices = self._font_choices()
    
    def clean(self):
        super().clean()
        errors = {}
        if not (1 <= self.default_wpm <= 2000):
            errors["default_wpm"] = "WPM must be between 1 and 2000."
        if not (0.0 <= self.default_bold_intensity <= 1.0):
            errors["default_bold_intensity"] = "Bold intensity must be between 0.0 and 1.0."
        if not (1 <= self.default_chunk_size <= 50):
            errors["default_chunk_size"] = "Chunk size must be between 1 and 50."
        if errors:
            raise ValidationError(errors)
    
    def __str__(self):
        return f"Preferences for {self.user.display_name}"


class ReadingSession(models.Model):
    MODE_RSVP = "rsvp"
    MODE_BIONIC = "bionic"
    MODE_CHOICES = [
        (MODE_RSVP, "RSVP"),
        (MODE_BIONIC, "Bionic"),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reading_sessions")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="sessions")
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_RSVP)
    wpm = models.PositiveIntegerField(default=300)
    bold_intensity = models.FloatField(default=0.5)
    font = models.CharField(max_length=20, default="inter")
    chunk_size = models.PositiveIntegerField(default=1)
    last_position = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "document"]),
            models.Index(fields=["user", "started_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(wpm__gte=1) & models.Q(wpm__lte=2000),
                name="readingsession_wpm_range",
            ),
            models.CheckConstraint(
                condition=models.Q(bold_intensity__gte=0.0) & models.Q(bold_intensity__lte=1.0),
                name="readingsession_bold_intensity_range",
            ),
        ]
    
    def clean(self):
        super().clean()
        errors = {}
        if not (1 <= self.wpm <= 2000):
            errors["wpm"] = "WPM must be between 1 and 2000."
        if not (0.0 <= self.bold_intensity <= 1.0):
            errors["bold_intensity"] = "Bold intensity must be between 0.0 and 1.0."
        if errors:
            raise ValidationError(errors)
    
    def __str__(self):
        return f"{self.user.display_name} - {self.document.title}"


class AudioTrack(models.Model):
    """Noise and ambient soundscape tracks for focus enhancement.

    Two categories:
      - 'noise': Generated client-side via Web Audio API (white, pink, brown).
        No audio file needed. audio_url is null.
      - 'ambient': Streamed from server/CDN. audio_url points to a hosted file.
    """
    CATEGORY_NOISE = "noise"
    CATEGORY_AMBIENT = "ambient"
    CATEGORY_CHOICES = [
        (CATEGORY_NOISE, "Color Noise"),
        (CATEGORY_AMBIENT, "Ambient Soundscape"),
    ]

    NOISE_WHITE = "white"
    NOISE_PINK = "pink"
    NOISE_BROWN = "brown"
    NOISE_TYPE_CHOICES = [
        (NOISE_WHITE, "White Noise"),
        (NOISE_PINK, "Pink Noise"),
        (NOISE_BROWN, "Brown Noise"),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default=CATEGORY_NOISE)
    noise_type = models.CharField(max_length=10, choices=NOISE_TYPE_CHOICES, null=True, blank=True)
    audio_url = models.URLField(max_length=500, null=True, blank=True, help_text="CDN URL for ambient tracks. Null for generated noise.")
    icon = models.CharField(max_length=10, default="🔊", help_text="Emoji icon for the UI")
    description = models.TextField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    volume_default = models.FloatField(default=0.5, help_text="Default volume 0.0-1.0")
    tags = models.CharField(max_length=200, blank=True, help_text="Comma-separated: adhd-i,adhd-c,focus,calm")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        indexes = [
            models.Index(fields=["category", "is_active"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(volume_default__gte=0.0) & models.Q(volume_default__lte=1.0),
                name="audiotrack_volume_default_range",
            ),
        ]

    def clean(self):
        super().clean()
        if not (0.0 <= self.volume_default <= 1.0):
            raise ValidationError({"volume_default": "Volume must be between 0.0 and 1.0."})

    def __str__(self):
        return f"{self.icon} {self.name}"

    @property
    def is_generated(self):
        """True if this track is generated client-side (no audio file needed)."""
        return self.category == self.CATEGORY_NOISE

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]

class Task(models.Model):
    """Kanban task for the co-working task board (C3 — web only).

    Simple three-column kanban: To Do, Doing, Done.
    Tasks are ordered by position within each column.
    """

    STATUS_TODO = "todo"
    STATUS_DOING = "doing"
    STATUS_DONE = "done"
    STATUS_CHOICES = [
        (STATUS_TODO, "To Do"),
        (STATUS_DOING, "Doing"),
        (STATUS_DONE, "Done"),
    ]

    PRIORITY_HIGH = "high"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_LOW = "low"
    PRIORITY_CHOICES = [
        (PRIORITY_HIGH, "High"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_LOW, "Low"),
    ]

    PRIORITY_COLORS = {
        PRIORITY_HIGH: "#ef4444",
        PRIORITY_MEDIUM: "#f59e0b",
        PRIORITY_LOW: "#6b7280",
    }

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_TODO, db_index=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    position = models.IntegerField(default=0, help_text="Order within the column (lower = top)")
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "position", "-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "status", "position"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(position__gte=0),
                name="task_position_non_negative",
            ),
        ]

    def clean(self):
        super().clean()
        if self.position < 0:
            raise ValidationError({"position": "Position must be non-negative."})

    def __str__(self):
        return self.title


class Note(models.Model):
    """Quick sticky-note style notes for the co-working suite (C4 — web only).

    Color-coded like physical sticky notes. Simple title + body with archive support.
    """

    COLOR_YELLOW = "yellow"
    COLOR_BLUE = "blue"
    COLOR_GREEN = "green"
    COLOR_PINK = "pink"
    COLOR_PURPLE = "purple"
    COLOR_DEFAULT = "default"
    COLOR_CHOICES = [
        (COLOR_DEFAULT, "Default"),
        (COLOR_YELLOW, "Yellow"),
        (COLOR_BLUE, "Blue"),
        (COLOR_GREEN, "Green"),
        (COLOR_PINK, "Pink"),
        (COLOR_PURPLE, "Purple"),
    ]

    COLOR_HEX = {
        COLOR_DEFAULT: "#1e1e24",
        COLOR_YELLOW: "#3d3520",
        COLOR_BLUE: "#1e2d3d",
        COLOR_GREEN: "#1e3d2d",
        COLOR_PINK: "#3d1e2d",
        COLOR_PURPLE: "#2d1e3d",
    }

    COLOR_BORDER = {
        COLOR_DEFAULT: "#2a2a2a",
        COLOR_YELLOW: "#5a4a20",
        COLOR_BLUE: "#2a3d5a",
        COLOR_GREEN: "#2a4a3d",
        COLOR_PINK: "#5a2a3d",
        COLOR_PURPLE: "#3d2a5a",
    }

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notes")
    title = models.CharField(max_length=200, blank=True, default="")
    body = models.TextField(blank=True, default="")
    color = models.CharField(max_length=10, choices=COLOR_CHOICES, default=COLOR_DEFAULT)
    is_archived = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "is_archived"]),
            models.Index(fields=["user", "-updated_at"]),
        ]

    def __str__(self):
        return self.title or self.body[:60]


class CoworkRoom(models.Model):
    """Real-time co-working room (C6 — WebSocket).

    Each room has a unique 6-char invite code. Timer state is synced
    across all participants via WebSocket.
    """

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=6, unique=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_rooms")
    timer_duration = models.PositiveIntegerField(default=25 * 60, help_text="Default timer in seconds (25 min)")
    timer_running = models.BooleanField(default=False)
    timer_started_at = models.DateTimeField(null=True, blank=True)
    timer_remaining = models.PositiveIntegerField(default=25 * 60, help_text="Remaining seconds when paused")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class RoomParticipant(models.Model):
    """Tracks who is in a room and their last ping for presence."""

    room = models.ForeignKey(CoworkRoom, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_ping = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("room", "user")]
        indexes = [
            models.Index(fields=["room", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user.display_name} in {self.room.code}"


class ChatMessage(models.Model):
    """A single chat message in a co-working room."""

    room = models.ForeignKey(CoworkRoom, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["room", "created_at"]),
        ]

    def __str__(self):
        return f"Message {self.id} in room {self.room.code}"


class UserXP(models.Model):
    """Per-user XP and level tracking for gamification.
    
    Level thresholds (XP required):
      L1: 0, L2: 100, L3: 250, L4: 500, L5: 1,000,
      L6: 2,000, L7: 4,000, L8: 8,000, L9: 16,000, L10: 32,000
    """

    LEVEL_THRESHOLDS = [0, 100, 250, 500, 1000, 2000, 4000, 8000, 16000, 32000]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="xp")
    total_xp = models.PositiveIntegerField(default=0)
    current_level = models.PositiveIntegerField(default=1)
    xp_to_next_level = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User XP"
        verbose_name_plural = "User XP"

    def __str__(self):
        return f"{self.user.display_name} — Lv.{self.current_level} ({self.total_xp} XP)"

    def add_xp(self, amount):
        """Add XP atomically, recalculate level, return whether a level-up occurred."""
        from django.db import transaction

        with transaction.atomic():
            xp = UserXP.objects.select_for_update().get(pk=self.pk)
            old_level = xp.current_level
            xp.total_xp += amount
            for i, threshold in enumerate(self.LEVEL_THRESHOLDS):
                if xp.total_xp >= threshold:
                    xp.current_level = i + 1
            next_idx = xp.current_level
            if next_idx < len(self.LEVEL_THRESHOLDS):
                xp.xp_to_next_level = self.LEVEL_THRESHOLDS[next_idx] - xp.total_xp
            else:
                xp.xp_to_next_level = 0
            xp.save()
            # Sync back to instance for caller
            self.total_xp = xp.total_xp
            self.current_level = xp.current_level
            self.xp_to_next_level = xp.xp_to_next_level
            return xp.current_level > old_level

    @property
    def level_progress_pct(self):
        """Progress through current level as 0-100 percentage."""
        if self.current_level >= len(self.LEVEL_THRESHOLDS):
            return 100
        current_threshold = self.LEVEL_THRESHOLDS[self.current_level - 1]
        next_threshold = self.LEVEL_THRESHOLDS[self.current_level]
        level_xp = self.total_xp - current_threshold
        level_width = next_threshold - current_threshold
        return min(100, round((level_xp / level_width) * 100))


class XPEvent(models.Model):
    """Individual XP-earning events for history display."""

    EVENT_WORDS = "words_read"
    EVENT_SPRINT = "sprint_complete"
    EVENT_STREAK = "streak_bonus"
    EVENT_DAILY_GOAL = "daily_goal"
    EVENT_CHOICES = [
        (EVENT_WORDS, "Words Read"),
        (EVENT_SPRINT, "Sprint Complete"),
        (EVENT_STREAK, "Streak Bonus"),
        (EVENT_DAILY_GOAL, "Daily Goal"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="xp_events")
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    xp_amount = models.PositiveIntegerField()
    metadata = models.JSONField(default=dict, blank=True, help_text="e.g., {'words': 250, 'document_id': 5}")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "event_type"]),
        ]

    def __str__(self):
        return f"{self.user.display_name} +{self.xp_amount} XP ({self.get_event_type_display()})"


class DailyReadingStat(models.Model):
    """Per-day reading stats for streak tracking and heat map."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="daily_stats")
    date = models.DateField(db_index=True)
    words_read = models.PositiveIntegerField(default=0)
    minutes_read = models.PositiveIntegerField(default=0, help_text="Estimated reading minutes")
    xp_earned = models.PositiveIntegerField(default=0)
    sessions_count = models.PositiveIntegerField(default=1, help_text="Number of reading sessions that day")

    class Meta:
        unique_together = [("user", "date")]
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["user", "-date"]),
        ]

    def __str__(self):
        return f"{self.user.display_name} — {self.date}: {self.words_read} words"


class FlashcardDeck(models.Model):
    """A collection of flashcards — typically per document or per topic."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="decks")
    name = models.CharField(max_length=200)
    document = models.ForeignKey("documents.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="decks")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = [("user", "name")]

    def __str__(self):
        return f"{self.name} ({self.user.display_name})"

    @property
    def card_count(self):
        return self.cards.count()

    @property
    def due_count(self):
        """Cards due for review (next_review <= now)."""
        from django.utils import timezone
        return self.cards.filter(next_review__lte=timezone.now()).count()


class Flashcard(models.Model):
    """A single flashcard created from a highlight or manually."""
    deck = models.ForeignKey(FlashcardDeck, on_delete=models.CASCADE, related_name="cards")
    front = models.TextField(help_text="Question, prompt, or highlighted text")
    back = models.TextField(blank=True, default="", help_text="Answer, definition, or notes")
    source_text = models.TextField(blank=True, default="", help_text="Original highlighted passage")
    source_index = models.PositiveIntegerField(default=0, help_text="Word index in source document")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_reviewed = models.DateTimeField(null=True, blank=True)
    next_review = models.DateTimeField(null=True, blank=True, help_text="Next scheduled review (spaced repetition)")
    review_count = models.PositiveIntegerField(default=0)
    ease_factor = models.FloatField(default=2.5, help_text="Spaced repetition ease factor (2.5 = default)")

    class Meta:
        ordering = ["next_review", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ease_factor__gte=1.3),
                name="flashcard_ease_factor_min",
            ),
        ]

    def clean(self):
        super().clean()
        if self.ease_factor < 1.3:
            raise ValidationError({"ease_factor": "Ease factor must be at least 1.3."})

    def __str__(self):
        preview = self.front[:60]
        return f"{preview}..."

    def schedule_review(self, quality):
        """Spaced repetition with atomic locking to prevent concurrent update races."""
        from django.db import transaction
        from django.utils import timezone

        with transaction.atomic():
            card = Flashcard.objects.select_for_update().get(pk=self.pk)

            if quality >= 3:
                if card.review_count == 0:
                    interval = 1
                elif card.review_count == 1:
                    interval = 3
                elif card.review_count == 2:
                    interval = 7
                else:
                    interval = round(card.review_count * 7 * card.ease_factor)
                card.ease_factor = max(1.3, card.ease_factor + (0.1 - (3 - quality) * (0.08 + (3 - quality) * 0.02)))
            else:
                interval = 1
                card.ease_factor = max(1.3, card.ease_factor - 0.2)

            card.review_count += 1
            card.last_reviewed = timezone.now()
            card.next_review = timezone.now() + timezone.timedelta(days=interval)
            card.save()
            # Sync back to instance for caller
            self.review_count = card.review_count
            self.ease_factor = card.ease_factor
            self.last_reviewed = card.last_reviewed
            self.next_review = card.next_review

class Highlight(models.Model):
    """Persistent cross-document highlight storage. Synced from client-side localStorage."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="highlights")
    document = models.ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="highlights")
    text = models.TextField()
    start_index = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=20, default="#fbbf24")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document", "start_index"]
        indexes = [
            models.Index(fields=["user", "document"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return self.text[:80]
