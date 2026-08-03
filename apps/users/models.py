from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    TIER_FREE = "free"
    TIER_PRO = "pro"
    TIER_CHOICES = [
        (TIER_FREE, "Free"),
        (TIER_PRO, "Pro"),
    ]
    
    username = None
    email = models.EmailField("email address", unique=True)
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default=TIER_FREE)
    textract_uploads_used = models.PositiveIntegerField(default=0)
    
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    
    def __str__(self):
        return self.email
    
    @property
    def display_name(self):
        """Display-safe name that doesn't leak email in logs."""
        if self.first_name:
            return self.first_name
        return f"User {self.pk}"
    
    def can_use_textract(self):
        return True
    
    def increment_textract_usage(self):
        pass
