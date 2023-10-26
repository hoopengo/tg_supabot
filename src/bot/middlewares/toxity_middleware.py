from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.db.methods import update_toxicity_level
from bot.services.toxicity import is_toxic


async def _toxicity_handler(message: Message) -> None:
    if not isinstance(message.text, str):
        return

    if await is_toxic(message.text[:120]):
        await update_toxicity_level(message.from_user.id, message.chat.id, +1)


class ToxityMessageMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        await _toxicity_handler(event)

        return await handler(event, data)
