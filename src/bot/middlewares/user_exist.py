import logging
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
        if event.chat.type != "private" and not await user_exist(
            event.from_user.id, event.chat.id
        ):
            try:
                await add_user(
                    event.from_user.id,
                    event.chat.id,
                    username=event.from_user.username,
                    first_name=event.from_user.first_name,
                )
            except Exception:
                logging.error("Failed to auto-register user", exc_info=True)
                return await event.answer("Произошла ошибка при регистрации.")

        return await handler(event, data)
