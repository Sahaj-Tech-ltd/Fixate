import secrets
import string
from django.db import transaction

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone as djangotime

from apps.reader.models import CoworkRoom, RoomParticipant, ChatMessage


class CoworkConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer for real-time co-working rooms.

    Events:
      → join, leave, chat, timer_start, timer_pause, timer_reset, presence_ping
      ← presence, chat, timer_sync, user_joined, user_left, error
    """

    ROOM_GROUP_PREFIX = "cowork_"

    @property
    def room_group_name(self):
        return f"{self.ROOM_GROUP_PREFIX}{self.room_id}"

    async def connect(self):
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # Verify room exists
        room = await self.get_room()
        if not room or not room.is_active:
            await self.close(code=4004)
            return
        # Verify user is a participant of the room
        is_member = await self.check_membership()
        if not is_member:
            await self.close(code=4003)
            return

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Register participant
        await self.join_room()

        await self.accept()

        # Send current presence + timer state to the joiner
        presence = await self.get_presence()
        timer = await self.get_timer_state()
        await self.send_json({
            "type": "room_state",
            "presence": presence,
            "timer": timer,
        })

        # Broadcast to others that someone joined
        user_info = await self.get_user_info()
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_joined",
                "user": user_info,
                "presence": presence,
            },
        )

    async def disconnect(self, close_code):
        if hasattr(self, "room_id") and hasattr(self, "user"):
            await self.leave_room()

            user_info = await self.get_user_info()
            presence = await self.get_presence()

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "user_left",
                    "user": user_info,
                    "presence": presence,
                },
            )

            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # ── Receive ──

    async def receive_json(self, content):
        msg_type = content.get("type")

        if msg_type == "chat":
            await self.handle_chat(content)
        elif msg_type == "timer_start":
            await self.handle_timer_start()
        elif msg_type == "timer_pause":
            await self.handle_timer_pause(content)
        elif msg_type == "timer_reset":
            await self.handle_timer_reset(content)
        elif msg_type == "presence_ping":
            await self.handle_ping()

    async def handle_chat(self, content):
        message = content.get("message", "").strip()
        if not message or len(message) > 500:
            return

        msg = await self.save_message(message)
        user_info = await self.get_user_info()

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "id": msg["id"],
                "user": user_info,
                "content": message,
                "created_at": msg["created_at"],
            },
        )

    async def handle_timer_start(self):
        now = djangotime.now()
        await self.update_timer(running=True, started_at=now)
        timer = await self.get_timer_state()

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "timer_sync", "timer": timer},
        )

    async def handle_timer_pause(self, content):
        remaining = content.get("remaining", 0)
        await self.update_timer(running=False, started_at=None, remaining=remaining)
        timer = await self.get_timer_state()

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "timer_sync", "timer": timer},
        )

    async def handle_timer_reset(self, content):
        duration = content.get("duration", 25 * 60)
        await self.update_timer(running=False, started_at=None, remaining=duration, duration=duration)
        timer = await self.get_timer_state()

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "timer_sync", "timer": timer},
        )

    async def handle_ping(self):
        await self.ping_participant()

    # ── Broadcast handlers (called by channel_layer.group_send) ──

    async def user_joined(self, event):
        await self.send_json({
            "type": "user_joined",
            "user": event["user"],
            "presence": event["presence"],
        })

    async def user_left(self, event):
        await self.send_json({
            "type": "user_left",
            "user": event["user"],
            "presence": event["presence"],
        })

    async def chat_message(self, event):
        await self.send_json({
            "type": "chat",
            "id": event["id"],
            "user": event["user"],
            "content": event["content"],
            "created_at": event["created_at"],
        })

    async def timer_sync(self, event):
        await self.send_json({
            "type": "timer_sync",
            "timer": event["timer"],
        })

    # ── DB helpers ──

    @database_sync_to_async
    def get_room(self):
        try:
            return CoworkRoom.objects.get(id=self.room_id)
        except CoworkRoom.DoesNotExist:
            return None

    @database_sync_to_async
    def get_user_info(self):
        return {
            "id": self.user.id,
            "email": self.user.email,
            "name": self.user.first_name or self.user.email.split("@")[0],
        }

    @database_sync_to_async
    def check_membership(self):
        return RoomParticipant.objects.filter(
            room_id=self.room_id, user=self.user
        ).exists()

    @database_sync_to_async
    def join_room(self):
        participant, _ = RoomParticipant.objects.update_or_create(
            room_id=self.room_id,
            user=self.user,
            defaults={"is_active": True, "last_ping": djangotime.now()},
        )
        return participant

    @database_sync_to_async
    def leave_room(self):
        RoomParticipant.objects.filter(
            room_id=self.room_id, user=self.user
        ).update(is_active=False)

    @database_sync_to_async
    def ping_participant(self):
        RoomParticipant.objects.filter(
            room_id=self.room_id, user=self.user
        ).update(last_ping=djangotime.now())

    @database_sync_to_async
    def get_presence(self):
        participants = RoomParticipant.objects.filter(
            room_id=self.room_id, is_active=True
        ).select_related("user").order_by("joined_at")

        return [
            {
                "id": p.user.id,
                "name": p.user.first_name or p.user.email.split("@")[0],
                "email": p.user.email,
                "joined_at": p.joined_at.isoformat(),
            }
            for p in participants
        ]

    @database_sync_to_async
    def get_timer_state(self):
        room = CoworkRoom.objects.get(id=self.room_id)
        return {
            "running": room.timer_running,
            "duration": room.timer_duration,
            "remaining": room.timer_remaining,
            "started_at": room.timer_started_at.isoformat() if room.timer_started_at else None,
        }

    @database_sync_to_async
    def update_timer(self, running=None, started_at=None, remaining=None, duration=None):
        with transaction.atomic():
            room = CoworkRoom.objects.select_for_update().get(id=self.room_id)
            if running is not None:
                room.timer_running = running
            if started_at is not None:
                room.timer_started_at = started_at
            if remaining is not None:
                room.timer_remaining = max(0, min(remaining, 86400))
            if duration is not None:
                room.timer_duration = duration
            room.save()

    @database_sync_to_async
    def save_message(self, content):
        msg = ChatMessage.objects.create(
            room_id=self.room_id,
            user=self.user,
            content=content,
        )
        return {
            "id": msg.id,
            "created_at": msg.created_at.isoformat(),
        }


def generate_room_code():
    """Generate a 6-character alphanumeric room code."""
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(6))
