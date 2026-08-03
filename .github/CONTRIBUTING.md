# Contributing to Fixate

Thanks for your interest in Fixate! Fixate is an ADHD-first reading research app backed by 40+ peer-reviewed papers across speed reading science and ADHD neuroscience.

## Dev Setup

```bash
git clone https://github.com/Sahaj-Tech-ltd/Fixate.git
cd Fixate
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Quick Start

```bash
python -m pytest          # 22 tests, should all pass
python manage.py check    # Django system checks
```

If both pass, you're ready to contribute.

## Contribution Priorities

1. **Bug fixes** — especially reading accuracy, accessibility, or data loss
2. **ADHD research** — new features grounded in peer-reviewed neuroscience
3. **Accessibility** — fonts, themes, screen reader support, WCAG compliance
4. **Performance** — RSVP rendering, noise generation, page load
5. **Documentation** — clarity, research citations, examples

## Branch Naming

| Type | Prefix | Example |
|------|--------|---------|
| Bug fix | `fix/` | `fix/rsvp-word-skip` |
| Feature | `feat/` | `feat/epub-annotations` |
| Docs | `docs/` | `docs/research-citations` |
| Test | `test/` | `test/noise-generator` |
| Refactor | `refactor/` | `refactor/ocr-pipeline` |
| Security | `security/` | `security/xss-reader-input` |

## Commit Style

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(reader): add parafoveal preview to RSVP mode
fix(noise): clamp volume to 30% on all browsers
docs(research): cite Soderlund 2024 for per-type noise defaults
```

## Code Style

- **Python:** PEP 8. Type hints encouraged.
- **JavaScript:** ES6+. No framework required — vanilla JS + Alpine.js for interactivity.
- **CSS:** BEM-ish naming. All new themes must pass WCAG AA contrast.
- **Tests:** pytest. One test file per feature area. Test noise generation, RSVP timing, theme switching.

## Research Requirement

Fixate is evidence-based. Any new reading or ADHD feature must cite at least one peer-reviewed paper. The research foundation lives in:

- `/home/harsh/butter/speed-reading-research.md`
- `/home/harsh/butter/adhd-reading-research.md`

If you're adding a feature not covered by existing research, include the citation in your PR description.

## Architecture

See `MASTER-PLAN.md` in the parent directory for the full roadmap.
