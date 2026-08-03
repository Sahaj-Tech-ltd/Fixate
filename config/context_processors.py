"""Context processors available to all templates."""
from django.conf import settings

from config.fonts import FONT_REGISTRY, get_google_fonts_url, get_cdn_urls
from config.quotes import get_daily_quote, get_time_greeting


def fixate_mode(request):
    """Expose FIXATE_MODE and font registry to all templates."""
    greeting, greeting_emoji = get_time_greeting()
    return {
        "fixate_mode": settings.FIXATE_MODE,
        "is_desktop": settings.FIXATE_MODE == "desktop",
        "FONTS": FONT_REGISTRY,
        "FONTS_JSON": _fonts_json(),
        "GOOGLE_FONTS_URL": get_google_fonts_url(),
        "CDN_URLS": get_cdn_urls(),
        "daily_quote": get_daily_quote(),
        "greeting": greeting,
        "greeting_emoji": greeting_emoji,
        "FORCE_SCRIPT_NAME": getattr(settings, "FORCE_SCRIPT_NAME", ""),
    }


def _fonts_json():
    """Serialize font registry to JSON for JS consumption. Only includes
    the fields Alpine.js needs (family, line_height, etc.) to keep it lean."""
    import json
    slim = {}
    for key, data in FONT_REGISTRY.items():
        slim[key] = {
            "family": data["family"],
            "line_height": data["line_height"],
            "letter_spacing": data["letter_spacing"],
            "word_spacing": data["word_spacing"],
        }
    return json.dumps(slim)
