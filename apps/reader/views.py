from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404

from apps.documents.models import Document
from apps.reader.models import ReadingSession, UserPreferences
from apps.reader.serializers import (
    UserPreferencesSerializer,
    ReadingSessionSerializer,
    UpdatePositionSerializer,
)


class UserPreferencesView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
        serializer = UserPreferencesSerializer(preferences)
        return Response(serializer.data)
    
    def patch(self, request):
        preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
        serializer = UserPreferencesSerializer(preferences, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class StartReadingView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, document_id):
        document = get_object_or_404(Document, id=document_id, user=request.user)
        
        if document.status != Document.STATUS_READY:
            return Response(
                {'error': 'Document is not ready for reading'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
        
        from django.db import IntegrityError

        try:
            session, created = ReadingSession.objects.get_or_create(
                user=request.user,
                document=document,
                defaults={
                    'mode': preferences.default_mode,
                    'wpm': preferences.default_wpm,
                    'bold_intensity': preferences.default_bold_intensity,
                    'font': preferences.default_font,
                    'chunk_size': preferences.default_chunk_size,
                }
            )
        except IntegrityError:
            session = ReadingSession.objects.get(user=request.user, document=document)
        
        return Response({
            'session': ReadingSessionSerializer(session).data,
            'text': document.raw_text,
            'word_count': document.word_count,
        })


class UpdateSessionView(APIView):
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, session_id):
        session = get_object_or_404(ReadingSession, id=session_id, user=request.user)
        
        if 'position' in request.data:
            serializer = UpdatePositionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            session.last_position = serializer.validated_data['position']
            session.completed = serializer.validated_data.get('completed', False)
        
        for field in ['mode', 'wpm', 'bold_intensity', 'font', 'chunk_size']:
            if field in request.data:
                setattr(session, field, request.data[field])
        
        session.save()
        return Response(ReadingSessionSerializer(session).data)


class DocumentTextView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, document_id):
        document = get_object_or_404(Document, id=document_id, user=request.user)
        
        if document.status != Document.STATUS_READY:
            return Response(
                {'error': 'Document is not ready'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'text': document.raw_text,
            'word_count': document.word_count,
        })


class ReaderView(LoginRequiredMixin, TemplateView):
    template_name = "reader.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        document_id = kwargs.get('document_id')
        document = get_object_or_404(Document, id=document_id, user=self.request.user)
        
        if document.status != Document.STATUS_READY:
            context['error'] = 'Document is not ready for reading'
            return context
        
        preferences, _ = UserPreferences.objects.get_or_create(user=self.request.user)
        
        from django.db import IntegrityError

        try:
            session, created = ReadingSession.objects.get_or_create(
                user=self.request.user,
                document=document,
                defaults={
                    'mode': preferences.default_mode,
                    'wpm': preferences.default_wpm,
                    'bold_intensity': preferences.default_bold_intensity,
                    'font': preferences.default_font,
                    'chunk_size': preferences.default_chunk_size,
                }
            )
        except IntegrityError:
            session = ReadingSession.objects.get(user=self.request.user, document=document)
        
        context['document'] = document
        context['session'] = session
        context['text'] = document.raw_text
        context['word_count'] = document.word_count
        
        return context
