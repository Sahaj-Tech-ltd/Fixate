# Fixate — ADHD-First PDF & EPUB Reader

**The first evidence-complete reading app for ADHD, backed by 40+ peer-reviewed papers.**

Fixate integrates RSVP speed reading, bionic text modes, stochastic resonance noise, hyperfocus induction, and accessibility-first design into a single research-grounded reading environment.

## Features

- **RSVP reading** — 100-1000 WPM with parafoveal preview, ORP highlighting
- **Bionic Reading** — optional, per research showing no universal benefit
- **Background noise** — white/pink/brown with EQ, LFO, and per-ADHD-subtype presets
- **Hyperfocus engine** — DMN disruption, variable rewards, comprehension checks
- **15 accessible themes + 6 fonts** — WCAG AA, OpenDyslexic, Atkinson Hyperlegible
- **Figure-panel linking** — auto-shows figures when text references them
- **EPUB + PDF** — both formats, local OCR via Tesseract (desktop) or AWS Textract (cloud)
- **Flashcards** — SM-2 spaced repetition from highlights, no AI gimmicks
- **Co-working rooms** — WebSocket timers, chat, presence, free forever
- **Gamification** — XP/levels, streak heatmap, breathing breaks
- **Desktop app** — Linux (.deb, .AppImage) + Windows (.msi, .exe) via Tauri

## Install

### Desktop App

Download the latest from [GitHub Releases](https://github.com/Sahaj-Tech-ltd/Fixate/releases).

### Self-Hosted (Docker)

```bash
git clone https://github.com/Sahaj-Tech-ltd/Fixate.git
cd Fixate
docker compose up -d
```

### Development

```bash
git clone https://github.com/Sahaj-Tech-ltd/Fixate.git
cd Fixate
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Research Foundation

Fixate is not vibes-based. Every feature is grounded in peer-reviewed research:

- RSVP boosts ADHD comprehension by 13% (Moussaoui et al., 2025)
- White/pink noise improves ADHD reading via stochastic resonance (g=0.249)
- DMN intrusion window is 5-15 seconds — the ritual targets this window
- Stimulants work through reward, not attention (WashU 2025) — XP does the same
- VWFA is an audiovisual convergence hub — TTS sync isn't redundant

Full research: `docs/research/`

## Architecture

Fixate is a Django application with:
- **Web frontend** — Django + HTMX + Alpine.js
- **Desktop shell** — Tauri (Rust) wrapping the Django backend via PyInstaller
- **Real-time** — Django Channels + Daphne for WebSocket co-working
- **OCR** — PyMuPDF + Tesseract (desktop) / AWS Textract (cloud)

## License

MIT — see [LICENSE](LICENSE).

Fixate is free software. The reading engine, noise system, hyperfocus, co-working, fonts, and themes are all open source. A separate commercial layer (`fixate-web`) handles Stripe billing and SaaS hosting.
