from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.db.methods import add_user, user_exist


class UserExistCallbackMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if event.chat.type != "private" and not await user_exist(event.from_user.id, event.chat.id):
            try:
                await add_user(event.from_user.id, event.chat.id)
            except Exception as err:
                return await event.answer(f"Произошла ошибка: {err}")
            else:
                await event.answer(f"Ты был насильно зарегестрирован в системе под id: {event.from_user.id}")

        return await handler(event, data)
