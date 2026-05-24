#!/bin/bash
# Build the Fixate Python backend into a single binary with PyInstaller.
# Output: desktop/dist/fixate-backend
set -e

cd "$(dirname "$0")/.."

echo "=== Installing PyInstaller ==="
pip install pyinstaller 2>&1 | tail -3

echo "=== Building fixate-backend ==="
pyinstaller \
    --onefile \
    --name fixate-backend \
    --distpath desktop/dist \
    --workpath desktop/build \
    --specpath desktop \
    --add-data "config:config" \
    --add-data "apps:apps" \
    --add-data "templates:templates" \
    --add-data "static:static" \
    --hidden-import django \
    --hidden-import django.contrib.admin \
    --hidden-import django.contrib.auth \
    --hidden-import django.contrib.contenttypes \
    --hidden-import django.contrib.sessions \
    --hidden-import django.contrib.messages \
    --hidden-import django.contrib.staticfiles \
    --hidden-import django.contrib.sites \
    --hidden-import rest_framework \
    --hidden-import rest_framework.authentication \
    --hidden-import allauth \
    --hidden-import allauth.account \
    --hidden-import whitenoise \
    --hidden-import whitenoise.storage \
    --hidden-import django_htmx \
    --hidden-import storages \
    --hidden-import config.backends \
    --hidden-import config.backends.database \
    --hidden-import config.backends.storage \
    --hidden-import config.backends.ocr \
    --hidden-import config.backends.tasks \
    --hidden-import config.backends.auth \
    --hidden-import config.backends.media \
    --hidden-import config.middleware \
    desktop/backend_entry.py

echo ""
echo "=== Done ==="
ls -lh desktop/dist/fixate-backend
