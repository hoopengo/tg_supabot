import logging

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.filters.queue_admin import IsGroupChatFilter
from bot.keyboards.raffle_kb import RaffleCallback, raffle_keyboard
from bot.services import admin_service, raffle_service
from bot.services.auto_delete import (
    PANEL_INACTIVITY_TIMEOUT,
    delete_command_and_response,
    delete_messages_later,
)

logger = logging.getLogger(__name__)

raffle_router = Router(name="raffles")

MAX_TOPICS = 50


@raffle_router.message(Command("raffle"), IsGroupChatFilter())
async def cmd_raffle(message: Message, bot: Bot):
    """Usage: /raffle <количество докладов> <время>  e.g. /raffle 10 30m"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await admin_service.is_admin(chat_id, user_id):
        bot_msg = await message.answer("Недостаточно прав для создания розыгрыша.")
        await delete_command_and_response(message, bot_msg, delay=10)
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        bot_msg = await message.answer(
            "Использование: /raffle <количество докладов> <время>\n"
            "Время: 30м / 30m / 1ч / 1h / 1ч30м\n"
            "Пример: /raffle 10 30м"
        )
        await delete_command_and_response(message, bot_msg, delay=15)
        return

    try:
        topic_count = int(args[1])
    except ValueError:
        bot_msg = await message.answer("Количество докладов должно быть числом.")
        await delete_command_and_response(message, bot_msg, delay=10)
        return

    if not 1 <= topic_count <= MAX_TOPICS:
        bot_msg = await message.answer(
            f"Количество докладов должно быть от 1 до {MAX_TOPICS}."
        )
        await delete_command_and_response(message, bot_msg, delay=10)
        return

    duration = raffle_service.parse_duration(args[2])
    if duration is None:
        bot_msg = await message.answer(
            "Не понял время. Примеры: 30м, 30m, 1ч, 1h, 1ч30м, 2h."
        )
        await delete_command_and_response(message, bot_msg, delay=10)
        return

    if await raffle_service.get_active_raffle(chat_id):
        bot_msg = await message.answer(
            "В этом чате уже идёт розыгрыш. Дождитесь его окончания."
        )
        await delete_command_and_response(message, bot_msg, delay=10)
        return

    raffle = await raffle_service.create_raffle(
        chat_id=chat_id,
        topic_count=topic_count,
        created_by=user_id,
        duration=duration,
    )

    text = await raffle_service.render_raffle(raffle)
    kb = raffle_keyboard(raffle.id, active=True)
    sent = await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await raffle_service.update_raffle_message_id(raffle.id, sent.message_id)

    await delete_messages_later(message.bot, chat_id, [message.message_id], delay=2)


@raffle_router.callback_query(RaffleCallback.filter(F.action == "toggle"))
async def cb_raffle_toggle(
    callback: CallbackQuery, callback_data: RaffleCallback, bot: Bot
):
    raffle_id = callback_data.raffle_id
    success, now_participating, msg = await raffle_service.toggle_participation(
        raffle_id,
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
    )
    if not success:
        await callback.answer(msg, show_alert=True)
        return
    await callback.answer(msg)

    raffle = await raffle_service.get_raffle(raffle_id)
    if not raffle:
        return
    try:
        await callback.message.edit_text(
            await raffle_service.render_raffle(raffle),
            reply_markup=raffle_keyboard(
                raffle_id, active=raffle.status.value == "active"
            ),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        if "message is not modified" not in str(e):
            logger.warning(f"Failed to refresh raffle message: {e}")


@raffle_router.callback_query(RaffleCallback.filter(F.action == "close"))
async def cb_raffle_close(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


@raffle_router.message(Command("raffle_stop"), IsGroupChatFilter())
async def cmd_raffle_stop(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await admin_service.is_admin(chat_id, user_id):
        bot_msg = await message.answer("Недостаточно прав.")
        await delete_command_and_response(message, bot_msg, delay=10)
        return

    raffle = await raffle_service.get_active_raffle(chat_id)
    if not raffle:
        bot_msg = await message.answer("Активного розыгрыша нет.")
        await delete_command_and_response(message, bot_msg, delay=10)
        return

    success, msg = await raffle_service.cancel_raffle(raffle.id, user_id)
    if success and raffle.message_id:
        await delete_messages_later(bot, chat_id, [raffle.message_id], delay=2)
    bot_msg = await message.answer(msg)
    await delete_messages_later(
        bot, chat_id, [bot_msg.message_id], delay=PANEL_INACTIVITY_TIMEOUT
    )
