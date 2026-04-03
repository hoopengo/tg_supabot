import logging

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.filters.queue_admin import IsGroupChatFilter
from bot.keyboards.queue_kb import (
    QueueCallback,
    QueueListCallback,
    queue_list_keyboard,
    queue_user_keyboard,
    swap_confirmation_keyboard,
    swap_list_keyboard,
)
from bot.services import admin_service, queue_service, swap_service

logger = logging.getLogger(__name__)

queue_router = Router(name="queues")


def _check_owner(callback: CallbackQuery, owner: int) -> bool:
    """Check if the user is allowed to interact. owner=0 means no restriction."""
    if owner and callback.from_user.id != owner:
        return False
    return True


async def _update_queue_message(
    message: Message, queue_id: int, owner: int = 0
) -> None:
    """Edit the live queue message with current state and user keyboard."""
    text = await queue_service.render_queue(queue_id)
    members = await queue_service.get_members(queue_id)
    queue = await queue_service.get_queue(queue_id)
    if not queue:
        return
    is_open = queue.status.value == "open"
    kb = queue_user_keyboard(queue_id, is_open, members, owner)
    try:
        await message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Failed to edit queue message: {e}")


async def _update_main_queue_message(bot: Bot, queue_id: int, owner: int = 0) -> None:
    """Update the main pinned queue message."""
    queue = await queue_service.get_queue(queue_id)
    if not queue or not queue.message_id:
        return
    text = await queue_service.render_queue(queue_id)
    members = await queue_service.get_members(queue_id)
    is_open = queue.status.value == "open"
    kb = queue_user_keyboard(queue_id, is_open, members, owner)
    try:
        await bot.edit_message_text(
            text,
            chat_id=queue.chat_id,
            message_id=queue.message_id,
            reply_markup=kb,
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.warning(f"Failed to edit main queue message: {e}")


# --- /create_queue command ---


@queue_router.message(Command("create_queue"), IsGroupChatFilter())
async def cmd_create_queue(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await admin_service.is_admin(chat_id, user_id):
        await message.answer("Недостаточно прав для создания очереди.")
        return
    title = message.text.split(maxsplit=1)
    if len(title) < 2 or not title[1].strip():
        await message.answer("Использование: /create_queue <название очереди>")
        return
    queue_title = title[1].strip()
    queue = await queue_service.create_queue(chat_id, queue_title, user_id)
    text = await queue_service.render_queue(queue.id)
    kb = queue_user_keyboard(queue.id, is_open=True)
    sent = await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await queue_service.update_queue_message_id(queue.id, sent.message_id)
    try:
        await bot.pin_chat_message(chat_id, sent.message_id, disable_notification=True)
    except Exception:
        pass


# --- User callback handlers ---


@queue_router.callback_query(QueueCallback.filter(F.action == "join"))
async def cb_queue_join(
    callback: CallbackQuery, callback_data: QueueCallback, bot: Bot
):
    queue_id = callback_data.queue_id
    owner = callback_data.owner

    if not _check_owner(callback, owner):
        await callback.answer("Это не ваша панель.", show_alert=True)
        return

    user_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name
    success, msg = await queue_service.join_queue(
        queue_id,
        user_id,
        username,
        first_name=first_name,
    )
    await callback.answer(msg, show_alert=not success)
    if success:
        await _update_queue_message(
            callback.message,
            queue_id,
            owner=owner,
        )
        await _update_main_queue_message(bot, queue_id, owner=owner)


@queue_router.callback_query(QueueCallback.filter(F.action == "leave"))
async def cb_queue_leave(
    callback: CallbackQuery, callback_data: QueueCallback, bot: Bot
):
    queue_id = callback_data.queue_id
    owner = callback_data.owner

    if not _check_owner(callback, owner):
        await callback.answer("Это не ваша панель.", show_alert=True)
        return

    user_id = callback.from_user.id
    success, msg = await queue_service.leave_queue(queue_id, user_id)
    await callback.answer(msg, show_alert=not success)
    if success:
        await _update_queue_message(
            callback.message,
            queue_id,
            owner=owner,
        )
        await _update_main_queue_message(bot, queue_id, owner=owner)


@queue_router.callback_query(QueueCallback.filter(F.action == "swap_list"))
async def cb_swap_list(callback: CallbackQuery, callback_data: QueueCallback):
    queue_id = callback_data.queue_id
    owner = callback_data.owner

    if not _check_owner(callback, owner):
        await callback.answer("Это не ваша панель.", show_alert=True)
        return

    user_id = callback.from_user.id
    members = await queue_service.get_members(queue_id)

    in_queue = any(m.user_id == user_id for m in members)
    if not in_queue:
        await callback.answer("Вы не в очереди.", show_alert=True)
        return

    if len(members) < 2:
        await callback.answer("Недостаточно участников для обмена.", show_alert=True)
        return
    kb = swap_list_keyboard(queue_id, members, user_id, owner)
    await callback.message.edit_text(
        "Выберите пользователя для обмена местами:",
        reply_markup=kb,
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@queue_router.callback_query(QueueCallback.filter(F.action == "back_to_queue"))
async def cb_back_to_queue(callback: CallbackQuery, callback_data: QueueCallback):
    queue_id = callback_data.queue_id
    owner = callback_data.owner
    await _update_queue_message(
        callback.message,
        queue_id,
        owner=owner,
    )
    await callback.answer()


@queue_router.callback_query(QueueCallback.filter(F.action == "swap_request"))
async def cb_swap_request(callback: CallbackQuery, callback_data: QueueCallback):
    queue_id = callback_data.queue_id
    from_user_id = callback.from_user.id
    to_user_id = callback_data.target
    success, msg, swap = await swap_service.create_swap_request(
        queue_id,
        from_user_id,
        to_user_id,
    )
    if not success or not swap:
        await callback.answer(msg, show_alert=True)
        return
    from_user_name = (
        callback.from_user.first_name
        or callback.from_user.username
        or str(from_user_id)
    )
    swap_kb = swap_confirmation_keyboard(swap.id, queue_id)
    await callback.message.answer(
        f"🔄 <b>{from_user_name}</b> хочет поменяться с тобой местами.\n"
        f"Запрос действителен 5 минут.",
        reply_markup=swap_kb,
        parse_mode=ParseMode.HTML,
    )
    await callback.answer("Запрос отправлен!")


@queue_router.callback_query(QueueCallback.filter(F.action == "swap_confirm"))
async def cb_swap_confirm(
    callback: CallbackQuery, callback_data: QueueCallback, bot: Bot
):
    swap_id = callback_data.target
    user_id = callback.from_user.id
    success, msg = await swap_service.approve_swap(swap_id, user_id)
    await callback.answer(msg, show_alert=not success)
    if success:
        queue_id = callback_data.queue_id
        await _update_queue_message(callback.message, queue_id)
        await _update_main_queue_message(bot, queue_id)
        try:
            await callback.message.delete()
        except Exception:
            pass


@queue_router.callback_query(QueueCallback.filter(F.action == "swap_reject"))
async def cb_swap_reject(callback: CallbackQuery, callback_data: QueueCallback):
    swap_id = callback_data.target
    user_id = callback.from_user.id
    success, msg = await swap_service.reject_swap(swap_id, user_id)
    await callback.answer(msg, show_alert=not success)
    if success:
        try:
            await callback.message.delete()
        except Exception:
            pass


# --- /switch command ---


@queue_router.message(Command("switch"), IsGroupChatFilter())
async def cmd_switch(message: Message, bot: Bot):
    chat_id = message.chat.id
    from_user_id = message.from_user.id
    queues = await queue_service.get_active_queues(chat_id)
    if not queues:
        await message.answer("В этом чате нет активных очередей.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer("Использование: /switch @username")
        return
    target_username = args[1].strip().lstrip("@")
    if not target_username:
        await message.answer("Использование: /switch @username")
        return
    queue = queues[0]
    members = await queue_service.get_members(queue.id)
    target_member = None
    for m in members:
        if m.username and m.username.lower() == target_username.lower():
            target_member = m
            break
    if not target_member:
        await message.answer(
            f"Пользователь @{target_username} не найден в очереди «{queue.title}»."
        )
        return
    success, msg, swap = await swap_service.create_swap_request(
        queue.id,
        from_user_id,
        target_member.user_id,
    )
    if not success or not swap:
        await message.answer(msg)
        return
    from_user_name = (
        message.from_user.first_name or message.from_user.username or str(from_user_id)
    )
    target_name = target_member.first_name or f"@{target_username}"
    swap_kb = swap_confirmation_keyboard(swap.id, queue.id)
    await message.answer(
        f"🔄 <b>{from_user_name}</b> хочет поменяться с <b>{target_name}</b> местами.\n"
        f"Запрос действителен 5 минут.",
        reply_markup=swap_kb,
        parse_mode=ParseMode.HTML,
    )


# --- Queue close ---


@queue_router.callback_query(QueueCallback.filter(F.action == "close"))
async def cb_queue_close(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


# --- /queues command ---


@queue_router.message(Command("queues"), IsGroupChatFilter())
async def cmd_queues(message: Message):
    queues = await queue_service.get_active_queues(message.chat.id)
    if not queues:
        await message.answer("В этом чате нет активных очередей.")
        return

    lines = ["<b>Очереди:</b>", ""]
    for q in queues:
        status = "🟢" if q.status.value == "open" else "🔴"
        count = await queue_service.get_member_count(q.id)
        lines.append(f"{status} <b>{q.title}</b> — {count} чел.")
    text = "\n".join(lines)

    kb = queue_list_keyboard(queues)
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@queue_router.callback_query(QueueListCallback.filter(F.action == "view"))
async def cb_queues_view(
    callback: CallbackQuery, callback_data: QueueListCallback, bot: Bot
):
    queue_id = callback_data.queue_id
    queue = await queue_service.get_queue(queue_id)
    if not queue:
        await callback.answer("Очередь не найдена.", show_alert=True)
        return

    owner = callback.from_user.id
    text = await queue_service.render_queue(queue_id)
    members = await queue_service.get_members(queue_id)
    is_open = queue.status.value == "open"
    kb = queue_user_keyboard(queue_id, is_open, members, owner=owner)

    try:
        await callback.message.edit_text(
            text, reply_markup=kb, parse_mode=ParseMode.HTML
        )
    except Exception:
        pass
    await _update_main_queue_message(bot, queue_id)
    await callback.answer()


@queue_router.callback_query(QueueListCallback.filter(F.action == "close"))
async def cb_queues_close(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()
