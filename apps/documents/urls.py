from django.urls import path
from apps.documents.views import (
    DocumentUploadView,
    DocumentConfirmUploadView,
    DocumentListView,
    DocumentDetailView,
    DocumentStatusView,
)

urlpatterns = [
    path('upload/', DocumentUploadView.as_view(), name='document-upload'),
    path('upload/<int:document_id>/confirm/', DocumentConfirmUploadView.as_view(), name='document-confirm-upload'),
    path('<int:document_id>/status/', DocumentStatusView.as_view(), name='document-status'),
    path('', DocumentListView.as_view(), name='document-list'),
    path('<int:document_id>/', DocumentDetailView.as_view(), name='document-detail'),
]
