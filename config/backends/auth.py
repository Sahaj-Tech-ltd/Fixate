"""Backend abstraction for authentication configuration.

Cloud mode: standard django-allauth flow (no changes).
Desktop mode: single-user auto-login.
"""


def configure_auth(mode):
    """Return auth-related settings dict, or None for defaults."""
    if mode == "desktop":
        return {
            "AUTO_LOGIN_USERNAME": "fixate-user",
        }
    return None
