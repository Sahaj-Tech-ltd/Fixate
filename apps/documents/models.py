from django.db import models
from django.conf import settings


class Document(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_READY = "ready"
    STATUS_ERROR = "error"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_READY, "Ready"),
        (STATUS_ERROR, "Error"),
    ]
    
    FILE_TYPE_PDF = "pdf"
    FILE_TYPE_CHOICES = [
        (FILE_TYPE_PDF, "PDF"),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=255)
    file_key = models.CharField(max_length=500)
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, default=FILE_TYPE_PDF)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    raw_text = models.TextField(blank=True, default="")
    page_count = models.PositiveIntegerField(default=0)
    word_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "created_at"]),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.user.email})"
