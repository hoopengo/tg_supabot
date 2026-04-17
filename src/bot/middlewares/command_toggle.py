import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.repositories import settings_repo

logger = logging.getLogger(__name__)

# Commands that can be toggled
TOGGLEABLE_COMMANDS = set(
    [
        "dick",
        "top_dick",
        "stats",
        "casino",
        "casino_top",
        "slots",
        "sanitary",
        "all",
        "top_toxic",
        "transfer",
        "queues",
        "create_queue",
        "switch",
        "ask",
    ]
)


def _extract_command(text: str | None) -> str | None:
    """Extract command name from message text."""
    if not text or not text.startswith("/"):
        return None
    # /command@botname args -> command
    cmd = text.split()[0].lstrip("/").split("@")[0].lower()
    return cmd


class CommandToggleMiddleware(BaseMiddleware):
    """Middleware that blocks disabled commands per chat."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        # Only check group/supergroup messages
        if event.chat.type == "private":
            return await handler(event, data)

        command = _extract_command(event.text)
        if not command or command not in TOGGLEABLE_COMMANDS:
            return await handler(event, data)

        if not await settings_repo.is_command_enabled(event.chat.id, command):
            # Silently ignore disabled commands
            return None

        return await handler(event, data)
