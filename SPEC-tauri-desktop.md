# SPEC: Fixate Tauri Desktop Shell

## Goal
Package Fixate as a native desktop app using Tauri. The app bundles the Django backend + Tesseract OCR and presents it in a native window. Zero cloud dependencies. Works offline.

## Architecture

```
Fixate.app/
├── fixate-desktop          # Tauri binary (Rust, ~5MB)
├── backend/                # Python embedded via PyInstaller
│   ├── python              # Embedded Python 3.12
│   ├── site-packages/      # Django + all deps
│   ├── tesseract/          # Bundled Tesseract binary
│   └── fixate-code/        # The Django app (frozen copy)
├── frontend/               # Static files (collected)
└── resources/              # Icons, fonts
```

## Tauri Shell Spec

### Window
- Framed window, 1200x800 default, min 800x600
- Title: "Fixate"
- Custom icon (placeholder — use Tauri default for now, we'll add custom later)
- Single window (no multi-window)

### Backend Lifecycle
1. On app start: spawn Python subprocess running Django
   - Command: `./backend/python -m django runserver 127.0.0.1:0 --noreload`
   - Capture the randomly-assigned port from stdout
2. Wait for backend to be ready (poll `http://127.0.0.1:{port}/` until 200)
3. Open webview to `http://127.0.0.1:{port}/`
4. On app close: kill the Python subprocess gracefully (SIGTERM, then SIGKILL after 5s)

### System Tray
- Minimize to system tray instead of closing
- Tray menu: Show, Pause/Play RSVP, Quit
- Tray icon: same as app icon

### Global Hotkeys (optional — nice-to-have)
- `Ctrl+Shift+Space`: Play/Pause RSVP (only when app is running)
- `Ctrl+Shift+Left`: Rewind
- `Ctrl+Shift+Right`: Forward
- These send keyboard events to the webview

### Auto-Updater
- Check GitHub Releases for new versions
- On startup: check once, notify if update available
- Download and prompt to install

## What the subagent must do

### 1. Install Tauri CLI
```bash
cargo install tauri-cli
```

### 2. Initialize Tauri project
```bash
cd /home/harsh/Fixate
cargo tauri init
# App name: fixate
# Window title: Fixate
# Dev URL: http://localhost:8000
# Build dist dir: ../staticfiles
# Dev command: python manage.py runserver
```

### 3. Configure `desktop/src-tauri/tauri.conf.json`
```json
{
  "build": {
    "devUrl": "http://localhost:8000",
    "frontendDist": "../staticfiles"
  },
  "app": {
    "title": "Fixate",
    "windows": [{
      "title": "Fixate",
      "width": 1200,
      "height": 800,
      "minWidth": 800,
      "minHeight": 600
    }],
    "security": {
      "csp": null
    }
  }
}
```

### 4. Rust main.rs — Backend Manager
The main.rs should:
- On startup, look for `backend/fixate-backend` (the PyInstaller binary)
- Spawn it as a child process with `FIXATE_MODE=desktop`
- Parse the port from stdout (the binary prints "PORT:12345")
- Set the webview URL
- Handle graceful shutdown

Key Rust code structure:
```rust
use std::process::{Command, Child};
use std::sync::Mutex;
use tauri::Manager;

struct BackendState {
    process: Mutex<Option<Child>>,
}

fn main() {
    tauri::Builder::default()
        .manage(BackendState { process: Mutex::new(None) })
        .setup(|app| {
            // Spawn backend
            let mut child = Command::new("backend/fixate-backend")
                .env("FIXATE_MODE", "desktop")
                .spawn()?;
            // Read port from stdout
            // Set webview URL
            Ok(())
        })
        .on_window_event(|event| {
            // On close, kill backend
        })
        .run(tauri::generate_context!())
        .expect("error while running Fixate");
}
```

### 5. Python Backend Entry Point
Create `desktop/backend_entry.py` — the script PyInstaller compiles:
```python
#!/usr/bin/env python
"""Entry point for the Fixate desktop backend."""
import os
import sys
import socket
import subprocess
import time

os.environ['FIXATE_MODE'] = 'desktop'
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ.setdefault('SECRET_KEY', 'fixate-desktop-dev-key-change-in-build')
os.environ.setdefault('DEBUG', 'False')
os.environ.setdefault('ALLOWED_HOSTS', '127.0.0.1,localhost')

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def main():
    port = find_free_port()
    print(f"PORT:{port}", flush=True)
    
    # Run Django
    from django.core.management import execute_from_command_line
    sys.argv = ['manage.py', 'runserver', f'127.0.0.1:{port}', '--noreload']
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
```

### 6. PyInstaller Build Script
Create `desktop/build-backend.sh`:
```bash
#!/bin/bash
# Build the Python backend binary
cd /home/harsh/Fixate

# Install deps
pip install pyinstaller

# Build single binary
pyinstaller \
    --onefile \
    --name fixate-backend \
    --add-data "config:config" \
    --add-data "apps:apps" \
    --add-data "templates:templates" \
    --add-data "static:static" \
    --hidden-import django \
    --hidden-import django.contrib.admin \
    --hidden-import rest_framework \
    --hidden-import allauth \
    --hidden-import whitenoise \
    --hidden-import pytesseract \
    --hidden-import pdf2image \
    desktop/backend_entry.py

echo "Backend built: dist/fixate-backend"
```

### 7. Cargo.toml Dependencies
```toml
[dependencies]
tauri = { version = "1", features = ["shell-open"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

### 8. Tauri System Tray Plugin
Enable system tray with minimize-to-tray behavior:
```toml
[dependencies]
tauri-plugin-tray = "1"
```

## Files to Create
```
desktop/
├── backend_entry.py        # PyInstaller entry point
├── build-backend.sh        # Build script for Python backend
├── src-tauri/
│   ├── Cargo.toml          # Rust dependencies
│   ├── tauri.conf.json     # Tauri config
│   ├── build.rs            # Tauri build script
│   ├── icons/              # App icons (placeholder PNG)
│   └── src/
│       └── main.rs         # Rust backend manager + window
└── README.md               # Desktop build instructions
```

## Verification
1. `cargo tauri dev` — Tauri window opens, Django starts, webview loads dashboard
2. `FIXATE_MODE=desktop` is set automatically
3. SQLite database created automatically
4. Closing window kills backend
5. `./desktop/build-backend.sh` produces a working `fixate-backend` binary

## Non-goals for this phase
- Windows/macOS builds (Linux first — cross-compilation is Phase 3)
- Auto-updater (Phase 4)
- Code signing
- App store distribution
