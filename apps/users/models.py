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
    
    def can_use_textract(self):
        if self.tier == self.TIER_PRO:
            return True
        return self.textract_uploads_used < 10
    
    def increment_textract_usage(self):
        if self.tier != self.TIER_PRO:
            self.textract_uploads_used += 1
            self.save(update_fields=["textract_uploads_used"])
