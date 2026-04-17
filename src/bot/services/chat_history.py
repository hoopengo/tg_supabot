"""Chat message history storage in Redis for AI context."""

import json
import logging

from aiogram.types import Message

from bot.redis import message_cache

logger = logging.getLogger(__name__)

REDIS_CHAT_MESSAGES_PREFIX = "chat_msgs"
MAX_STORED_MESSAGES = 2000
MESSAGE_TTL_SECONDS = 7 * 24 * 3600  # 7 days

# Approximate token budget for context (leave room for system prompt + user query)
MAX_CONTEXT_CHARS = 100_000  # ~25k tokens rough estimate


def _chat_messages_key(chat_id: int) -> str:
    return f"{REDIS_CHAT_MESSAGES_PREFIX}:{chat_id}"


async def store_chat_message(chat_id: int, message: Message) -> None:
    """Store a message in the chat history sorted set."""
    if not message.text:
        return

    sender = message.from_user
    if not sender:
        return

    name = sender.first_name or sender.username or str(sender.user_id)
    if sender.username and sender.first_name:
        name = f"{sender.first_name} (@{sender.username})"

    entry = json.dumps(
        {
            "mid": message.message_id,
            "name": name,
            "text": message.text,
            "ts": int(message.date.timestamp()),
        },
        ensure_ascii=False,
    )

    key = _chat_messages_key(chat_id)
    # Use message_id as score for ordering
    await message_cache.zadd(key, {entry: message.message_id})
    # Trim to keep only last MAX_STORED_MESSAGES
    await message_cache.zremrangebyrank(key, 0, -(MAX_STORED_MESSAGES + 1))
    # Refresh TTL
    await message_cache.expire(key, MESSAGE_TTL_SECONDS)


async def get_chat_history(chat_id: int, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """Get recent chat messages formatted for the AI, fitting within max_chars.

    Each line includes #msg_<id> so the LLM can reference specific messages.
    """
    key = _chat_messages_key(chat_id)
    # Get all stored messages ordered by score (message_id) ascending
    raw_messages = await message_cache.zrange(key, 0, -1)

    if not raw_messages:
        return "(история чата пуста)"

    # Build from newest to oldest, then reverse for chronological order
    lines: list[str] = []
    total_chars = 0

    for raw in reversed(raw_messages):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        mid = data.get("mid", "?")
        line = f"#msg_{mid} [{data['name']}]: {data['text']}"
        line_len = len(line) + 1  # +1 for newline

        if total_chars + line_len > max_chars:
            break

        lines.append(line)
        total_chars += line_len

    lines.reverse()
    return "\n".join(lines)
