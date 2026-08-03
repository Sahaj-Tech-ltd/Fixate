#!/usr/bin/env bash
# Fixate Desktop — single command local setup
# Run this from the Fixate/app directory
# Usage: bash run.sh
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

echo "=== Fixate Desktop Setup ==="

# 1. Create .env if missing
if [ ! -f .env ]; then
    cat > .env << 'EOF'
FIXATE_MODE=desktop
EOF
    echo "  Created .env"
fi

# 2. Create virtualenv if missing
if [ ! -d venv ]; then
    python3 -m venv venv
    echo "  Created venv"
fi

# 3. Activate and install
source venv/bin/activate
pip install -q --upgrade pip

# Install only what's needed for desktop
pip install -q \
    "Django>=5.2.15,<6" \
    "djangorestframework>=3.17" \
    "django-allauth>=65" \
    "django-htmx>=1.27" \
    "django-environ>=0.13" \
    "whitenoise>=6.12" \
    "pillow>=12.2" \
    "PyMuPDF>=1.27" \
    "ebooklib>=0.20" \
    "beautifulsoup4>=4.15" \
    "pytesseract>=0.3" \
    "pdf2image>=1.16" \
    "python-magic>=0.4" \
    "requests>=2.32" \
    "defusedxml>=0.7"

echo "  Dependencies installed"

# 4. Create media dir
mkdir -p media

# 5. Run migrations
python manage.py migrate --noinput
echo "  Migrations complete"

# 6. Start the server
echo ""
echo "=== Fixate running at http://localhost:8000 ==="
echo "    Open your browser. You're auto-logged in."
echo "    Upload PDFs, start reading."
echo ""
python manage.py runserver
