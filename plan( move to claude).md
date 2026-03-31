# FIXATE
## ADHD-First Reading App - MVP Build Plan
**Django + HTMX + Alpine.js | S3 + Cloudflare | RSVP + Bionic Reading**

---

## Pricing Model

- **Free tier**: 10 Textract OCR uploads total
- **Pro tier ($5/mo)**: Unlimited Textract + all features

---

## MVP Scope

**In Scope:**
- Auth (Email + Google OAuth)
- PDF upload only (EPUB deferred)
- OCR pipeline with lazy loading
- RSVP reader
- Bionic reader
- Font system (dyslexia-friendly included)
- Customization (speed, bold, theme, chunk size)
- Position tracking

**Post-MVP:**
- Document references/organizing
- AI flashcards from highlights
- Spaced repetition
- Stripe billing
- EPUB support

---

## Build Phases

### PHASE 1: FOUNDATION ✅
- [x] Initialize Django project with proper structure
- [x] Set up PostgreSQL (Docker)
- [x] Configure django-environ
- [x] Set up Redis (Docker)
- [x] Create User model with tier field (free/pro)
- [ ] Set up S3 bucket (private policy) - user has this
- [ ] Configure Cloudflare tunnel - user has this
- [x] Create .env.example
- [x] Set up logging

### PHASE 2: AUTH & USER SYSTEM ✅
- [x] Email/password registration
- [x] Email/password login
- [x] Google OAuth integration
- [x] Password reset
- [x] UserPreferences model
- [x] Session management
- [ ] Auth tests

### PHASE 3: DOCUMENT PIPELINE ✅
- [x] Document model
- [x] PDF upload endpoint (python-magic validation)
- [x] Pre-signed S3 URLs
- [x] Celery setup
- [x] Textract integration with quota tracking
- [ ] Lazy loading (page-by-page) - deferred to post-MVP
- [x] Progress tracking (OCR status)
- [x] Text storage in PostgreSQL
- [x] Error handling: skip unreadable pages, show indicator
- [ ] Reference detection logic (non-AI, OCR-based) - deferred
- [ ] Pipeline tests

### PHASE 4: READER ENGINE ✅
- [x] ReadingSession model
- [x] RSVP JavaScript engine
- [x] Bionic Reading JavaScript engine
- [x] Font system (OpenDyslexic, Inter, system fonts)
- [ ] Theme system (light, dark, sepia) - deferred
- [x] Speed control (100-800 WPM)
- [x] Bold intensity slider
- [x] Chunk size control
- [x] Pause/play/rewind/keyboard shortcuts
- [x] Position persistence
- [ ] Reader tests

### PHASE 5: UI & POLISH ✅
- [x] Dashboard/library page
- [x] Reader page layout
- [x] Settings page
- [x] HTMX interactions
- [x] Alpine.js state management
- [x] Mobile responsive
- [x] Loading states, error messages
- [x] Quota display (X/10 uploads)

---

## Agent Rules

### Never
- Hardcode secrets
- Expose S3 publicly
- Run migrations without backup
- Call Textract without quota check
- Use DEBUG=True in production

### Always
- Validate files with python-magic
- Index foreign keys
- Write idempotent Celery tasks
- Scope queries by user
- Test OCR output (>50 chars for multi-page)
