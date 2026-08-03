#!/usr/bin/env python3
"""Entry point for the Fixate desktop backend.

Compiled with PyInstaller. Starts Django with FIXATE_MODE=desktop,
auto-runs migrations, generates a secure SECRET_KEY on first run,
and prints the port on stdout for the Tauri shell to read.
"""
import os
import sys
import socket
import secrets
import json
from pathlib import Path

os.environ["FIXATE_MODE"] = "desktop"
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ.setdefault("DEBUG", "False")
os.environ.setdefault("ALLOWED_HOSTS", "127.0.0.1,localhost")

# Per-install data directory (user's config dir)
DATA_DIR = Path.home() / ".fixate"
CONFIG_FILE = DATA_DIR / "config.json"


def _load_or_generate_secret_key():
    """Load SECRET_KEY from config file, or generate and persist a new one."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
            key = config.get("secret_key")
            if key and len(key) >= 50:
                return key
        except (json.JSONDecodeError, KeyError):
            pass

    # Generate a new secure key
    key = secrets.token_urlsafe(64)
    config = {"secret_key": key}
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)
    return key


os.environ["SECRET_KEY"] = _load_or_generate_secret_key()


def find_free_port(preferred=None):
    """Find a free port, trying the preferred port first."""
    if preferred is None:
        preferred = int(os.environ.get("FIXATE_DESKTOP_PORT", "18000"))
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", preferred))
            return preferred
    except OSError:
        pass
    # Preferred port taken, find any free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = find_free_port()


def main():
    print(f"PORT:{PORT}", flush=True)

    from django.core.management import execute_from_command_line

    # Run migrations on every startup (idempotent)
    sys.argv = ["fixate-backend", "migrate", "--noinput"]
    execute_from_command_line(sys.argv)

    # Start the server
    sys.argv = ["fixate-backend", "runserver", f"127.0.0.1:{PORT}", "--noreload"]
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
