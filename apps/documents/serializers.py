from rest_framework import serializers
from apps.documents.models import Document


class DocumentUploadSerializer(serializers.Serializer):
    """Cloud mode: expects filename and file_size for pre-signed S3 upload."""
    filename = serializers.CharField(max_length=255)
    file_size = serializers.IntegerField(min_value=1, max_value=50 * 1024 * 1024)  # 50MB max

    def validate_filename(self, value):
        if not value.lower().endswith(".pdf"):
            raise serializers.ValidationError("Only PDF files are supported.")
        return value


class DocumentUploadFileSerializer(serializers.Serializer):
    """Desktop mode: accepts the actual PDF file via multipart upload."""
    file = serializers.FileField()

    def validate_file(self, value):
        if not value.name.lower().endswith(".pdf"):
            raise serializers.ValidationError("Only PDF files are supported.")
        if value.size > 50 * 1024 * 1024:
            raise serializers.ValidationError("File size must be under 50MB.")
        return value


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id", "title", "file_type", "status",
            "page_count", "word_count", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "page_count", "word_count",
            "created_at", "updated_at",
        ]


class DocumentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id", "title", "file_type", "status",
            "page_count", "word_count", "raw_text",
            "created_at", "updated_at", "error_message",
        ]
        read_only_fields = [
            "id", "status", "page_count", "word_count",
            "raw_text", "created_at", "updated_at", "error_message",
        ]
