"""Middleware to add Content-Security-Policy header to all responses."""


class CSPMiddleware:
    """Add CSP header to responses using Django settings."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdnjs.cloudflare.com https://www.youtube.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://fonts.gstatic.com https://fonts.cdnfonts.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' ws: wss: https://www.youtube.com; "
            "frame-src 'self' https://open.spotify.com https://www.youtube.com https://player.vimeo.com https://calendar.google.com https://outlook.live.com https://outlook.office.com; "
            "font-src 'self' https://fonts.gstatic.com https://fonts.cdnfonts.com"
        )
        return response
