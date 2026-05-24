#!/usr/bin/env python3
"""Entry point for the Fixate desktop backend.

Compiled with PyInstaller. Starts Django with FIXATE_MODE=desktop,
prints the port on stdout for the Tauri shell to read.
"""
import os
import sys
import socket

os.environ["FIXATE_MODE"] = "desktop"
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ.setdefault("SECRET_KEY", "fixate-desktop-dev-key-change-in-build")
os.environ.setdefault("DEBUG", "False")
os.environ.setdefault("ALLOWED_HOSTS", "127.0.0.1,localhost")
os.environ.setdefault("DB_NAME", "fixate-desktop")


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    port = find_free_port()
    print(f"PORT:{port}", flush=True)

    # Set up Django
    from django.core.management import execute_from_command_line

    sys.argv = ["fixate-backend", "runserver", f"127.0.0.1:{port}", "--noreload"]
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
