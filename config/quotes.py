"""
Daily quote engine — curated quotes that rotate daily.
No API dependency. Works offline. Deterministic per day.

Categories:
  - focus: deep work, concentration
  - adhd: neurodivergent-friendly motivation
  - resilience: keep going
  - humor: funny, self-deprecating
  - general: classic productivity
"""

import hashlib
from datetime import date

QUOTES = [
    # ── Focus ──
    {"text": "The successful warrior is the average man, with laser-like focus.", "author": "Bruce Lee", "category": "focus"},
    {"text": "You can do anything, but not everything.", "author": "David Allen", "category": "focus"},
    {"text": "What you do today can improve all your tomorrows.", "author": "Ralph Marston", "category": "focus"},
    {"text": "It is not enough to be busy. So are the ants. The question is: What are we busy about?", "author": "Henry David Thoreau", "category": "focus"},
    {"text": "Focus is a matter of deciding what things you're not going to do.", "author": "John Carmack", "category": "focus"},
    {"text": "The shorter way to do many things is to only do one thing at a time.", "author": "Mozart", "category": "focus"},
    {"text": "Most of what we say and do is not essential. If you can eliminate it, you'll have more time, and more tranquility.", "author": "Marcus Aurelius", "category": "focus"},

    # ── ADHD ──
    {"text": "You don't have a motivation problem. You have a starting problem. Start smaller.", "author": "Dr. Russell Barkley", "category": "adhd"},
    {"text": "Your brain isn't broken. It's a Ferrari engine with bicycle brakes.", "author": "Dr. Edward Hallowell", "category": "adhd"},
    {"text": "Interest + Challenge + Urgency = Focus. If you're struggling, one of these is missing.", "author": "ADHD productivity rule", "category": "adhd"},
    {"text": "Done is better than perfect. Perfect is a procrastination tool.", "author": "Sheryl Sandberg", "category": "adhd"},
    {"text": "The only way to eat an elephant is one bite at a time. The ADHD way: hyperfocus and eat half the elephant, then forget about it for three days.", "author": "Unknown", "category": "adhd"},
    {"text": "You're not lazy. You're understimulated. There's a difference.", "author": "ADHD wisdom", "category": "adhd"},
    {"text": "Body doubling works. Your brain literally mirrors the focus of others. Use it.", "author": "ADHD productivity science", "category": "adhd"},

    # ── Resilience ──
    {"text": "It does not matter how slowly you go as long as you do not stop.", "author": "Confucius", "category": "resilience"},
    {"text": "Fall seven times, stand up eight.", "author": "Japanese proverb", "category": "resilience"},
    {"text": "The master has failed more times than the beginner has even tried.", "author": "Stephen McCranie", "category": "resilience"},
    {"text": "You may have to fight a battle more than once to win it.", "author": "Margaret Thatcher", "category": "resilience"},
    {"text": "Our greatest glory is not in never falling, but in rising every time we fall.", "author": "Confucius", "category": "resilience"},

    # ── Humor ──
    {"text": "I'm not procrastinating. I'm doing background processing.", "author": "Every developer ever", "category": "humor"},
    {"text": "My brain has too many tabs open.", "author": "ADHD starter pack", "category": "humor"},
    {"text": "I'll do it tomorrow. — Me, every day, about everything.", "author": "Honest productivity", "category": "humor"},
    {"text": "Productivity tip: close Twitter. Oh wait, you're reading this on Twitter.", "author": "Irony", "category": "humor"},
    {"text": "I have a system. I just don't follow it.", "author": "Organized chaos", "category": "humor"},
    {"text": "Why do today what you can hyperfocus on at 3 AM?", "author": "Night owl manifesto", "category": "humor"},

    # ── General ──
    {"text": "The best time to plant a tree was 20 years ago. The second best time is now.", "author": "Chinese proverb", "category": "general"},
    {"text": "Simplicity is the ultimate sophistication.", "author": "Leonardo da Vinci", "category": "general"},
    {"text": "First, solve the problem. Then, write the code.", "author": "John Johnson", "category": "general"},
    {"text": "Walking on water and developing software from a specification are easy if both are frozen.", "author": "Edward V. Berard", "category": "general"},
    {"text": "The only way to do great work is to love what you do.", "author": "Steve Jobs", "category": "general"},
]


def get_daily_quote(category: str = None) -> dict:
    """
    Return a deterministic daily quote. Same quote all day, changes at midnight.
    Uses the current date as a seed for deterministic selection.
    If category is provided, filters to that category.
    """
    pool = QUOTES
    if category:
        pool = [q for q in QUOTES if q["category"] == category]
        if not pool:
            pool = QUOTES  # fallback

    today = date.today().isoformat()
    # Hash the date to get a deterministic index
    hash_bytes = hashlib.md5(today.encode()).digest()
    index = int.from_bytes(hash_bytes[:4], 'big') % len(pool)
    return pool[index]


def get_time_greeting() -> tuple[str, str]:
    """
    Return (greeting, emoji) based on current hour.
    """
    from django.utils import timezone
    hour = timezone.now().hour

    if 5 <= hour < 12:
        return ("Good morning", "☀️")
    elif 12 <= hour < 17:
        return ("Good afternoon", "🌤️")
    elif 17 <= hour < 21:
        return ("Good evening", "🌅")
    elif 21 <= hour < 24:
        return ("Late night grind", "🌙")
    else:
        return ("Still up?", "🦉")
