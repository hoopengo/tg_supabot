import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import Update


class FloodControlMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except TelegramRetryAfter as e:
            logging.warning(
                f"Flood control exceeded. Sleeping for {e.retry_after} seconds."
            )
            await asyncio.sleep(e.retry_after)
            return await handler(event, data)
