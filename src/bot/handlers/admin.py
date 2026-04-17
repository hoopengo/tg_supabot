import logging

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.filters.queue_admin import IsAdminFilter, IsGroupChatFilter
from bot.keyboards.queue_kb import (
    AdminCallback,
    AdminListCallback,
    MEMBERS_PER_PAGE,
    queue_admin_keyboard,
    queue_user_keyboard,
    admin_queue_list_keyboard,
)
import html

from bot.services import queue_service
from bot.services.auto_delete import (
    delete_messages_later,
    PANEL_INACTIVITY_TIMEOUT,
)

logger = logging.getLogger(__name__)

admin_router = Router(name="admin")

PER_PAGE = 5


def _queue_list_text(queues, page: int = 0) -> str:
    """Build formatted queue list text for a page."""
    if not queues:
        return "Активных очередей нет. Создайте: /create_queue &lt;название&gt;"

    lines = ["<b>Очереди в этом чате:</b>", ""]
    for q in queues:
        status = "🟢" if q.status.value == "open" else "🔴"
        title = html.escape(q.title)
        lines.append(f"{status} {title}")
    return "\n".join(lines)


def _admin_panel_text(queue, members) -> str:
    """Build admin panel text with member list."""
    status_emoji = "🟢" if queue.status.value == "open" else "🔴"
    status_text = "Открыта" if queue.status.value == "open" else "Закрыта"
    title = html.escape(queue.title)

    lines = [
        f"⚙️ <b>Управление очередью</b>",
        f"{status_emoji} {title} — {status_text}",
        f"👥 Участников: {len(members)}",
    ]

    if members:
        lines.append("")
        for m in members:
            name = html.escape(m.first_name or m.username or str(m.user_id))
            lines.append(f"  {m.position}. {name}")

    return "\n".join(lines)


async def _update_queue_live_message_by_bot(
    bot: Bot,
    queue_id: int,
) -> None:
    """Update the live queue message via bot.edit_message_text."""
    queue = await queue_service.get_queue(queue_id)
    if not queue or not queue.message_id:
        return

    text = await queue_service.render_queue(queue_id)
    members = await queue_service.get_members(queue_id)
    is_open = queue.status.value == "open"
    kb = queue_user_keyboard(queue_id, is_open, members)

    try:
        await bot.edit_message_text(
            text,
            chat_id=queue.chat_id,
            message_id=queue.message_id,
            reply_markup=kb,
            parse_mode=ParseMode.HTML,
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.warning(f"Failed to edit queue message: {e}")
    except Exception as e:
        logger.warning(f"Failed to edit queue message: {e}")


async def _update_queue_live_message(
    message: Message,
    queue_id: int,
) -> None:
    """Update the live queue message (user-facing)."""
    text = await queue_service.render_queue(queue_id)
    members = await queue_service.get_members(queue_id)
    queue = await queue_service.get_queue(queue_id)
    if not queue:
        return

    is_open = queue.status.value == "open"
    kb = queue_user_keyboard(queue_id, is_open, members)

    try:
        await message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.warning(f"Failed to edit queue message: {e}")
    except Exception as e:
        logger.warning(f"Failed to edit queue message: {e}")


async def _update_admin_panel(
    message: Message,
    queue_id: int,
    page: int = 0,
) -> None:
    """Update the admin panel message with summary and management buttons."""
    queue = await queue_service.get_queue(queue_id)
    if not queue:
        return

    members = await queue_service.get_members(queue_id)
    text = _admin_panel_text(queue, members)
    kb = queue_admin_keyboard(queue_id, queue.status.value == "open", members, page)

    try:
        await message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.warning(f"Failed to edit admin panel: {e}")
    except Exception as e:
        logger.warning(f"Failed to edit admin panel: {e}")


# --- /admin command ---


@admin_router.message(Command("admin"), IsGroupChatFilter(), IsAdminFilter())
async def cmd_admin(message: Message):
    """Show admin panel. Reply to queue message for that queue's panel, otherwise show queue list."""
    chat_id = message.chat.id

    if message.reply_to_message:
        queue = await queue_service.get_queue_by_message(
            chat_id, message.reply_to_message.message_id
        )
        if queue:
            members = await queue_service.get_members(queue.id)
            text = _admin_panel_text(queue, members)
            kb = queue_admin_keyboard(
                queue.id, queue.status.value == "open", members, page=0
            )
            bot_msg = await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
            # Delete user command, auto-delete panel after inactivity
            await delete_messages_later(
                message.bot, chat_id, [message.message_id], 2
            )
            await delete_messages_later(
                message.bot, chat_id, [bot_msg.message_id], PANEL_INACTIVITY_TIMEOUT
            )
            return

    queues = await queue_service.get_active_queues(chat_id)
    kb = admin_queue_list_keyboard(queues, page=0, per_page=PER_PAGE)
    text = _queue_list_text(queues)

    bot_msg = await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    # Delete user command, auto-delete panel after inactivity
    await delete_messages_later(
        message.bot, chat_id, [message.message_id], 2
    )
    await delete_messages_later(
        message.bot, chat_id, [bot_msg.message_id], PANEL_INACTIVITY_TIMEOUT
    )


@admin_router.message(Command("queue"), IsGroupChatFilter(), IsAdminFilter())
async def cmd_queue(message: Message):
    await cmd_admin(message)


# --- Admin queue list callbacks ---


@admin_router.callback_query(AdminListCallback.filter(F.action == "select"))
async def cb_admin_select_queue(
    callback: CallbackQuery, callback_data: AdminListCallback
):
    queue_id = callback_data.queue_id
    queue = await queue_service.get_queue(queue_id)
    if not queue:
        await callback.answer("Очередь не найдена.", show_alert=True)
        return

    members = await queue_service.get_members(queue_id)
    text = _admin_panel_text(queue, members)
    kb = queue_admin_keyboard(queue_id, queue.status.value == "open", members, page=0)

    try:
        await callback.message.edit_text(
            text, reply_markup=kb, parse_mode=ParseMode.HTML
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            pass
    except Exception:
        pass
    await callback.answer()


@admin_router.callback_query(AdminListCallback.filter(F.action == "back"))
async def cb_admin_back_to_list(
    callback: CallbackQuery, callback_data: AdminListCallback
):
    chat_id = callback.message.chat.id
    page = callback_data.page
    queues = await queue_service.get_active_queues(chat_id)
    kb = admin_queue_list_keyboard(queues, page=page, per_page=PER_PAGE)
    text = _queue_list_text(queues)

    try:
        await callback.message.edit_text(
            text, reply_markup=kb, parse_mode=ParseMode.HTML
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            pass
    except Exception:
        pass
    await callback.answer()


@admin_router.callback_query(AdminListCallback.filter(F.action == "close"))
async def cb_admin_close_list(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


# --- Admin queue management callbacks ---


@admin_router.callback_query(AdminCallback.filter(F.action == "open"), IsAdminFilter())
async def cb_admin_open(
    callback: CallbackQuery, callback_data: AdminCallback, bot: Bot
):
    queue_id = callback_data.queue_id
    page = callback_data.page
    success, msg = await queue_service.open_queue(queue_id, callback.from_user.id)
    await callback.answer(msg, show_alert=not success)
    if success:
        await _update_admin_panel(callback.message, queue_id, page)
        await _update_queue_live_message_by_bot(bot, queue_id)


@admin_router.callback_query(AdminCallback.filter(F.action == "close"), IsAdminFilter())
async def cb_admin_close(
    callback: CallbackQuery, callback_data: AdminCallback, bot: Bot
):
    queue_id = callback_data.queue_id
    page = callback_data.page
    success, msg = await queue_service.close_queue(queue_id, callback.from_user.id)
    await callback.answer(msg, show_alert=not success)
    if success:
        await _update_admin_panel(callback.message, queue_id, page)
        await _update_queue_live_message_by_bot(bot, queue_id)


@admin_router.callback_query(AdminCallback.filter(F.action == "clear"), IsAdminFilter())
async def cb_admin_clear(
    callback: CallbackQuery, callback_data: AdminCallback, bot: Bot
):
    queue_id = callback_data.queue_id
    page = callback_data.page
    success, msg = await queue_service.clear_queue(queue_id, callback.from_user.id)
    await callback.answer(msg, show_alert=not success)
    if success:
        await _update_admin_panel(callback.message, queue_id, page)
        await _update_queue_live_message_by_bot(bot, queue_id)


@admin_router.callback_query(
    AdminCallback.filter(F.action == "remove_member"), IsAdminFilter()
)
async def cb_admin_remove_member(
    callback: CallbackQuery, callback_data: AdminCallback, bot: Bot
):
    queue_id = callback_data.queue_id
    page = callback_data.page
    target_user_id = callback_data.target
    success, msg = await queue_service.remove_user_from_queue(
        queue_id, target_user_id, callback.from_user.id
    )
    await callback.answer(msg, show_alert=not success)
    if success:
        await _update_admin_panel(callback.message, queue_id, page)
        await _update_queue_live_message_by_bot(bot, queue_id)


@admin_router.callback_query(
    AdminCallback.filter(F.action == "move_up"), IsAdminFilter()
)
async def cb_admin_move_up(
    callback: CallbackQuery, callback_data: AdminCallback, bot: Bot
):
    queue_id = callback_data.queue_id
    page = callback_data.page
    target_user_id = callback_data.target
    success, msg = await queue_service.move_user_up(
        queue_id, target_user_id, callback.from_user.id
    )
    await callback.answer(msg, show_alert=not success)
    if success:
        await _update_admin_panel(callback.message, queue_id, page)
        await _update_queue_live_message_by_bot(bot, queue_id)


@admin_router.callback_query(
    AdminCallback.filter(F.action == "move_down"), IsAdminFilter()
)
async def cb_admin_move_down(
    callback: CallbackQuery, callback_data: AdminCallback, bot: Bot
):
    queue_id = callback_data.queue_id
    page = callback_data.page
    target_user_id = callback_data.target
    success, msg = await queue_service.move_user_down(
        queue_id, target_user_id, callback.from_user.id
    )
    await callback.answer(msg, show_alert=not success)
    if success:
        await _update_admin_panel(callback.message, queue_id, page)
        await _update_queue_live_message_by_bot(bot, queue_id)


@admin_router.callback_query(
    AdminCallback.filter(F.action == "members_page"), IsAdminFilter()
)
async def cb_admin_members_page(callback: CallbackQuery, callback_data: AdminCallback):
    queue_id = callback_data.queue_id
    page = callback_data.page
    await _update_admin_panel(callback.message, queue_id, page)
    await callback.answer()


@admin_router.callback_query(
    AdminCallback.filter(F.action == "delete"), IsAdminFilter()
)
async def cb_admin_delete(
    callback: CallbackQuery, callback_data: AdminCallback, bot: Bot
):
    queue_id = callback_data.queue_id
    queue = await queue_service.get_queue(queue_id)
    chat_id = queue.chat_id if queue else None
    message_id = queue.message_id if queue else None

    success, msg = await queue_service.delete_queue(queue_id, callback.from_user.id)
    await callback.answer(msg, show_alert=not success)
    if success:
        if message_id:
            try:
                await bot.delete_message(chat_id, message_id)
            except Exception:
                pass
        try:
            await callback.message.delete()
        except Exception:
            pass


@admin_router.callback_query(
    AdminCallback.filter(F.action == "close_panel"), IsAdminFilter()
)
async def cb_admin_close_panel(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


@admin_router.callback_query(
    AdminCallback.filter(F.action == "refresh"), IsAdminFilter()
)
async def cb_admin_refresh(
    callback: CallbackQuery, callback_data: AdminCallback, bot: Bot
):
    queue_id = callback_data.queue_id
    page = callback_data.page
    await _update_admin_panel(callback.message, queue_id, page)
    await callback.answer("Обновлено")
