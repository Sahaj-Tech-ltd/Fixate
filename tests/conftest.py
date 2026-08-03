"""
Test fixtures for Fixate desktop mode.
Sets up SQLite in-memory DB, desktop mode env vars, auto-creates the local user.
"""
import os
import pytest


def pytest_configure():
    """Configure Django settings for testing."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ["FIXATE_MODE"] = "desktop"
    os.environ["SECRET_KEY"] = "test-secret-key-for-pytest"
    os.environ["DEBUG"] = "False"
    os.environ["ALLOWED_HOSTS"] = "127.0.0.1,localhost"
    os.environ["DB_NAME"] = "fixate-test-desktop"


@pytest.fixture(autouse=True)
def desktop_mode(settings):
    """Force desktop mode for all tests."""
    settings.FIXATE_MODE = "desktop"
    settings.DEBUG = True  # for test convenience
    settings.ALLOWED_HOSTS = ["*"]
    settings.SECRET_KEY = "test-key"
    settings.FORCE_SCRIPT_NAME = None  # clear for tests — no Caddy prefix
    settings.DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
    # Disable celery in tests
    settings.CELERY_TASK_ALWAYS_EAGER = True


@pytest.fixture
def auto_login_user(db, client):
    """Create the auto-login user and force login."""
    from apps.users.models import User

    user, _ = User.objects.get_or_create(
        email="local@fixate.app",
        defaults={"tier": User.TIER_PRO},
    )
    client.force_login(user)
    return user


@pytest.fixture
def document(db, auto_login_user):
    """Create a test document owned by the auto-login user."""
    from apps.documents.models import Document

    return Document.objects.create(
        user=auto_login_user,
        title="Test Document",
        file_key="uploads/1/documents/test.pdf",
        file_type=Document.FILE_TYPE_PDF,
        status=Document.STATUS_PENDING,
    )
