from rest_framework import serializers
from apps.reader.models import ReadingSession, UserPreferences


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreferences
        fields = [
            'default_mode', 'default_wpm', 'default_font',
            'default_bold_intensity', 'default_chunk_size', 'theme'
        ]


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
