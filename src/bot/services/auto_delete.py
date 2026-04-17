"""Auto-delete utility for bot messages.

Provides helpers to schedule message deletion after a delay.
- Immediate commands (dick, casino, sanitary, etc.): delete both user command
  and bot response after a short delay.
- Slots/roulette: delete after the spin finishes.
- Interactive panels (admin, superadmin, queues): delete after inactivity timeout.
"""

import asyncio
import logging

from aiogram import Bot
from aiogram.types import Message

logger = logging.getLogger(__name__)

# Default delays in seconds
DEFAULT_COMMAND_DELETE_DELAY = 5  # For simple command responses
PANEL_INACTIVITY_TIMEOUT = 60  # 1 minute for interactive panels
RESULT_DELETE_DELAY = 60  # For game results (slots, casino)


async def _safe_delete_message(bot: Bot, chat_id: int, message_id: int) -> None:
    """Safely delete a single message, ignoring errors."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass  # Message may already be deleted or bot lacks permissions


async def schedule_delete(
    bot: Bot,
    chat_id: int,
    message_ids: list[int],
    delay: float = DEFAULT_COMMAND_DELETE_DELAY,
) -> None:
    """Schedule deletion of messages after a delay. Fire-and-forget."""
    await asyncio.sleep(delay)
    for msg_id in message_ids:
        await _safe_delete_message(bot, chat_id, msg_id)


def schedule_delete_task(
    bot: Bot,
    chat_id: int,
    message_ids: list[int],
    delay: float = DEFAULT_COMMAND_DELETE_DELAY,
) -> asyncio.Task:
    """Create a background task to delete messages after delay."""
    return asyncio.create_task(schedule_delete(bot, chat_id, message_ids, delay))


async def delete_command_and_response(
    user_message: Message,
    bot_message: Message,
    delay: float = DEFAULT_COMMAND_DELETE_DELAY,
) -> None:
    """Schedule deletion of both user command and bot response."""
    bot = user_message.bot
    chat_id = user_message.chat.id
    message_ids = [user_message.message_id, bot_message.message_id]
    schedule_delete_task(bot, chat_id, message_ids, delay)


async def delete_messages_later(
    bot: Bot,
    chat_id: int,
    message_ids: list[int],
    delay: float = DEFAULT_COMMAND_DELETE_DELAY,
) -> None:
    """Schedule deletion of arbitrary messages."""
    schedule_delete_task(bot, chat_id, message_ids, delay)
