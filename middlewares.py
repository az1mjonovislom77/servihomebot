
from aiogram import BaseMiddleware
from aiogram.types import Message


class BlockMiddleware(BaseMiddleware):
    def __init__(self, blocked_users: set):
        super().__init__()
        self.blocked_users = blocked_users
        self.prev_status = {}

    async def __call__(self, handler, event: Message, data: dict):
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id = event.from_user.id
        username = event.from_user.username.lower() if event.from_user.username else None

        is_blocked = username in self.blocked_users if username else False
        was_blocked = self.prev_status.get(user_id)

        if is_blocked:
            if was_blocked is not True:
                await event.answer('🚫 Siz bloklandingiz, botdan foydalana olmaysiz')
            self.prev_status[user_id] = True
            return

        if was_blocked is True and not is_blocked:
            await event.answer('✅ Siz blokdan chiqarildingiz, endi botdan foydalanishingiz mumkin')

        self.prev_status[user_id] = False
        return await handler(event, data)
