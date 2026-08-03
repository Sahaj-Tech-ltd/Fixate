from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/documents/", include("apps.documents.urls")),
    path("api/reader/", include("apps.reader.urls")),
    path("", include("apps.users.urls")),
]

# allauth not needed in desktop mode (AutoLoginMiddleware handles auth)
if settings.FIXATE_MODE != "desktop":
    urlpatterns.insert(1, path("accounts/", include("allauth.urls")))

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Desktop mode: serve uploaded media files via Django
if settings.FIXATE_MODE == "desktop":
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
