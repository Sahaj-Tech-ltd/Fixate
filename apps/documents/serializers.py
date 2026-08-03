from rest_framework import serializers
from apps.documents.models import Document, Figure, Folder


class DocumentUploadSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=255)
    file_size = serializers.IntegerField(min_value=1, max_value=50 * 1024 * 1024)

    def validate_filename(self, value):
        if not (value.lower().endswith(".pdf") or value.lower().endswith(".epub")):
            raise serializers.ValidationError("Only PDF and EPUB files are supported.")
        return value


class DocumentUploadFileSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        name = value.name.lower()
        if not (name.endswith(".pdf") or name.endswith(".epub")):
            raise serializers.ValidationError("Only PDF and EPUB files are supported.")
        if value.size > 50 * 1024 * 1024:
            raise serializers.ValidationError("File size must be under 50MB.")
        return value


class DocumentSerializer(serializers.ModelSerializer):
    figure_count = serializers.SerializerMethodField()
    reading_stats = serializers.SerializerMethodField()
    error = serializers.CharField(source='error_message', read_only=True)

    class Meta:
        model = Document
        fields = [
            "id", "title", "file_type", "status",
            "page_count", "word_count", "figure_count",
            "reading_stats", "error",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "page_count", "word_count",
            "figure_count", "reading_stats", "error", "created_at", "updated_at",
        ]

    def get_figure_count(self, obj):
        return getattr(obj, '_figure_count', obj.figures.count())

    def get_reading_stats(self, obj):
        session = obj.sessions.order_by('-updated_at').first()
        if not session:
            return None
        duration = None
        if session.started_at and session.updated_at:
            delta = (session.updated_at - session.started_at).total_seconds()
            if delta > 0:
                duration = round(delta / 60, 1)  # minutes
        progress = 0
        if obj.word_count > 0:
            progress = min(100, round((session.last_position / obj.word_count) * 100))
        return {
            "wpm": session.wpm,
            "duration_minutes": duration,
            "progress_pct": progress,
            "mode": session.mode,
        }


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


class FigureSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Figure
        fields = [
            "id", "page_number", "figure_number", "reference_text",
            "caption", "width", "height", "sort_order",
            "image_url", "thumbnail_url",
        ]

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            return obj.thumbnail.url
        return None


class FolderSerializer(serializers.ModelSerializer):
    document_count = serializers.SerializerMethodField()

    class Meta:
        model = Folder
        fields = ['id', 'name', 'parent', 'document_count', 'sort_order', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']

    def validate_parent(self, value):
        """Ensure parent folder belongs to the same user."""
        if value is not None:
            request = self.context.get('request')
            if request and hasattr(request, 'user'):
                if value.user != request.user:
                    raise serializers.ValidationError(
                        "Parent folder does not exist."
                    )
        return value

    def get_document_count(self, obj):
        return obj.documents.count()


class DocumentMoveSerializer(serializers.Serializer):
    folder_id = serializers.IntegerField(required=False, allow_null=True)
    tags = serializers.CharField(required=False, allow_blank=True, max_length=500)
