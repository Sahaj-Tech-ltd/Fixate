"""
Central font registry — single source of truth.

Add a font here and it automatically propagates to:
- models.py (FONT_CHOICES)
- context processor (template {{ FONTS }})
- base.html (JS FONT_REGISTRY + CSS CDN links)
- reader.html (getFontFamily() map)
- settings.html (font selector)
- main.css (data-font rules)

Format:
    FONT_ID: {
        "name": "Display Name",
        "family": "CSS font-family value",
        "category": "sans-serif" | "serif" | "system",
        "google_fonts": "Family+Name",  # or None
        "cdn_url": "https://...",       # or None (for non-Google CDN)
        "variable": True/False,         # is it a variable font?
        "weights": [400, 700],          # font weights to load
        "line_height": 1.6,             # default line-height
        "letter_spacing": "normal",     # CSS letter-spacing
        "word_spacing": "normal",       # CSS word-spacing
        "description": "one-liner",
        "accessibility": "adhd,dyslexia",  # comma-separated tags
    }
"""

FONT_REGISTRY = {
    "inter": {
        "name": "Inter",
        "family": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        "category": "sans-serif",
        "google_fonts": "Inter:wght@400;500;600;700",
        "cdn_url": None,
        "variable": True,
        "weights": [400, 500, 600, 700],
        "line_height": 1.6,
        "letter_spacing": "normal",
        "word_spacing": "normal",
        "description": "Modern, highly readable. The default.",
        "accessibility": "general",
    },
    "opendyslexic": {
        "name": "OpenDyslexic",
        "family": "'OpenDyslexic', 'Atkinson Hyperlegible', sans-serif",
        "category": "sans-serif",
        "google_fonts": None,
        "cdn_url": "https://fonts.cdnfonts.com/css/opendyslexic",
        "variable": False,
        "weights": [400, 700],
        "line_height": 1.8,
        "letter_spacing": "0.04em",
        "word_spacing": "0.16em",
        "description": "Open-source dyslexia-friendly font. Heavy bottoms prevent flipping.",
        "accessibility": "dyslexia",
    },
    "atkinson": {
        "name": "Atkinson Hyperlegible",
        "family": "'Atkinson Hyperlegible', sans-serif",
        "category": "sans-serif",
        "google_fonts": "Atkinson+Hyperlegible:ital,wght@0,400;0,700;1,400",
        "cdn_url": None,
        "variable": False,
        "weights": [400, 700],
        "line_height": 1.7,
        "letter_spacing": "0.02em",
        "word_spacing": "normal",
        "description": "Braille Institute font. Exaggerated differentiation for low vision.",
        "accessibility": "low-vision,dyslexia",
    },
    "lexend": {
        "name": "Lexend",
        "family": "'Lexend', sans-serif",
        "category": "sans-serif",
        "google_fonts": "Lexend:wght@400;500;600;700",
        "cdn_url": None,
        "variable": True,
        "weights": [400, 500, 600, 700],
        "line_height": 1.7,
        "letter_spacing": "normal",
        "word_spacing": "normal",
        "description": "Designed to improve reading speed. Variable width/spacing.",
        "accessibility": "adhd,general",
    },
    "comic": {
        "name": "Comic Sans",
        "family": "'Comic Sans MS', 'Comic Sans', 'Comic Neue', cursive, sans-serif",
        "category": "sans-serif",
        "google_fonts": None,
        "cdn_url": None,
        "variable": False,
        "weights": [400, 700],
        "line_height": 1.7,
        "letter_spacing": "0.02em",
        "word_spacing": "normal",
        "description": "Irregular letter shapes reduce confusion for dyslexic readers.",
        "accessibility": "dyslexia",
    },
    "system": {
        "name": "System Font",
        "family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif",
        "category": "system",
        "google_fonts": None,
        "cdn_url": None,
        "variable": False,
        "weights": [400, 700],
        "line_height": 1.6,
        "letter_spacing": "normal",
        "word_spacing": "normal",
        "description": "Your operating system's default font. Zero load time.",
        "accessibility": "general",
    },
}


def get_font_choices():
    """Return Django model choices from the registry."""
    return [(key, data["name"]) for key, data in FONT_REGISTRY.items()]


def get_google_fonts_url():
    """Build a single Google Fonts URL for all fonts that use Google Fonts."""
    families = []
    for key, data in FONT_REGISTRY.items():
        if data["google_fonts"]:
            families.append(data["google_fonts"])
    if not families:
        return None
    # Join with & since we pass individual family params
    return "https://fonts.googleapis.com/css2?" + "&family=".join(families) + "&display=swap"


def get_cdn_urls():
    """Return list of non-Google CDN URLs that need <link> tags."""
    urls = []
    for key, data in FONT_REGISTRY.items():
        if data["cdn_url"] and not data["google_fonts"]:
            urls.append(data["cdn_url"])
    return urls
