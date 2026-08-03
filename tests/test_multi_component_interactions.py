"""
MULTI-COMPONENT EDGE CASES: Cross-cutting concerns across the fixate stack.

Tests the interaction between:
- AutoLoginMiddleware + Document upload + OCR + Reading session
- Tauri shell readiness signaling
- Desktop mode end-to-end flow
- Race conditions between components
- Double-start guard
"""
import pytest
from django.test import RequestFactory, Client
from rest_framework.test import force_authenticate


@pytest.mark.django_db
class TestMultiComponentAutoLoginFlow:
    """AutoLoginMiddleware creates user and logs them in transparently."""

    def test_first_request_creates_user_and_logs_in(self):
        """First unauthenticated request in desktop mode should auto-login."""
        client = Client()
        response = client.get('/')

        # Should get a redirect or page, not a 302 to login
        assert response.status_code != 302 or 'login' not in str(response.url).lower(), \
            f"Auto-login failed — got redirect to: {response.url}"

        from apps.users.models import User
        user = User.objects.filter(email="local@fixate.app").first()
        assert user is not None, "local@fixate.app user should be auto-created"
        assert user.tier == User.TIER_PRO, "Desktop user should be Pro tier"

    def test_second_request_uses_same_user(self):
        """Multiple requests reuse the same auto-created user."""
        from apps.users.models import User

        client1 = Client()
        client1.get('/')

        client2 = Client()
        client2.get('/')

        users = User.objects.filter(email="local@fixate.app")
        assert users.count() == 1, (
            f"Expected 1 auto-login user, found {users.count()}. "
            f"Each request should reuse the same user."
        )

    def test_auto_login_user_has_no_password(self):
        """The auto-created user has no usable password."""
        from apps.users.models import User

        client = Client()
        client.get('/')

        user = User.objects.get(email="local@fixate.app")
        assert not user.has_usable_password(), (
            "Auto-login user should have no password — "
            "prevents direct login if middleware is disabled"
        )


@pytest.mark.django_db
class TestMultiComponentUploadToReadPipeline:
    """Test the full flow: upload → OCR → read."""

    def test_full_pipeline_desktop_mode(self, auto_login_user):
        """End-to-end: upload a PDF, process it, start reading."""
        from apps.documents.models import Document
        from apps.reader.models import ReadingSession, UserPreferences
        from django.core.files.uploadedfile import SimpleUploadedFile
        from unittest.mock import patch

        # Create preferences
        prefs, _ = UserPreferences.objects.get_or_create(
            user=auto_login_user,
            defaults={'default_wpm': 250, 'default_mode': 'rsvp'}
        )

        # Upload a PDF with mocked OCR
        factory = RequestFactory()
        uploaded = SimpleUploadedFile('test.pdf', b'%PDF-1.4 fake', content_type='application/pdf')

        request = factory.post('/api/documents/upload/', {'file': uploaded})
        force_authenticate(request, user=auto_login_user)

        with patch('config.backends.ocr.extract_text', return_value={
            'text': 'Hello world this is a test document for reading',
            'pages': 1,
            'word_count': 10,
        }):
            from apps.documents.views import DocumentUploadView
            response = DocumentUploadView.as_view()(request)
            assert response.status_code == 201

        # Verify document was created and processed
        doc = Document.objects.filter(user=auto_login_user).first()
        assert doc is not None
        assert doc.status == Document.STATUS_READY
        assert doc.raw_text == 'Hello world this is a test document for reading'

        # Start reading
        from apps.reader.views import StartReadingView
        read_request = factory.post(f'/api/reader/start/{doc.id}/')
        force_authenticate(read_request, user=auto_login_user)
        read_response = StartReadingView.as_view()(read_request, document_id=doc.id)

        assert read_response.status_code == 200
        data = read_response.data
        assert data['text'] == doc.raw_text
        assert data['word_count'] == 10

        # Verify reading session created
        session = ReadingSession.objects.filter(
            user=auto_login_user, document=doc
        ).first()
        assert session is not None
        assert session.mode == prefs.default_mode
        assert session.wpm == prefs.default_wpm


@pytest.mark.django_db
class TestMultiComponentRaceConditions:
    """Test race conditions and concurrent access patterns."""

    def test_double_document_upload_same_name(self, auto_login_user):
        """Uploading the same file twice should create two documents."""
        from apps.documents.models import Document
        from django.core.files.uploadedfile import SimpleUploadedFile
        from unittest.mock import patch

        factory = RequestFactory()

        mock_ocr = patch('config.backends.ocr.extract_text', return_value={
            'text': 'test text', 'pages': 1, 'word_count': 2
        })

        with mock_ocr:
            from apps.documents.views import DocumentUploadView

            for i in range(3):
                uploaded = SimpleUploadedFile('test.pdf', b'%PDF-1.4', content_type='application/pdf')
                request = factory.post('/api/documents/upload/', {'file': uploaded})
                force_authenticate(request, user=auto_login_user)
                response = DocumentUploadView.as_view()(request)
                assert response.status_code == 201

        docs = Document.objects.filter(user=auto_login_user)
        assert docs.count() == 3, f"Expected 3 documents, got {docs.count()}"

    def test_concurrent_reading_sessions_same_document(self, auto_login_user):
        """Multiple reading sessions for the same document should work."""
        from apps.documents.models import Document
        from apps.reader.models import ReadingSession

        doc = Document.objects.create(
            user=auto_login_user,
            title="Concurrent Test",
            file_key="key",
            status=Document.STATUS_READY,
            raw_text="word " * 100,
            word_count=100,
        )

        # Create two sessions via StartReadingView
        from apps.reader.views import StartReadingView

        factory = RequestFactory()

        # First session
        r1 = factory.post(f'/api/reader/start/{doc.id}/')
        force_authenticate(r1, user=auto_login_user)
        resp1 = StartReadingView.as_view()(r1, document_id=doc.id)

        # Second request — should get same session (get_or_create)
        r2 = factory.post(f'/api/reader/start/{doc.id}/')
        force_authenticate(r2, user=auto_login_user)
        resp2 = StartReadingView.as_view()(r2, document_id=doc.id)

        # Both should return the same session ID
        assert resp1.data['session']['id'] == resp2.data['session']['id'], (
            "get_or_create should return the same session for duplicate requests"
        )

        sessions = ReadingSession.objects.filter(user=auto_login_user, document=doc)
        assert sessions.count() == 1, (
            f"Expected 1 reading session, got {sessions.count()}"
        )


@pytest.mark.django_db
class TestMultiComponentTauriBackendInteraction:
    """Tests for the Tauri ↔ Django backend boundary."""

    def test_backend_entry_sets_required_env_vars(self):
        """backend_entry.py must set FIXATE_MODE, SECRET_KEY, DEBUG, etc."""
        entry_path = __import__('os').path.join(
            __import__('os').path.dirname(__file__), '..', 'desktop', 'backend_entry.py'
        )
        with open(entry_path) as f:
            source = f.read()

        required_vars = ['FIXATE_MODE', 'DJANGO_SETTINGS_MODULE', 'SECRET_KEY', 'ALLOWED_HOSTS']
        for var in required_vars:
            assert var in source, f"backend_entry.py does not set {var}"

    def test_desktop_mode_has_no_external_dependencies(self):
        """Desktop mode should work without Redis, PostgreSQL, S3, or Celery broker."""
        from django.conf import settings

        # These should NOT be configured in desktop mode
        desktop_no_needs = [
            'CELERY_BROKER_URL',
            'AWS_ACCESS_KEY_ID',
            'AWS_SECRET_ACCESS_KEY',
            'AWS_STORAGE_BUCKET_NAME',
        ]

        for setting_name in desktop_no_needs:
            val = getattr(settings, setting_name, None)
            if val:  # Only flag if non-empty
                assert False, (
                    f"{setting_name} = '{val}' in desktop mode. "
                    f"Desktop mode should not require cloud services."
                )

    def test_no_textract_in_desktop_ocr_flow(self):
        """OCR in desktop mode should use Tesseract, never Textract."""
        from config.backends import ocr as ocr_module
        import inspect

        source = inspect.getsource(ocr_module.extract_text)

        # Desktop path should call _extract_text_tesseract
        assert '_extract_text_tesseract' in source
        # The desktop path should not reference Textract
        desktop_block = source[source.find("if mode == 'desktop'"):]
        next_elif = desktop_block.find('elif') if 'elif' in desktop_block else len(desktop_block)
        next_else = desktop_block.find('else:') if 'else:' in desktop_block else len(desktop_block)
        desktop_end = min(next_elif, next_else)
        desktop_path = desktop_block[:desktop_end]

        assert 'textract' not in desktop_path.lower(), (
            "Desktop OCR path references Textract — should only use Tesseract"
        )
