"""Middleware that stores every text message in Redis for AI context."""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.services.chat_history import store_chat_message

logger = logging.getLogger(__name__)


async def _store_message(message: Message) -> None:
    """Fire-and-forget helper to store a message without blocking the pipeline."""
    try:
        if message.chat.type in ("group", "supergroup") and message.text:
            # Skip /ask commands so they don't pollute AI context
            if message.text.startswith("/ask"):
                return
            await store_chat_message(message.chat.id, message)
    except Exception:
        logger.debug("Failed to store chat message", exc_info=True)


class MessageHistoryMiddleware(BaseMiddleware):
    """Stores text messages in Redis sorted sets for later AI queries."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        # Store in background, don't block the handler pipeline
        asyncio.create_task(_store_message(event))

        return await handler(event, data)
