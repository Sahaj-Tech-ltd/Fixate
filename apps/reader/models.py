from django.db import models
from django.conf import settings

from apps.documents.models import Document


class UserPreferences(models.Model):
    FONT_INTER = "inter"
    FONT_OPENDYSLEXIC = "opendyslexic"
    FONT_SYSTEM = "system"
    FONT_CHOICES = [
        (FONT_INTER, "Inter"),
        (FONT_OPENDYSLEXIC, "OpenDyslexic"),
        (FONT_SYSTEM, "System"),
    ]
    
    THEME_LIGHT = "light"
    THEME_DARK = "dark"
    THEME_SEPIA = "sepia"
    THEME_CHOICES = [
        (THEME_LIGHT, "Light"),
        (THEME_DARK, "Dark"),
        (THEME_SEPIA, "Sepia"),
    ]
    
    MODE_RSVP = "rsvp"
    MODE_BIONIC = "bionic"
    MODE_CHOICES = [
        (MODE_RSVP, "RSVP"),
        (MODE_BIONIC, "Bionic"),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preferences")
    default_mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_RSVP)
    default_wpm = models.PositiveIntegerField(default=300)
    default_font = models.CharField(max_length=20, choices=FONT_CHOICES, default=FONT_INTER)
    default_bold_intensity = models.FloatField(default=0.5)
    default_chunk_size = models.PositiveIntegerField(default=1)
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default=THEME_DARK)
    
    def __str__(self):
        return f"Preferences for {self.user.email}"


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
    
    def __str__(self):
        return f"{self.user.email} - {self.document.title}"
