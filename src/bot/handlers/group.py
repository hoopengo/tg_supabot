import html
import logging
from typing import Sequence

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.filters.queue_admin import IsAdminFilter, IsGroupChatFilter
from bot.repositories import group_repo
from bot.services import admin_service, queue_service
from bot.services import group_service
from bot.services.auto_delete import delete_command_and_response, delete_messages_later

logger = logging.getLogger(__name__)

group_router = Router(name="group")


# --- Callback data ---


class GroupSelectCallback(CallbackData, prefix="grp"):
    action: str  # toggle, confirm, cancel
    queue_id: int = 0


class GroupManageCallback(CallbackData, prefix="grpm"):
    action: str  # delete, refresh, close, select
    group_id: int = 0


# --- In-memory selection state ---
# Key: (chat_id, user_id) → set of selected queue_ids
_selections: dict[tuple[int, int], set[int]] = {}


def _get_selection(chat_id: int, user_id: int) -> set[int]:
    return _selections.setdefault((chat_id, user_id), set())


def _clear_selection(chat_id: int, user_id: int) -> None:
    _selections.pop((chat_id, user_id), None)


# --- Keyboard builders ---


def _group_select_keyboard(
    queues: Sequence, selected: set[int]
) -> InlineKeyboardMarkup:
    """Build queue selection keyboard with checkboxes."""
    rows: list[list[InlineKeyboardButton]] = []

    for q in queues:
        check = "☑" if q.id in selected else "☐"
        title = q.title
        if len(title) > 30:
            title = title[:30] + "…"
        rows.append([
            InlineKeyboardButton(
                text=f"{check} {title}",
                callback_data=GroupSelectCallback(
                    action="toggle", queue_id=q.id
                ).pack(),
            )
        ])

    # Bottom row: confirm (if ≥2 selected) and cancel
    bottom: list[InlineKeyboardButton] = []
    if len(selected) >= 2:
        bottom.append(
            InlineKeyboardButton(
                text=f"✅ Создать ({len(selected)})",
                callback_data=GroupSelectCallback(action="confirm").pack(),
            )
        )
    bottom.append(
        InlineKeyboardButton(
            text="✖ Отмена",
            callback_data=GroupSelectCallback(action="cancel").pack(),
        )
    )
    rows.append(bottom)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _group_list_keyboard(groups: Sequence) -> InlineKeyboardMarkup:
    """Build keyboard listing existing groups for management."""
    rows: list[list[InlineKeyboardButton]] = []

    for g in groups:
        title = g.title or f"Группа #{g.id}"
        if len(title) > 28:
            title = title[:28] + "…"
        rows.append([
            InlineKeyboardButton(
                text=f"📋 {title}",
                callback_data=GroupManageCallback(
                    action="select", group_id=g.id
                ).pack(),
            )
        ])

    if not groups:
        rows.append([
            InlineKeyboardButton(
                text="Нет групп",
                callback_data=GroupManageCallback(action="close").pack(),
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text="✖ Закрыть",
            callback_data=GroupManageCallback(action="close").pack(),
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _group_detail_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """Build keyboard for managing a specific group."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 Обновить сообщение",
                callback_data=GroupManageCallback(
                    action="refresh", group_id=group_id
                ).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🗑 Удалить группу",
                callback_data=GroupManageCallback(
                    action="delete", group_id=group_id
                ).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=GroupManageCallback(action="back").pack(),
            ),
        ],
    ])


def _selection_text(selected_count: int) -> str:
    if selected_count == 0:
        return "Выберите очереди для объединения в группу:"
    if selected_count == 1:
        return "Выберите ещё минимум 1 очередь:"
    return f"Выбрано: {selected_count}. Нажмите «Создать» или выберите ещё."


# --- /group command (create) ---


@group_router.message(Command("group"), IsGroupChatFilter())
async def cmd_group(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Only admin / super admin / bot creator
    if not await admin_service.is_admin(chat_id, user_id):
        bot_msg = await message.answer("Недостаточно прав для создания группы.")
        await delete_command_and_response(message, bot_msg, delay=10)
        return

    queues = await queue_service.get_active_queues(chat_id)
    if len(queues) < 2:
        bot_msg = await message.answer(
            "Нужно минимум 2 очереди в чате для создания группы."
        )
        await delete_command_and_response(message, bot_msg, delay=10)
        return

    # Reset selection and show picker
    _clear_selection(chat_id, user_id)
    selected = _get_selection(chat_id, user_id)
    kb = _group_select_keyboard(queues, selected)
    bot_msg = await message.answer(
        _selection_text(0), reply_markup=kb, parse_mode=ParseMode.HTML
    )

    # Delete user command
    await delete_messages_later(message.bot, chat_id, [message.message_id], delay=2)


# --- /groups command (manage) ---


@group_router.message(Command("groups"), IsGroupChatFilter(), IsAdminFilter())
async def cmd_groups(message: Message):
    chat_id = message.chat.id
    groups = await group_repo.get_groups_by_chat(chat_id)

    if not groups:
        bot_msg = await message.answer("В этом чате нет групп очередей.")
        await delete_command_and_response(message, bot_msg, delay=10)
        return

    kb = _group_list_keyboard(groups)
    bot_msg = await message.answer(
        "<b>Группы очередей:</b>", reply_markup=kb, parse_mode=ParseMode.HTML
    )
    await delete_messages_later(message.bot, chat_id, [message.message_id], delay=2)


# --- Toggle callback ---


@group_router.callback_query(GroupSelectCallback.filter(F.action == "toggle"))
async def cb_group_toggle(
    callback: CallbackQuery, callback_data: GroupSelectCallback
):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id

    # Check permission
    if not await admin_service.is_admin(chat_id, user_id):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    queue_id = callback_data.queue_id
    selected = _get_selection(chat_id, user_id)

    # Toggle
    if queue_id in selected:
        selected.discard(queue_id)
    else:
        selected.add(queue_id)

    # Refresh keyboard
    queues = await queue_service.get_active_queues(chat_id)
    kb = _group_select_keyboard(queues, selected)
    text = _selection_text(len(selected))

    try:
        await callback.message.edit_text(
            text, reply_markup=kb, parse_mode=ParseMode.HTML
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.warning(f"Failed to edit group select: {e}")
    await callback.answer()


# --- Confirm callback ---


@group_router.callback_query(GroupSelectCallback.filter(F.action == "confirm"))
async def cb_group_confirm(callback: CallbackQuery, bot: Bot):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id

    if not await admin_service.is_admin(chat_id, user_id):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    selected = _get_selection(chat_id, user_id)
    if len(selected) < 2:
        await callback.answer("Выберите минимум 2 очереди.", show_alert=True)
        return

    # Preserve insertion order based on queue positions
    queues = await queue_service.get_active_queues(chat_id)
    queue_ids = [q.id for q in queues if q.id in selected]

    # Create the group
    group = await group_service.create_group(chat_id, queue_ids, user_id)

    # Delete the selection message
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Send the group message
    text = await group_service.render_group(group.id)
    sent = await bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)

    # Save message_id
    await group_repo.update_group_message_id(group.id, sent.message_id)

    # Pin
    try:
        await bot.pin_chat_message(
            chat_id, sent.message_id, disable_notification=True
        )
    except Exception:
        pass

    _clear_selection(chat_id, user_id)
    await callback.answer("Группа создана!")


# --- Cancel callback ---


@group_router.callback_query(GroupSelectCallback.filter(F.action == "cancel"))
async def cb_group_cancel(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    _clear_selection(chat_id, user_id)

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Отменено.")


# --- Group management callbacks ---


@group_router.callback_query(
    GroupManageCallback.filter(F.action == "select"), IsAdminFilter()
)
async def cb_group_manage_select(
    callback: CallbackQuery, callback_data: GroupManageCallback
):
    group_id = callback_data.group_id
    group = await group_repo.get_group(group_id)
    if not group:
        await callback.answer("Группа не найдена.", show_alert=True)
        return

    queue_ids = await group_repo.get_group_queue_ids(group_id)
    lines = [f"<b>📋 {html.escape(group.title or 'Группа')}</b>", ""]
    lines.append(f"Очередей: {len(queue_ids)}")
    for qid in queue_ids:
        q = await queue_service.get_queue(qid)
        if q:
            lines.append(f"  • {html.escape(q.title)}")

    kb = _group_detail_keyboard(group_id)
    try:
        await callback.message.edit_text(
            "\n".join(lines), reply_markup=kb, parse_mode=ParseMode.HTML
        )
    except TelegramBadRequest:
        pass
    await callback.answer()


@group_router.callback_query(
    GroupManageCallback.filter(F.action == "back"), IsAdminFilter()
)
async def cb_group_manage_back(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    groups = await group_repo.get_groups_by_chat(chat_id)
    kb = _group_list_keyboard(groups)
    try:
        await callback.message.edit_text(
            "<b>Группы очередей:</b>", reply_markup=kb, parse_mode=ParseMode.HTML
        )
    except TelegramBadRequest:
        pass
    await callback.answer()


@group_router.callback_query(
    GroupManageCallback.filter(F.action == "refresh"), IsAdminFilter()
)
async def cb_group_manage_refresh(
    callback: CallbackQuery, callback_data: GroupManageCallback, bot: Bot
):
    group_id = callback_data.group_id
    group = await group_repo.get_group(group_id)
    if not group:
        await callback.answer("Группа не найдена.", show_alert=True)
        return

    # Force-update the group message
    await group_service._do_update_group_message(bot, group_id)
    await callback.answer("Сообщение группы обновлено.")


@group_router.callback_query(
    GroupManageCallback.filter(F.action == "delete"), IsAdminFilter()
)
async def cb_group_manage_delete(
    callback: CallbackQuery, callback_data: GroupManageCallback, bot: Bot
):
    group_id = callback_data.group_id
    group = await group_repo.get_group(group_id)
    if not group:
        await callback.answer("Группа не найдена.", show_alert=True)
        return

    # Delete group message from chat
    if group.message_id:
        try:
            await bot.delete_message(group.chat_id, group.message_id)
        except Exception:
            pass

    await group_repo.delete_group(group_id)

    # Go back to list
    chat_id = callback.message.chat.id
    groups = await group_repo.get_groups_by_chat(chat_id)
    if groups:
        kb = _group_list_keyboard(groups)
        try:
            await callback.message.edit_text(
                "<b>Группы очередей:</b>", reply_markup=kb, parse_mode=ParseMode.HTML
            )
        except TelegramBadRequest:
            pass
    else:
        try:
            await callback.message.delete()
        except Exception:
            pass

    await callback.answer("Группа удалена.")


@group_router.callback_query(
    GroupManageCallback.filter(F.action == "close"), IsAdminFilter()
)
async def cb_group_manage_close(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()
