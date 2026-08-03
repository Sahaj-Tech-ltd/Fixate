"""
Middleware to make request.get_full_path() include SCRIPT_NAME when
FORCE_SCRIPT_NAME is set. This fixes redirect parameters like ?next=
so they include the full URL path prefix.

Without this, get_full_path() returns /dashboard/ instead of /fixate/dashboard/
because Caddy strips the prefix before proxying.
"""

from django.conf import settings


class ScriptNameMiddleware:
    """Patch get_full_path() to respect FORCE_SCRIPT_NAME."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.script_name = getattr(settings, "FORCE_SCRIPT_NAME", "")

    def __call__(self, request):
        if self.script_name:
            # Store original so we can restore
            request._original_get_full_path = request.get_full_path

            def get_full_path_with_script(*args, **kwargs):
                # Call the original get_full_path (handles force_append_slash properly)
                path = request._original_get_full_path(*args, **kwargs)
                if self.script_name and not path.startswith(self.script_name):
                    path = self.script_name + path
                return path

            request.get_full_path = get_full_path_with_script

        return self.get_response(request)
