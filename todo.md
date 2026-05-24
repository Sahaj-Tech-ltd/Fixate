# Fixate — TODO / Missing Features

## Current Shape

Django + DRF + HTMX + Alpine.js app for ADHD-friendly reading.

### What's built:
- ✅ User model (email-auth, tier system, Textract quota)
- ✅ Auth: email/password + Google OAuth (django-allauth)
- ✅ Document model with status pipeline (pending → processing → ready/error)
- ✅ Pre-signed S3 upload (client uploads directly to S3)
- ✅ Celery task: Textract async OCR with polling + retry logic
- ✅ RSVP reader engine (pure JS, solid — 141 lines)
- ✅ Bionic reading engine (pure JS, solid — 107 lines)
- ✅ Reading session tracking (position, mode, settings persisted to DB)
- ✅ Dashboard with document library (upload, status polling, delete)
- ✅ Reader page with full controls (speed, chunk size, bold, font, keyboard shortcuts)
- ✅ Settings page (preferences CRUD)
- ✅ UserPreferences signal (auto-create on user signup)
- ✅ Mobile responsive CSS
- ✅ Free tier: 10 Textract uploads
- ✅ Pro tier: unlimited (no Stripe integration yet)
- ✅ OpenCode GitHub Action (comment `/oc` to trigger)
- ✅ Dockerized (PostgreSQL 16, Redis 7, Django, Celery)

### What's broken (see bugs.md):
- 4 CRITICAL: HomeView crash, no migrations, no email backend, `_.debounce` crash
- 2 HIGH: static files in prod, Dockerfile/docker-compose mismatch
- 5 MEDIUM: Textract sorting, race condition, missing adapter, broken theme CSS, missing OpenDyslexic font
- 4 LOW: duplicate README, empty dir, unused import, no tests

---

## Must-Fix (blockers before any real usage)

- [ ] Fix BUG-1: `HomeView.as_view()` in urls
- [ ] Fix BUG-2: Generate and commit migrations
- [ ] Fix BUG-3: Configure email backend (console for dev, SMTP for prod)
- [ ] Fix BUG-4: Replace `_.debounce` with manual debounce in settings.html

## Should-Fix (broken in production)

- [ ] Fix BUG-5: Add `collectstatic` to Dockerfile
- [ ] Fix BUG-6: Sort out dev vs prod docker-compose (separate override file or profiles)
- [ ] Fix BUG-10: Implement light/sepia theme CSS
- [ ] Fix BUG-11: Load OpenDyslexic font via CDN

## Nice-to-Fix

- [ ] Fix BUG-7: Make Textract sorting resilient to missing geometry
- [ ] Fix BUG-8: Handle `get_or_create` race condition
- [ ] Fix BUG-9: Add `ACCOUNT_ADAPTER` setting
- [ ] Fix BUG-12: Delete duplicate `general README.md`
- [ ] Fix BUG-13: Populate or remove empty `gitfix/`
- [ ] Fix BUG-14: Remove unused `import magic`

## Missing Features (from original plan)

### Post-MVP (from plan — not started)
- [ ] Stripe billing integration
- [ ] EPUB support
- [ ] Document references/organizing
- [ ] AI flashcards from highlights
- [ ] Spaced repetition

### Deferred (acknowledged in plan)
- [ ] Lazy loading (page-by-page text delivery)
- [ ] Reference detection logic (OCR-based, non-AI)

### Not in plan but worth considering
- [ ] EPUB upload pipeline (currently PDF-only)
- [ ] Progress sync across devices (currently session-local)
- [ ] Dark/light/sepia theme in reader (model + UI exist, CSS missing)
- [ ] Reading stats dashboard (time spent, WPM trends, completion rate)
- [ ] Audio mode (TTS for RSVP — read aloud while flashing)

## Test Coverage (zero — plan had these unchecked)

- [ ] Auth tests (signup, login, OAuth, password reset)
- [ ] Pipeline tests (upload → S3 → Textract → status transitions)
- [ ] Reader tests (RSVP engine, bionic engine, session CRUD)
- [ ] Quota enforcement tests (free tier 10 limit, pro unlimited)

## Deployment Checklist

- [ ] S3 bucket created with private policy
- [ ] Cloudflare tunnel configured for domain
- [ ] `.env` populated with real secrets (not example values)
- [ ] `SECRET_KEY` changed from default
- [ ] `DEBUG=False` in production
- [ ] `ALLOWED_HOSTS` set to real domain
- [ ] Google OAuth credentials configured
- [ ] SSL/TLS handled by Cloudflare
- [ ] Database backups configured
