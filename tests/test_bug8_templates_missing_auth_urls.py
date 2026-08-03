"""
BUG-8 (CRITICAL): Templates reference allauth URLs that don't exist in desktop mode.

In config/urls.py, allauth URLs are conditionally excluded when FIXATE_MODE=desktop:
    if settings.FIXATE_MODE != "desktop":
        urlpatterns.insert(1, path("accounts/", include("allauth.urls")))

But the templates still use {% url 'account_signup' %}, {% url 'account_login' %},
{% url 'account_logout' %}. In desktop mode, these reverse() lookups crash with:

    NoReverseMatch: Reverse for 'account_signup' not found.

Affected templates:
- home.html: buttons for "Get Started Free" / "Sign In"
- dashboard.html: "Sign Out" link
- account/* templates: various references (these are less critical since
  AutoLoginMiddleware prevents users from reaching login/signup pages)

Root cause: The mode-switching only affects URL configuration and middleware,
not the template layer. Templates need to conditionally hide/show auth links
based on FIXATE_MODE.
"""
import pytest
from django.test import Client
from django.urls import reverse, NoReverseMatch


@pytest.mark.django_db
class TestBug8TemplatesReferenceMissingAuthUrls:
    """Templates crash because allauth URLs don't exist in desktop mode."""

    def test_account_signup_does_not_exist_in_desktop_mode(self):
        """In desktop mode, 'account_signup' should not exist or the template
        should conditionally avoid it."""
        with pytest.raises(NoReverseMatch) as exc_info:
            reverse('account_signup')
        assert 'account_signup' in str(exc_info.value)

    def test_account_login_does_not_exist_in_desktop_mode(self):
        """Ditto for login."""
        with pytest.raises(NoReverseMatch) as exc_info:
            reverse('account_login')
        assert 'account_login' in str(exc_info.value)

    def test_account_logout_does_not_exist_in_desktop_mode(self):
        """Ditto for logout."""
        with pytest.raises(NoReverseMatch) as exc_info:
            reverse('account_logout')
        assert 'account_logout' in str(exc_info.value)

    def test_home_template_has_auth_references(self):
        """home.html contains references to nonexistent auth URLs."""
        template_path = __import__('os').path.join(
            __import__('os').path.dirname(__file__),
            '..', 'templates', 'home.html'
        )
        with open(template_path) as f:
            content = f.read()

        # These will cause NoReverseMatch in desktop mode
        assert 'account_signup' in content or 'account_login' in content, (
            "home.html should NOT have allauth URL references in desktop mode, "
            "or the template should wrap them in {% if FIXATE_MODE != 'desktop' %}"
        )

    def test_dashboard_template_uses_builtin_logout(self):
        """dashboard.html should use Django's built-in {% url 'logout' %}, not allauth's."""
        template_path = __import__('os').path.join(
            __import__('os').path.dirname(__file__),
            '..', 'templates', 'dashboard.html'
        )
        with open(template_path) as f:
            content = f.read()

        # Should use Django's logout, not allauth's
        assert "{% url 'logout' %}" in content, \
            "dashboard.html should use Django's built-in logout URL"
        assert 'account_logout' not in content, \
            "dashboard.html must NOT reference allauth's account_logout"

    def test_home_page_works_in_desktop_mode(self, auto_login_user):
        """After fix: the home page should render without crashing."""
        client = Client()
        client.force_login(auto_login_user)

        response = client.get('/')
        # Should NOT crash — the fix wraps auth URLs in {% if %}
        assert response.status_code == 200, (
            f"Home page returned {response.status_code}. "
            f"Expected 200 after auth URL fix."
        )
