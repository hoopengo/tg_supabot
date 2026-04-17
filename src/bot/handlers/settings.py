import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.db.models import ChatSettingsModel
from bot.filters.queue_admin import IsGroupChatFilter, IsAdminFilter
from bot.repositories import settings_repo
from bot.services.auto_delete import delete_messages_later, PANEL_INACTIVITY_TIMEOUT

logger = logging.getLogger(__name__)

settings_router = Router(name="settings")


class SettingsCallback(CallbackData, prefix="stg"):
    action: str  # toggle, close, refresh
    command: str = ""
    page: int = 0


COMMANDS_PER_PAGE = 8


def _build_settings_keyboard(
    settings: ChatSettingsModel, page: int = 0
) -> InlineKeyboardMarkup:
    """Build inline keyboard for command toggles."""
    commands = list(ChatSettingsModel.COMMAND_MAP.keys())
    total_pages = max(1, (len(commands) + COMMANDS_PER_PAGE - 1) // COMMANDS_PER_PAGE)
    page = min(page, total_pages - 1)

    start = page * COMMANDS_PER_PAGE
    page_commands = commands[start : start + COMMANDS_PER_PAGE]

    rows: list[list[InlineKeyboardButton]] = []

    for cmd in page_commands:
        enabled = settings.is_command_enabled(cmd)
        status = "✅" if enabled else "❌"
        label = ChatSettingsModel.COMMAND_LABELS.get(cmd, cmd)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{status} {label}",
                    callback_data=SettingsCallback(
                        action="toggle", command=cmd, page=page
                    ).pack(),
                ),
            ]
        )

    # Navigation
    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=SettingsCallback(
                        action="refresh", page=page - 1
                    ).pack(),
                )
            )
        nav.append(
            InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data=SettingsCallback(action="noop").pack(),
            )
        )
        if page < total_pages - 1:
            nav.append(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=SettingsCallback(
                        action="refresh", page=page + 1
                    ).pack(),
                )
            )
        rows.append(nav)

    rows.append(
        [
            InlineKeyboardButton(
                text="✖ Закрыть",
                callback_data=SettingsCallback(action="close").pack(),
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


@settings_router.message(Command("settings"), IsGroupChatFilter(), IsAdminFilter())
async def cmd_settings(message: Message):
    """Show settings panel for toggling commands."""
    settings = await settings_repo.get_settings(message.chat.id)
    kb = _build_settings_keyboard(settings)
    bot_msg = await message.answer(
        "⚙️ <b>Настройки команд</b>\n\n"
        "Нажмите на команду, чтобы включить или выключить её:",
        reply_markup=kb,
        parse_mode=ParseMode.HTML,
    )
    chat_id = message.chat.id
    # Delete user command quickly, panel after inactivity
    await delete_messages_later(message.bot, chat_id, [message.message_id], delay=2)
    await delete_messages_later(message.bot, chat_id, [bot_msg.message_id], PANEL_INACTIVITY_TIMEOUT)


@settings_router.callback_query(SettingsCallback.filter(F.action == "toggle"), IsAdminFilter())
async def cb_settings_toggle(callback: CallbackQuery, callback_data: SettingsCallback):
    chat_id = callback.message.chat.id
    command = callback_data.command
    page = callback_data.page

    success, new_state = await settings_repo.toggle_command(chat_id, command)
    if not success:
        await callback.answer("Не удалось изменить настройку.", show_alert=True)
        return

    label = ChatSettingsModel.COMMAND_LABELS.get(command, command)
    state_text = "включена" if new_state else "выключена"
    await callback.answer(f"{label} — {state_text}")

    settings = await settings_repo.get_settings(chat_id)
    kb = _build_settings_keyboard(settings, page)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass


@settings_router.callback_query(SettingsCallback.filter(F.action == "refresh"))
async def cb_settings_refresh(callback: CallbackQuery, callback_data: SettingsCallback):
    chat_id = callback.message.chat.id
    page = callback_data.page

    settings = await settings_repo.get_settings(chat_id)
    kb = _build_settings_keyboard(settings, page)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@settings_router.callback_query(SettingsCallback.filter(F.action == "close"))
async def cb_settings_close(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()
