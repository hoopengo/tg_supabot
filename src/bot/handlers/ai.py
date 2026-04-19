"""AI command handler using OpenAI-compatible API via logfare.ai."""

import json
import logging

from aiogram import F, Router
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from openai import AsyncOpenAI

from bot.redis import message_cache
from bot.services.admin_service import is_admin, is_bot_creator, is_super_admin
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

_client = AsyncOpenAI(
    base_url=LOGFARE_BASE_URL,
    api_key="not-needed",
)

SYSTEM_PROMPT = (
    "Ты — полезный ассистент группового чата в Telegram. "
    "Тебе передаётся ПОЛНАЯ доступная история сообщений чата и вопрос пользователя.\n"
    "Отвечай на русском языке, кратко и по делу.\n\n"
    "ВАЖНО: Анализируй ВСЮ историю чата целиком, от самого начала до конца. "
    "Ответ может находиться в ЛЮБОЙ части истории, не только в последних сообщениях. "
    "Внимательно просмотри все сообщения перед тем, как ответить.\n\n"
    "Каждое сообщение в истории помечено идентификатором #msg_<id> и временной меткой.\n"
    "Если ты ссылаешься на конкретное сообщение из истории — вызови функцию "
    "reply_to с id этого сообщения. Бот автоматически сделает reply, чтобы "
    "пользователь мог перейти к нему в чате.\n"
    "НЕ вставляй id сообщений в текст ответа. Используй ТОЛЬКО функцию reply_to.\n"
    "Если ответа нет в истории — честно скажи, что не нашёл."
)

# OpenAI function / tool definition for reply_to
REPLY_TO_TOOL = {
    "type": "function",
    "function": {
        "name": "reply_to",
        "description": (
            "Сделать reply бота на конкретное сообщение из истории чата. "
            "Вызови эту функцию, если хочешь указать пользователю на "
            "конкретное сообщение."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "integer",
                    "description": "ID сообщения из истории (число из #msg_<id>)",
                },
            },
            "required": ["message_id"],
        },
    },
}


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


def _extract_tool_reply_id(response_message) -> int | None:
    """Extract message_id from reply_to tool call if present."""
    if not response_message.tool_calls:
        return None
    for tool_call in response_message.tool_calls:
        if tool_call.function.name == "reply_to":
            try:
                args = json.loads(tool_call.function.arguments)
                return int(args["message_id"])
            except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                continue
    return None


# --- Handler ---


@ai_router.message(Command("ask", ignore_case=True), F.chat.type != "private")
async def ai_command(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Extract query after /ask
    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot_msg = await message.answer(
            "<b>AI ассистент</b>\n\n"
            "Использование: <code>/ask ваш вопрос</code>\n\n"
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
            tools=[REPLY_TO_TOOL],
            tool_choice="auto",
        )
        resp_message = response.choices[0].message
        answer = resp_message.content or ""
        reply_to_msg_id = _extract_tool_reply_id(resp_message)

        # If the model returned a tool call without text content,
        # send the tool result back and get the final text answer.
        if not answer and resp_message.tool_calls:
            # Build follow-up messages with tool results
            follow_up = list(llm_messages)
            follow_up.append(resp_message.model_dump(exclude_none=True))
            for tool_call in resp_message.tool_calls:
                follow_up.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"status": "ok"}),
                })

            response2 = await _client.chat.completions.create(
                model=LOGFARE_MODEL,
                messages=follow_up,
            )
            answer = response2.choices[0].message.content or ""

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

    # Decide what to reply to: referenced message, or the user's /ask command
    target_msg_id = reply_to_msg_id if reply_to_msg_id else message.message_id

    try:
        await message.bot.send_message(
            chat_id=chat_id,
            text=answer,
            reply_to_message_id=target_msg_id,
            parse_mode=None,
        )
    except Exception:
        # Fallback: if reply_to the referenced msg fails (e.g. deleted),
        # just reply to the user's command message
        await message.reply(answer, parse_mode=None)
