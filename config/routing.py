from django.urls import path
from apps.reader.consumers import CoworkConsumer

websocket_urlpatterns = [
    path("ws/cowork/<int:room_id>/", CoworkConsumer.as_asgi()),
]
