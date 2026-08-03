from django.urls import path, re_path
from apps.documents.views import (
    DocumentUploadView,
    DocumentConfirmUploadView,
    DocumentListView,
    DocumentDetailView,
    DocumentStatusView,
    FigureListView,
    FolderListView,
    FolderDetailView,
    DocumentMoveView,
    LocalUploadReceiveView,
)

urlpatterns = [
    path('upload/', DocumentUploadView.as_view(), name='document-upload'),
    path('upload/<int:document_id>/confirm/', DocumentConfirmUploadView.as_view(), name='document-confirm-upload'),
    re_path(r'^upload-local/(?P<key>uploads/.+)$', LocalUploadReceiveView.as_view(), name='document-upload-local'),
    path('<int:document_id>/status/', DocumentStatusView.as_view(), name='document-status'),
    path('<int:document_id>/figures/', FigureListView.as_view(), name='document-figures'),
    path('<int:document_id>/move/', DocumentMoveView.as_view(), name='document-move'),
    path('folders/', FolderListView.as_view(), name='folder-list'),
    path('folders/<int:folder_id>/', FolderDetailView.as_view(), name='folder-detail'),
    path('', DocumentListView.as_view(), name='document-list'),
    path('<int:document_id>/', DocumentDetailView.as_view(), name='document-detail'),
]
