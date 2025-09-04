from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery


class BlockMiddleware(BaseMiddleware):
    def __init__(self, blocked_users: set):
        super().__init__()
        self.blocked_users = blocked_users

    async def __call__(self, handler, event, data):
        if isinstance(event, Message):
            user_id = event.from_user.id
            username = event.from_user.username.lower() if event.from_user.username else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            username = event.from_user.username.lower() if event.from_user.username else None
        else:
            return await handler(event, data)

        if user_id in self.blocked_users or (username and username in self.blocked_users):
            if isinstance(event, Message):
                await event.answer('🚫 Siz bloklandingiz, botdan foydalana olmaysiz')
            elif isinstance(event, CallbackQuery):
                await event.answer('🚫 Siz bloklandingiz, botdan foydalana olmaysiz', show_alert=True)
            return

        return await handler(event, data)
