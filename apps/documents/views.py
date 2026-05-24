from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.conf import settings

from apps.documents.models import Document
from apps.documents.serializers import (
    DocumentUploadSerializer,
    DocumentSerializer,
    DocumentDetailSerializer,
    DocumentUploadFileSerializer,
)
from config.backends import storage
from config.backends import ocr


class DocumentUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if settings.FIXATE_MODE == "desktop":
            return self._desktop_upload(request)
        else:
            return self._cloud_upload(request)

    def _cloud_upload(self, request):
        """Existing pre-signed S3 upload flow (unchanged)."""
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        filename = serializer.validated_data["filename"]

        if not request.user.can_use_textract():
            return Response(
                {
                    "error": "You have reached your upload limit. Upgrade to Pro for unlimited uploads."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        upload_data = storage.generate_upload_url(request.user.id, filename)

        document = Document.objects.create(
            user=request.user,
            title=filename.rsplit(".", 1)[0],
            file_key=upload_data["key"],
            file_type=Document.FILE_TYPE_PDF,
            status=Document.STATUS_PENDING,
        )

        return Response(
            {
                "document_id": document.id,
                "upload_url": upload_data["url"],
                "key": upload_data["key"],
                "expires_in": upload_data["expires_in"],
            },
            status=status.HTTP_201_CREATED,
        )

    def _desktop_upload(self, request):
        """Desktop: accept multipart file upload directly, save locally, run OCR sync."""
        serializer = DocumentUploadFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data["file"]
        filename = uploaded_file.name

        # Save file locally
        file_key = storage.save_uploaded_file(
            request.user.id, filename, uploaded_file
        )

        document = Document.objects.create(
            user=request.user,
            title=filename.rsplit(".", 1)[0],
            file_key=file_key,
            file_type=Document.FILE_TYPE_PDF,
            status=Document.STATUS_PROCESSING,
        )

        # Run OCR synchronously
        try:
            file_path = storage.get_local_path(file_key)
            result = ocr.extract_text(file_path)
            document.raw_text = result["text"]
            document.page_count = result["pages"]
            document.word_count = result["word_count"]
            document.status = Document.STATUS_READY
            document.save()
        except Exception as e:
            document.status = Document.STATUS_ERROR
            document.error_message = str(e)
            document.save()

        return Response(
            DocumentSerializer(document).data,
            status=status.HTTP_201_CREATED,
        )


class DocumentConfirmUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, document_id):
        document = get_object_or_404(
            Document, id=document_id, user=request.user
        )

        if document.status != Document.STATUS_PENDING:
            return Response(
                {
                    "error": "Document is already being processed or has been processed."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        document.status = Document.STATUS_PROCESSING
        document.save()

        from config.backends.tasks import process_document_async

        process_document_async(document.id)

        return Response({"status": "processing"})


class DocumentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, document_id):
        document = get_object_or_404(
            Document, id=document_id, user=request.user
        )

        return Response(
            {
                "status": document.status,
                "page_count": document.page_count,
                "word_count": document.word_count,
                "error_message": document.error_message,
            }
        )


class DocumentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        documents = Document.objects.filter(user=request.user)
        serializer = DocumentSerializer(documents, many=True)
        return Response(serializer.data)


class DocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, document_id):
        document = get_object_or_404(
            Document, id=document_id, user=request.user
        )
        serializer = DocumentDetailSerializer(document)
        return Response(serializer.data)

    def delete(self, request, document_id):
        document = get_object_or_404(
            Document, id=document_id, user=request.user
        )

        try:
            storage.delete_file(document.file_key)
        except Exception:
            pass

        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
