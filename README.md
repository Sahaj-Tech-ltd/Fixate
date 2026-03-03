# Fixate

An ADHD-optimized reading app using RSVP (Rapid Serial Visual Presentation) and Bionic Reading to maximize focus and comprehension.

## Features

- **RSVP Mode** - Words flash one at a time, eliminating saccades and forcing focus
- **Bionic Reading** - First letters bolded for faster pattern-matching
- **Dyslexia-Friendly Fonts** - OpenDyslexic and other accessible font options
- **Deep Customization** - Speed, bold intensity, themes, chunk sizes
- **Smart Position Tracking** - Resume exactly where you left off

## Tech Stack

- **Backend**: Django, Django REST Framework, Celery, Redis
- **Frontend**: HTMX, Alpine.js
- **Database**: PostgreSQL
- **Storage**: Amazon S3
- **OCR**: Amazon Textract
- **CDN**: Cloudflare

## Development

```bash
# Clone the repo
git clone https://github.com/Sahaj-Tech-ltd/Fixate.git
cd Fixate

# Set up environment
cp .env.example .env
# Edit .env with your credentials

# Run with Docker
docker-compose up -d
```

## License

MIT License - see [LICENSE](LICENSE)
