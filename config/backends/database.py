import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def get_database_config(mode):
    """Return database configuration based on FIXATE_MODE.

    desktop: SQLite stored at BASE_DIR/db.sqlite3
    cloud: returns None (settings.py uses its existing PostgreSQL config)
    """
    if mode == "desktop":
        db_path = BASE_DIR / "db.sqlite3"
        return {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(db_path),
            }
        }
    return None
