from django.urls import path
from apps.reader.views import (
    UserPreferencesView,
    StartReadingView,
    UpdateSessionView,
    DocumentTextView,
    ReaderView,
)

urlpatterns = [
    path('preferences/', UserPreferencesView.as_view(), name='user-preferences'),
    path('start/<int:document_id>/', StartReadingView.as_view(), name='start-reading'),
    path('session/<int:session_id>/', UpdateSessionView.as_view(), name='update-session'),
    path('text/<int:document_id>/', DocumentTextView.as_view(), name='document-text'),
    path('read/<int:document_id>/', ReaderView.as_view(), name='reader'),
]
