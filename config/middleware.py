"""AutoLoginMiddleware — single-user mode for desktop.

When FIXATE_MODE=desktop, automatically creates and logs in a local user
on the first request. Subsequent requests reuse the same user.
No signup/login pages needed.
"""

from django.conf import settings
from django.contrib.auth import login


class AutoLoginMiddleware:
    """Auto-creates and logs in a default user when FIXATE_MODE=desktop."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            settings.FIXATE_MODE == "desktop"
            and hasattr(request, "user")
            and not request.user.is_authenticated
        ):
            from apps.users.models import User

            user, _ = User.objects.get_or_create(
                email="local@fixate.app",
                defaults={
                    "tier": User.TIER_PRO,
                },
            )
            login(request, user)

        return self.get_response(request)
