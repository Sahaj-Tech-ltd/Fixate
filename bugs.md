# Fixate — Bug Tracker

## CRITICAL (app won't start or core flow broken)

### BUG-1: HomeView not instantiated
**File:** `apps/users/urls.py:5`
**Problem:** `HomeView` is passed as the class itself instead of `HomeView.as_view()`. Django crashes on startup:
```
TypeError: view must be a callable or a list/tuple in the case of include()
```
**Fix:** Change `path("", HomeView, name="home")` → `path("", HomeView.as_view(), name="home")`

### BUG-2: Zero migration files
**File:** All `apps/*/migrations/` directories
**Problem:** No `migrations/` directories exist anywhere. Django can't create database tables. `python manage.py migrate` sees nothing to apply. Any DB access fails with `relation does not exist`.
**Fix:** Run `python manage.py makemigrations users documents reader` and commit the resulting migration files.

### BUG-3: No email backend configured
**File:** `config/settings.py`
**Problem:** `ACCOUNT_EMAIL_VERIFICATION = "mandatory"` requires sending real emails, but no `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, etc. are configured. New users can't verify emails → can't sign up. Password reset is also broken.
**Fix:** Add email config to settings and `.env.example`. Minimum:
```python
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"  # or console for dev
EMAIL_HOST = env("EMAIL_HOST", default="")
# ... etc
```
For dev: `EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"` — verification links appear in console output.

### BUG-4: `_.debounce` undefined in settings page
**File:** `templates/settings.html:114`
**Problem:** `savePreferences: _.debounce(async function() {...}, 500)` — Lodash/Underscore is not loaded anywhere. Alpine.js does not include `_.debounce`. Throws `ReferenceError: _ is not defined` when the settings page loads, breaking the entire Alpine component.
**Fix:** Either load Lodash via CDN in the template or implement a simple debounce manually:
```javascript
let debounceTimer;
function savePreferences() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
        // fetch...
    }, 500);
}
```

## HIGH (app runs but feature is broken)

### BUG-5: Static files break in production ✅ FIXED
**File:** `config/settings.py:96` + `Dockerfile`
**Problem:** `STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"` requires `python manage.py collectstatic` to generate manifest. Dockerfile doesn't run `collectstatic`. In production (DEBUG=False), static files 404 because manifest has no entries.
**Fix:** Add `RUN python manage.py collectstatic --noinput` to Dockerfile after COPY.
**Status:** Fixed — `collectstatic` added to Dockerfile.

### BUG-6: Dockerfile CMD vs docker-compose mismatch
**Files:** `Dockerfile:22`, `docker-compose.yml:30`
**Problem:** Dockerfile CMD is `gunicorn` (production), but docker-compose overrides with `python manage.py runserver` (dev). Not a bug per se, but the Dockerfile CMD is dead code if docker-compose always overrides it. More importantly, the docker-compose has `DEBUG=True` hardcoded and no gunicorn config for production.
**Fix:** Either make docker-compose use gunicorn in non-debug mode, or document that docker-compose is dev-only.

## MEDIUM (functional gaps, edge cases)

### BUG-7: Textract block sorting assumes Geometry always present
**File:** `apps/documents/tasks.py:129`
**Problem:** Line 129 sorts text blocks by `(page, Geometry.BoundingBox.Top)`. If Textract returns LINE blocks without Geometry data, the `.get()` chain returns `0` for all, collapsing reading order. Words may appear out of sequence.
**Fix:** Add fallback index-based sorting or use Textract's inherent block ordering (blocks array is already ordered top-to-bottom, left-to-right by default).

### BUG-8: `get_or_create` race condition in StartReadingView
**File:** `apps/reader/views.py:48-58`, `apps/reader/views.py:119-129`
**Problem:** `ReadingSession.objects.get_or_create()` with `defaults` — if two requests for the same (user, document) arrive simultaneously, the second one raises `IntegrityError` because the row was created between the get and the create.
**Fix:** Wrap in try/except IntegrityError or use `unique_together` constraint + retry on conflict.

### BUG-9: Missing `ACCOUNT_ADAPTER`
**File:** `config/settings.py`
**Problem:** django-allauth needs `ACCOUNT_ADAPTER` setting for proper email verification flows. Without it, allauth uses defaults which may not match the custom User model (email-as-username).
**Fix:** Add `ACCOUNT_ADAPTER = "allauth.account.adapter.DefaultAccountAdapter"`

### BUG-10: Theme system partially implemented — CSS doesn't switch
**Files:** `static/css/main.css`, `templates/reader.html`, `templates/settings.html`
**Problem:** UserPreferences has a `theme` field (light/dark/sepia), settings page lets you change it, but the CSS only defines dark theme variables in `:root`. No light or sepia theme CSS exists. Changing theme in settings does nothing visually.
**Fix:** Add `[data-theme="light"]` and `[data-theme="sepia"]` CSS variable overrides, and set `data-theme` attribute on `<html>` from Alpine based on user preference.

### BUG-11: OpenDyslexic font never loaded
**Files:** `static/css/main.css`, `templates/reader.html`
**Problem:** The font is referenced (`font-family: 'OpenDyslexic'`) in the font selector, but no `@font-face` declaration or Google Fonts/CDN link loads the actual font file. Falls back silently to sans-serif.
**Fix:** Add OpenDyslexic via CDN or self-host the font files. E.g.:
```html
<link href="https://fonts.cdnfonts.com/css/opendyslexic" rel="stylesheet">
```

## LOW (cosmetic, cleanup, minor)

### BUG-12: Duplicate README files
**Files:** `README.md`, `general README.md`
**Problem:** Both files contain identical content. Only `README.md` is the convention.
**Fix:** Delete `general README.md`.

### BUG-13: Empty `gitfix/` directory
**File:** `gitfix/`
**Problem:** Empty directory committed to git. No purpose.
**Fix:** Populate with actual git hooks/scripts or remove.

### BUG-14: Unused `import magic` in serializers.py
**File:** `apps/documents/serializers.py:1`
**Problem:** `import magic` imported but never used. Adds unnecessary dependency.
**Fix:** Remove the import.

### BUG-15: No test files exist anywhere
**Files:** All apps
**Problem:** Zero test files. Plan explicitly has "Auth tests", "Pipeline tests", "Reader tests" unchecked.
**Fix:** Write tests. Priority: auth flows, document upload/processing, reader session CRUD.
