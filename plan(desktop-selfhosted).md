# Fixate — Desktop + Self-Hosted Architecture

## Model

```
┌─────────────────────────────────────────────────┐
│                  Fixate App                      │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  CLOUD   │  │  DOCKER  │  │   DESKTOP    │  │
│  │  (SaaS)  │  │(selfhost)│  │   (Tauri)    │  │
│  ├──────────┤  ├──────────┤  ├──────────────┤  │
│  │PostgreSQL│  │PostgreSQL│  │   SQLite     │  │
│  │  S3      │  │  S3/MinIO│  │   Local FS   │  │
│  │Textract  │  │Textract  │  │  Tesseract   │  │
│  │  Redis   │  │  Redis   │  │   No Redis   │  │
│  │ Celery   │  │  Celery  │  │  No Celery   │  │
│  │Freemium  │  │  Free    │  │   Free       │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
└─────────────────────────────────────────────────┘
```

## Desktop App: Tauri + Embedded Python

### Why Tauri over Electron
- **Tauri**: ~5MB binary, Rust shell, system webview
- **Electron**: 150MB+, ships full Chromium
- For ADHD users, fast startup matters. Tauri launches in <1s.

### Architecture
```
Fixate.app/
├── fixate-desktop        # Tauri binary (Rust)
├── backend/              # Python backend (PyInstaller bundle)
│   ├── python            # Embedded Python 3.12
│   ├── django/           # All Django code (shared with web)
│   ├── tesseract/        # Bundled Tesseract OCR binary
│   └── sqlite3           # Local database
├── frontend/             # Same Alpine.js + HTMX templates
└── resources/            # Icons, fonts (OpenDyslexic bundled)
```

### Tauri Responsibilities
- Spawn Python backend on startup (`python manage.py runserver 127.0.0.1:0`)
- Detect free port, pass to webview
- Open borderless/framed window with webview to localhost
- System tray (minimize to tray, quick resume)
- Keyboard shortcuts at OS level (global play/pause for RSVP)
- Auto-updater
- Bundles OpenDyslexic font locally (no CDN dependency)

### Backend Changes for Desktop Mode
- `FIXATE_MODE=desktop` env var switches behavior:
  - **Database**: SQLite instead of PostgreSQL
  - **OCR**: pytesseract instead of Textract
  - **Storage**: Local filesystem instead of S3
  - **Tasks**: Synchronous (no Celery/Redis needed)
  - **Auth**: Optional — single-user mode, or skip entirely
- Same Django views, serializers, models
- Same Alpine.js/HTMX frontend — zero changes

### Desktop-Specific Features
- **Global hotkey**: Space to play/pause RSVP even when app is in background
- **System tray**: Mini controls (play/pause, WPM +/-)
- **Offline-first**: Everything works without internet
- **Auto-save**: Position saved locally every second (already built)
- **Import**: File picker or drag-and-drop PDFs (bypasses S3 upload flow)

### Freemium Model
- **Desktop (Tauri)**: Always free. Local OCR, SQLite, all reader features.
- **Docker self-hosted**: Always free. Bring your own S3/Textract keys or use Tesseract.
- **Cloud (SaaS, fixate.app)**: Freemium — 10 Textract uploads free, Pro $5/mo unlimited.
- **Pro add-on (any platform)**: Cloud sync between devices — $5/mo.
  - Encrypted sync of reading positions, documents, preferences
  - Works across desktop ↔ web ↔ mobile (future)

## Self-Hosted (Docker)

Already built. Docker Compose with PostgreSQL + Redis + Celery.

### Additions needed:
- `FIXATE_MODE=selfhosted` env var
- Option to use Tesseract instead of Textract (for fully free self-hosting)
- Healthcheck endpoint
- One-command deploy script

## Implementation Plan

### Phase 1: Backend Abstraction (unblocks everything)
- [ ] Create `config/backends.py` — switchable backends for DB, OCR, storage, tasks
- [ ] `FIXATE_MODE` setting: `cloud` (default) | `selfhosted` | `desktop`
- [ ] SQLite backend (django.db.backends.sqlite3)
- [ ] Local storage backend (Django FileSystemStorage)
- [ ] Tesseract OCR backend (pytesseract + pdf2image)
- [ ] Synchronous task runner (no Celery when desktop/selfhosted)
- [ ] Single-user mode (skip auth for desktop)

### Phase 2: Tauri Desktop Shell
- [ ] Init Tauri project in `/desktop/`
- [ ] Rust: spawn Python subprocess, port detection
- [ ] Rust: webview to localhost
- [ ] Rust: system tray + global hotkeys
- [ ] PyInstaller config to bundle Python + Django + Tesseract
- [ ] Build scripts for .exe (Windows), .app (macOS), .AppImage (Linux)
- [ ] Auto-updater via GitHub Releases

### Phase 3: Sync (Pro feature)
- [ ] Sync API endpoints (Django REST)
- [ ] Encryption at rest (client-side key)
- [ ] Conflict resolution (last-write-wins for position, merge for preferences)

### Phase 4: Polish
- [ ] OpenDyslexic bundled with app
- [ ] Light/sepia theme CSS
- [ ] Onboarding flow (first-launch preferences wizard)
- [ ] Import from URL (fetch PDF directly)
- [ ] Reading stats dashboard

## File Changes Summary
```
New files:
  config/backends.py          # Switchable backends
  config/backends/
    db.py                     # SQLite + PostgreSQL
    ocr.py                    # Textract + Tesseract
    storage.py                # S3 + Local
    tasks.py                  # Celery + Sync
  desktop/                    # Tauri project
    src-tauri/
    src/
  scripts/
    build-desktop.sh          # PyInstaller + Tauri build

Modified files:
  config/settings.py          # FIXATE_MODE + backend switching
  apps/documents/tasks.py    # Abstract OCR call
  apps/documents/s3_utils.py # Abstract storage call
  docker-compose.yml          # Add FIXATE_MODE env var
  Dockerfile                  # Add collectstatic
```

## Non-Goals (for now)
- Mobile app (iOS/Android) — web app works on mobile browsers
- EPUB support — PDF-only for MVP
- Stripe integration — manual billing for early Pro users
- AI flashcards / spaced repetition — post-MVP
