"""
Seed default audio tracks (noise + ambient soundscapes).

Run: python manage.py seed_audio_tracks
Safe to run multiple times — uses get_or_create on slug.
"""
from django.core.management.base import BaseCommand
from apps.reader.models import AudioTrack


DEFAULT_TRACKS = [
    # ── Color Noise (generated client-side, no audio file) ──
    {
        "name": "White Noise",
        "slug": "white-noise",
        "category": AudioTrack.CATEGORY_NOISE,
        "noise_type": AudioTrack.NOISE_WHITE,
        "audio_url": None,
        "icon": "📺",
        "description": "Static-like hiss. Most studied for ADHD — boosts performance (g=0.249). Equal energy at all frequencies.",
        "sort_order": 1,
        "volume_default": 0.35,
        "tags": "adhd-i,adhd-c,focus,studying",
    },
    {
        "name": "Pink Noise",
        "slug": "pink-noise",
        "category": AudioTrack.CATEGORY_NOISE,
        "noise_type": AudioTrack.NOISE_PINK,
        "audio_url": None,
        "icon": "🌧️",
        "description": "Rain-like sound. Energy decreases as frequency increases. Good for sustained attention.",
        "sort_order": 2,
        "volume_default": 0.40,
        "tags": "adhd-i,adhd-c,focus,calm,rain",
    },
    {
        "name": "Brown Noise",
        "slug": "brown-noise",
        "category": AudioTrack.CATEGORY_NOISE,
        "noise_type": AudioTrack.NOISE_BROWN,
        "audio_url": None,
        "icon": "🌊",
        "description": "Deep, rumbling. Even less high-frequency energy than pink. Popular on social media (zero studies — use with caution).",
        "sort_order": 3,
        "volume_default": 0.45,
        "tags": "adhd-i,calm,sleep,deep",
    },
    # ── Ambient Soundscapes (streamed from CDN) ──
    # Audio URLs will be populated once files are uploaded to CDN.
    # For now, these are placeholders. audio_url is null until files exist.
    {
        "name": "Rain on Window",
        "slug": "rain-on-window",
        "category": AudioTrack.CATEGORY_AMBIENT,
        "noise_type": None,
        "audio_url": None,
        "icon": "☔",
        "description": "Gentle rain against a window pane. Occasional thunder in the distance. Loops seamlessly.",
        "sort_order": 10,
        "volume_default": 0.45,
        "tags": "ambient,rain,calm,adhd-i",
    },
    {
        "name": "Coffee Shop",
        "slug": "coffee-shop",
        "category": AudioTrack.CATEGORY_AMBIENT,
        "noise_type": None,
        "audio_url": None,
        "icon": "☕",
        "description": "Low murmur of conversation, clinking cups, espresso machine. The original productivity soundscape.",
        "sort_order": 11,
        "volume_default": 0.35,
        "tags": "ambient,cafe,focus,adhd-i",
    },
    {
        "name": "Forest Morning",
        "slug": "forest-morning",
        "category": AudioTrack.CATEGORY_AMBIENT,
        "noise_type": None,
        "audio_url": None,
        "icon": "🌲",
        "description": "Birdsong, rustling leaves, distant stream. Nature sounds reduce cortisol and improve cognitive performance.",
        "sort_order": 12,
        "volume_default": 0.40,
        "tags": "ambient,nature,calm,adhd-i",
    },
    {
        "name": "Ocean Waves",
        "slug": "ocean-waves",
        "category": AudioTrack.CATEGORY_AMBIENT,
        "noise_type": None,
        "audio_url": None,
        "icon": "🌊",
        "description": "Waves rolling in and out. Rhythmic, predictable — helps entrain brainwaves for focus.",
        "sort_order": 13,
        "volume_default": 0.45,
        "tags": "ambient,ocean,calm,adhd-i,sleep",
    },
    {
        "name": "Deep Space",
        "slug": "deep-space",
        "category": AudioTrack.CATEGORY_AMBIENT,
        "noise_type": None,
        "audio_url": None,
        "icon": "🚀",
        "description": "Low, ambient drone. Spaceship hum. Blocks out environmental noise without being distracting.",
        "sort_order": 14,
        "volume_default": 0.30,
        "tags": "ambient,drone,focus,adhd-i,adhd-c",
    },
    {
        "name": "Keyboard Typing",
        "slug": "keyboard-typing",
        "category": AudioTrack.CATEGORY_AMBIENT,
        "noise_type": None,
        "audio_url": None,
        "icon": "⌨️",
        "description": "Mechanical keyboard ASMR. Rhythmic typing creates a proxy for productivity — you hear work happening.",
        "sort_order": 15,
        "volume_default": 0.30,
        "tags": "ambient,asmr,focus,adhd-c",
    },
    {
        "name": "Cat Purring",
        "slug": "cat-purring",
        "category": AudioTrack.CATEGORY_AMBIENT,
        "noise_type": None,
        "audio_url": None,
        "icon": "🐱",
        "description": "A cat purring. Frequencies between 25-150 Hz are known to reduce stress and lower blood pressure.",
        "sort_order": 16,
        "volume_default": 0.50,
        "tags": "ambient,animal,calm,adhd-i,anxiety",
    },
]


class Command(BaseCommand):
    help = "Seed default audio tracks (noise + ambient soundscapes)"

    def handle(self, **options):
        created_count = 0
        updated_count = 0

        for data in DEFAULT_TRACKS:
            track, created = AudioTrack.objects.get_or_create(
                slug=data["slug"],
                defaults=data,
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  + {track}"))
            else:
                # Update existing with current defaults (non-destructive: only update
                # fields that don't have user customizations)
                changed = False
                for field in ["name", "icon", "description", "volume_default", "tags", "sort_order"]:
                    current = getattr(track, field)
                    new = data.get(field)
                    if current != new:
                        setattr(track, field, new)
                        changed = True
                if changed:
                    track.save()
                    updated_count += 1
                    self.stdout.write(self.style.WARNING(f"  ~ {track}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone: {created_count} created, {updated_count} updated, "
                f"{len(DEFAULT_TRACKS) - created_count - updated_count} unchanged"
            )
        )
