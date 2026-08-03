#!/bin/bash
# Build the Fixate Python backend into a single binary with PyInstaller.
# Output: desktop/dist/fixate-backend
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "=== Installing PyInstaller ==="
pip install pyinstaller 2>&1 | tail -3

echo "=== Collecting static files ==="
python manage.py collectstatic --noinput 2>&1 | tail -3

echo "=== Building fixate-backend ==="
pyinstaller \
    --onefile \
    --name fixate-backend \
    --distpath "$PROJECT_DIR/desktop/dist" \
    --workpath "$PROJECT_DIR/desktop/build" \
    --specpath /tmp \
    --add-data "$PROJECT_DIR/config:config" \
    --add-data "$PROJECT_DIR/apps:apps" \
    --add-data "$PROJECT_DIR/templates:templates" \
    --add-data "$PROJECT_DIR/static:static" \
    --add-data "$PROJECT_DIR/staticfiles:staticfiles" \
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
    --collect-submodules rest_framework \
    --hidden-import allauth \
    --collect-submodules allauth \
    --hidden-import whitenoise \
    --hidden-import whitenoise.storage \
    --collect-submodules whitenoise \
    --hidden-import django_htmx \
    --collect-submodules django_htmx \
    --hidden-import environ \
    --hidden-import storages \
    --hidden-import config.backends \
    --hidden-import config.backends.database \
    --hidden-import config.backends.storage \
    --hidden-import config.backends.ocr \
    --hidden-import config.backends.tasks \
    --hidden-import config.backends.auth \
    --hidden-import config.backends.media \
    --hidden-import config.middleware \
    "$PROJECT_DIR/desktop/backend_entry.py"

echo ""
echo "=== Done ==="
ls -lh "$PROJECT_DIR/desktop/dist/fixate-backend"
