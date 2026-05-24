"""Desktop media configuration.

When FIXATE_MODE=desktop, uploaded files are stored locally under MEDIA_ROOT
and served by Django's static() helper in development.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
