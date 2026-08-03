import logging
import os

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import models
from django.db import transaction
from django.conf import settings
from django.http import HttpResponse
from django.views import View

from apps.documents.models import Document, Folder
from apps.documents.serializers import (
    DocumentUploadSerializer,
    DocumentSerializer,
    DocumentDetailSerializer,
    DocumentUploadFileSerializer,
    FigureSerializer,
    FolderSerializer,
    DocumentMoveSerializer,
)
from config.backends import storage
from config.backends import ocr

logger = logging.getLogger(__name__)

# 50MB upload limit
MAX_UPLOAD_SIZE = 50 * 1024 * 1024


class DocumentUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if settings.FIXATE_MODE == "desktop":
            return self._desktop_upload(request)
        else:
            return self._cloud_upload(request)

    def _cloud_upload(self, request):
        """Cloud upload — uses presigned URL flow (S3 or local)."""
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        filename = serializer.validated_data["filename"]
        is_epub = filename.lower().endswith(".epub")
        file_type = Document.FILE_TYPE_EPUB if is_epub else Document.FILE_TYPE_PDF

        # Atomically check and increment textract usage
        if not is_epub:
            with transaction.atomic():
                from apps.users.models import User
                user = User.objects.select_for_update().get(pk=request.user.pk)
                if not user.can_use_textract():
                    return Response(
                        {
                            "error": "You have reached your upload limit. Upgrade to Pro for unlimited uploads."
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
                user.increment_textract_usage()

        upload_data = storage.generate_upload_url(request.user.id, filename)

        document = Document.objects.create(
            user=request.user,
            title=filename.rsplit(".", 1)[0],
            file_key=upload_data["key"],
            file_type=file_type,
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
        # Check file size before reading entire body
        content_length = request.META.get("CONTENT_LENGTH")
        if content_length:
            try:
                if int(content_length) > MAX_UPLOAD_SIZE:
                    return Response(
                        {"error": f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)}MB."},
                        status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    )
            except (ValueError, TypeError):
                pass

        serializer = DocumentUploadFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data["file"]
        filename = uploaded_file.name

        # Detect file type from extension
        is_epub = filename.lower().endswith(".epub")
        file_type = Document.FILE_TYPE_EPUB if is_epub else Document.FILE_TYPE_PDF

        # Save file locally
        file_key = storage.save_uploaded_file(
            request.user.id, filename, uploaded_file
        )

        document = Document.objects.create(
            user=request.user,
            title=filename.rsplit(".", 1)[0],
            file_key=file_key,
            file_type=file_type,
            status=Document.STATUS_PROCESSING,
        )

        # Process based on file type
        try:
            file_path = storage.get_local_path(file_key)
            if is_epub:
                from config.backends import epub as epub_backend
                result = epub_backend.extract_text(file_path)
            else:
                result = ocr.extract_text(file_path)

            document.raw_text = result["text"]
            document.page_count = result["pages"]
            document.word_count = result["word_count"]
            document.status = Document.STATUS_READY
            document.save()
        except Exception as e:
            logger.error("Processing failed for document %d: %s", document.id, e)
            document.status = Document.STATUS_ERROR
            document.error_message = "Document processing failed. Please try again or contact support."
            try:
                document.save()
            except Exception as save_error:
                logger.critical(
                    "Failed to save error status for document %d: %s (original error: %s)",
                    document.id, save_error, e
                )

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

        # EPUB: process synchronously (no OCR needed)
        if document.file_type == Document.FILE_TYPE_EPUB:
            return self._process_epub(document)

        from config.backends.tasks import process_document_async

        process_document_async(document.id)

        return Response({"status": "processing"})

    def _process_epub(self, document):
        """Process EPUB synchronously (fast, no OCR)."""
        try:
            from config.backends import epub as epub_backend
            file_path = storage.get_local_path(document.file_key)
            result = epub_backend.extract_text(file_path)
            document.raw_text = result["text"]
            document.page_count = result["pages"]
            document.word_count = result["word_count"]
            document.status = Document.STATUS_READY
            document.save()
            return Response({"status": "ready"})
        except Exception as e:
            logger.error("EPUB processing failed for document %d: %s", document.id, e)
            document.status = Document.STATUS_ERROR
            document.error_message = "Document processing failed. Please try again or contact support."
            document.save()
            return Response({"status": "error", "error": "Document processing failed."}, status=500)


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
        documents = Document.objects.filter(user=request.user).prefetch_related('sessions')

        # Folder filter
        folder_id = request.query_params.get("folder")
        if folder_id is not None:
            if folder_id == "none":
                documents = documents.filter(folder__isnull=True)
            else:
                try:
                    folder_id_int = int(folder_id)
                except (ValueError, TypeError):
                    return Response(
                        {"error": "Invalid folder ID"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                documents = documents.filter(folder_id=folder_id_int)

        # Search
        search = request.query_params.get("search", "").strip()
        if search:
            documents = documents.filter(
                models.Q(title__icontains=search) | models.Q(raw_text__icontains=search)
            )

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
        except Exception as e:
            logger.error(
                "Failed to delete file %s for document %d: %s",
                document.file_key, document.id, e
            )

        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FigureListView(APIView):
    """List figures for a document, sorted by sort_order."""
    permission_classes = [IsAuthenticated]

    def get(self, request, document_id):
        document = get_object_or_404(Document, id=document_id, user=request.user)
        figures = document.figures.all()
        serializer = FigureSerializer(figures, many=True)
        return Response(serializer.data)


class FolderListView(APIView):
    """List and create folders."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        folders = Folder.objects.filter(user=request.user)
        serializer = FolderSerializer(folders, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = FolderSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        # Validate parent folder belongs to request.user
        parent = serializer.validated_data.get('parent')
        if parent is not None and parent.user != request.user:
            return Response(
                {"error": "Parent folder does not belong to you."},
                status=status.HTTP_403_FORBIDDEN,
            )

        folder = serializer.save(user=request.user)
        return Response(FolderSerializer(folder).data, status=status.HTTP_201_CREATED)


class FolderDetailView(APIView):
    """Update or delete a folder."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, folder_id):
        folder = get_object_or_404(Folder, id=folder_id, user=request.user)
        # Unlink documents (set folder to null)
        folder.documents.update(folder=None)
        folder.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentMoveView(APIView):
    """Move a document to a folder and/or update its tags."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, document_id):
        document = get_object_or_404(Document, id=document_id, user=request.user)
        serializer = DocumentMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        if "folder_id" in data:
            fid = data["folder_id"]
            if fid is None:
                document.folder = None
            else:
                folder = get_object_or_404(Folder, id=fid, user=request.user)
                document.folder = folder

        if "tags" in data:
            document.tags = data["tags"]

        document.save()
        return Response(DocumentSerializer(document).data)


class LocalUploadReceiveView(View):
    """Accept PUT with raw file body and save locally. Used when S3 is not configured."""

    def put(self, request, key):
        from config.backends.storage import _validate_key_within_root

        # Validate key against MEDIA_ROOT
        try:
            dest_path = _validate_key_within_root(key)
        except ValueError as e:
            return HttpResponse(str(e), status=400)

        # Save file
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(request.body)

        return HttpResponse("OK", status=200)
