import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import Update


class FloodControlMiddleware(BaseMiddleware):
    CLEANUP_INTERVAL = 300  # Clean up stale entries every 5 minutes
    MAX_AGE = 60  # Remove entries older than 60 seconds

    def __init__(self, min_interval: float = 0.5):
        self.min_interval = min_interval
        self.last_processed: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._last_cleanup = time.time()

    async def _cleanup_stale_entries(self) -> None:
        """Remove entries that haven't been seen in MAX_AGE seconds."""
        now = time.time()
        if now - self._last_cleanup < self.CLEANUP_INTERVAL:
            return
        self._last_cleanup = now
        cutoff = now - self.MAX_AGE
        stale_keys = [k for k, v in self.last_processed.items() if v < cutoff]
        for key in stale_keys:
            del self.last_processed[key]

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        # Get chat_id and user_id for this update
        if hasattr(event, "message") and event.message:
            chat_id = event.message.chat.id
            user_id = event.message.from_user.id
        elif hasattr(event, "callback_query") and event.callback_query:
            chat_id = event.callback_query.message.chat.id
            user_id = event.callback_query.from_user.id
        else:
            return await handler(event, data)

        key = f"{chat_id}:{user_id}"

        async with self._lock:
            now = time.time()
            last_time = self.last_processed.get(key, 0)
            if now - last_time < self.min_interval:
                return  # Silently ignore to prevent flooding
            self.last_processed[key] = now
            await self._cleanup_stale_entries()

        try:
            return await handler(event, data)
        except TelegramRetryAfter as e:
            logging.warning(
                f"Flood control exceeded. Sleeping for {e.retry_after} seconds."
            )
            await asyncio.sleep(e.retry_after)
            return await handler(event, data)
