"""AI command handler using OpenAI-compatible API via logfare.ai."""

import logging
import re

from aiogram import F, Router
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from openai import AsyncOpenAI

from bot.redis import message_cache
from bot.services.admin_service import is_admin, is_super_admin, is_bot_creator
from bot.services.auto_delete import delete_command_and_response
from bot.services.chat_history import get_chat_history

logger = logging.getLogger(__name__)

ai_router = Router(name="ai")

# --- Constants ---

LOGFARE_BASE_URL = "https://logfare.ai/v1"
LOGFARE_MODEL = "gemini-3-flash"

# Rate limits in seconds per role
COOLDOWN_USER = 30
COOLDOWN_ADMIN = 5
# Super admin and bot owner: no cooldown

REDIS_KEY_PREFIX = "ai_cooldown"

# Regex to find [REF:123456] tags in LLM output
_REF_PATTERN = re.compile(r"\[REF:(\d+)\]")

_client = AsyncOpenAI(
    base_url=LOGFARE_BASE_URL,
    api_key="not-needed",
)

SYSTEM_PROMPT = (
    "Ты — полезный ассистент группового чата в Telegram. "
    "Тебе передаётся история последних сообщений чата и вопрос пользователя. "
    "Отвечай на русском языке, кратко и по делу. "
    "Каждое сообщение в истории помечено идентификатором #msg_<id>. "
    "Если ты ссылаешься на конкретное сообщение из истории — ОБЯЗАТЕЛЬНО укажи его тег "
    "в формате [REF:<id>] (например [REF:12345]). Можно указать несколько тегов. "
    "Бот автоматически сделает reply на первое указанное сообщение, чтобы пользователь "
    "мог перейти к нему в чате. "
    "Если ответа нет в истории — честно скажи, что не нашёл."
)


# --- Cooldown helpers ---


def _cooldown_key(user_id: int, chat_id: int) -> str:
    return f"{REDIS_KEY_PREFIX}:{chat_id}:{user_id}"


async def _check_cooldown(user_id: int, chat_id: int) -> int | None:
    """Return remaining seconds if on cooldown, else None."""
    key = _cooldown_key(user_id, chat_id)
    ttl = await message_cache.ttl(key)
    if ttl > 0:
        return ttl
    return None


async def _set_cooldown(user_id: int, chat_id: int, seconds: int) -> None:
    key = _cooldown_key(user_id, chat_id)
    await message_cache.setex(key, seconds, "1")


async def _get_cooldown_seconds(user_id: int, chat_id: int) -> int:
    """Determine cooldown duration based on user role. 0 = no cooldown."""
    if is_bot_creator(user_id):
        return 0
    if await is_super_admin(chat_id, user_id):
        return 0
    if await is_admin(chat_id, user_id):
        return COOLDOWN_ADMIN
    return COOLDOWN_USER


def _parse_refs(text: str) -> tuple[str, list[int]]:
    """Extract [REF:id] tags from LLM response.

    Returns cleaned text and list of referenced message IDs.
    """
    refs: list[int] = []
    for match in _REF_PATTERN.finditer(text):
        try:
            refs.append(int(match.group(1)))
        except ValueError:
            continue
    # Remove the [REF:...] tags from the visible text
    clean = _REF_PATTERN.sub("", text).strip()
    # Collapse multiple spaces left after removal
    clean = re.sub(r" {2,}", " ", clean)
    return clean, refs


# --- Handler ---


@ai_router.message(Command("ai", ignore_case=True), F.chat.type != "private")
async def ai_command(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Extract query after /ai
    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot_msg = await message.answer(
            "<b>AI ассистент</b>\n\n"
            "Использование: <code>/ai ваш вопрос</code>\n\n"
            "Бот проанализирует историю чата и ответит на ваш вопрос.",
            parse_mode=ParseMode.HTML,
        )
        await delete_command_and_response(message, bot_msg, 10)
        return

    query = parts[1].strip()

    # Check cooldown
    cooldown_seconds = await _get_cooldown_seconds(user_id, chat_id)
    if cooldown_seconds > 0:
        remaining = await _check_cooldown(user_id, chat_id)
        if remaining is not None:
            bot_msg = await message.answer(
                f"Подожди ещё {remaining} сек. перед следующим запросом.",
                parse_mode=ParseMode.HTML,
            )
            await delete_command_and_response(message, bot_msg, 5)
            return

    # Set cooldown before processing
    if cooldown_seconds > 0:
        await _set_cooldown(user_id, chat_id, cooldown_seconds)

    # Get chat history
    history = await get_chat_history(chat_id)

    # Build messages for the LLM
    llm_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"История чата:\n{history}\n\n"
                f"Вопрос от пользователя "
                f"{message.from_user.first_name or message.from_user.username or user_id}:\n"
                f"{query}"
            ),
        },
    ]

    # Send typing indicator
    await message.bot.send_chat_action(chat_id, ChatAction.TYPING)

    try:
        response = await _client.chat.completions.create(
            model=LOGFARE_MODEL,
            messages=llm_messages,
        )
        answer = response.choices[0].message.content
    except Exception as e:
        logger.error(f"AI request failed: {e}", exc_info=True)
        bot_msg = await message.answer(
            "Не удалось получить ответ от AI. Попробуйте позже.",
            parse_mode=ParseMode.HTML,
        )
        await delete_command_and_response(message, bot_msg, 10)
        return

    if not answer:
        answer = "AI не вернул ответ."

    # Parse [REF:...] tags from LLM response
    clean_answer, ref_ids = _parse_refs(answer)

    if not clean_answer:
        clean_answer = answer

    # If LLM referenced a specific message, reply to the first one
    reply_to_msg_id = ref_ids[0] if ref_ids else message.message_id

    try:
        await message.bot.send_message(
            chat_id=chat_id,
            text=clean_answer,
            reply_to_message_id=reply_to_msg_id,
            parse_mode=None,
        )
    except Exception:
        # Fallback: if reply_to the referenced msg fails (e.g. deleted),
        # just reply to the user's command message
        await message.reply(clean_answer, parse_mode=None)
