from django.core.exceptions import ValidationError
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
    FILE_TYPE_EPUB = "epub"
    FILE_TYPE_CHOICES = [
        (FILE_TYPE_PDF, "PDF"),
        (FILE_TYPE_EPUB, "EPUB"),
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
    folder = models.ForeignKey("Folder", on_delete=models.SET_NULL, null=True, blank=True, related_name="documents")
    tags = models.CharField(max_length=500, blank=True, default="", help_text="Comma-separated tags")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["user", "folder"]),
        ]
    
    def __str__(self):
        return f"{self.title} (doc #{self.pk})"

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]


class Figure(models.Model):
    """Extracted figure/image from a PDF document with caption and reference mapping."""
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="figures")
    page_number = models.PositiveIntegerField()
    image = models.ImageField(upload_to="figures/%Y/%m/", max_length=500)
    thumbnail = models.ImageField(upload_to="figures/thumbnails/%Y/%m/", max_length=500, blank=True)
    caption = models.TextField(blank=True, default="", help_text="Detected caption text near the figure")
    figure_number = models.CharField(max_length=20, blank=True, default="", help_text="e.g., '1', '2.3', 'A'")
    reference_text = models.CharField(max_length=100, blank=True, default="", help_text="How it's referenced in text: 'Figure 1', 'Fig. 1'")
    bounding_box = models.JSONField(null=True, blank=True, help_text="{x0, y0, x1, y1} on page")
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "page_number"]
        indexes = [
            models.Index(fields=["document", "page_number"]),
        ]

    def __str__(self):
        label = f"Figure {self.figure_number}" if self.figure_number else f"Page {self.page_number}"
        return f"{label} — {self.document.title}"


class Folder(models.Model):
    """User-created folder for organizing documents. Supports nesting."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="folders")
    name = models.CharField(max_length=100)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children")
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        unique_together = [("user", "name", "parent")]
        indexes = [
            models.Index(fields=["user", "parent"]),
        ]

    def clean(self):
        super().clean()
        # Prevent circular parent references
        if self.parent is None:
            return
        seen = {self.pk} if self.pk else set()
        current = self.parent
        while current is not None:
            if current.pk in seen:
                raise ValidationError({"parent": "Circular folder reference detected."})
            seen.add(current.pk)
            current = current.parent

    def __str__(self):
        path = self.name
        p = self.parent
        while p:
            path = f"{p.name} / {path}"
            p = p.parent
        return path
