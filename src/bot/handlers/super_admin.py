import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.db.methods import get_user_by_username
from bot.db.models import AdminRole
from bot.filters.queue_admin import IsGroupChatFilter, IsSuperAdminFilter
from bot.keyboards.queue_kb import (
    SuperAdminCallback,
    admin_management_keyboard,
)
from bot.services import admin_service
from bot.services.auto_delete import delete_command_and_response, delete_messages_later, PANEL_INACTIVITY_TIMEOUT

logger = logging.getLogger(__name__)

super_admin_router = Router(name="super_admin")


def _admin_list_text(admins) -> str:
    lines = ["<b>Администраторы:</b>", ""]
    for admin in admins:
        role_label = (
            "⭐ Супер-админ" if admin.role == AdminRole.SUPER_ADMIN else "👤 Админ"
        )
        lines.append(f"• {admin.display_name} (ID:{admin.user_id}) — {role_label}")
    return "\n".join(lines)


# --- /superadmin command ---


@super_admin_router.message(
    Command("superadmin"), IsGroupChatFilter(), IsSuperAdminFilter()
)
async def cmd_superadmin(message: Message):
    chat_id = message.chat.id
    admins = await admin_service.list_admins(chat_id)

    if not admins:
        bot_msg = await message.answer(
            "<b>Панель супер-администратора</b>\n\nНет администраторов.\nИспользуйте /add_admin для добавления.",
            parse_mode=ParseMode.HTML,
        )
        await delete_messages_later(
            message.bot, chat_id, [message.message_id], 2
        )
        await delete_messages_later(
            message.bot, chat_id, [bot_msg.message_id], PANEL_INACTIVITY_TIMEOUT
        )
        return

    text = _admin_list_text(admins)
    kb = admin_management_keyboard(admins, chat_id)
    bot_msg = await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    # Delete user command, auto-delete panel after inactivity
    await delete_messages_later(
        message.bot, chat_id, [message.message_id], 2
    )
    await delete_messages_later(
        message.bot, chat_id, [bot_msg.message_id], PANEL_INACTIVITY_TIMEOUT
    )


# --- /add_admin command ---


@super_admin_router.message(
    Command("add_admin"), IsGroupChatFilter(), IsSuperAdminFilter()
)
async def cmd_add_admin(message: Message):
    chat_id = message.chat.id
    added_by = message.from_user.id

    target_user_id = None
    first_name = None
    username = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user_id = message.reply_to_message.from_user.id
        first_name = message.reply_to_message.from_user.first_name
        username = message.reply_to_message.from_user.username
    else:
        args = message.text.split(maxsplit=1)
        if len(args) < 2 or not args[1].strip():
            bot_msg = await message.answer(
                "Ответьте на сообщение пользователя или: /add_admin @username"
            )
            await delete_command_and_response(message, bot_msg, delay=10)
            return

        raw = args[1].strip()
        if raw.startswith("@"):
            username = raw.lstrip("@")
            user = await get_user_by_username(username, chat_id)
            if not user:
                bot_msg = await message.answer(
                    "Пользователь не найден в базе. Он должен хотя бы раз написать в чат."
                )
                await delete_command_and_response(message, bot_msg, delay=10)
                return
            target_user_id = user.user_id
            first_name = user.first_name
        else:
            try:
                target_user_id = int(raw)
            except ValueError:
                bot_msg = await message.answer("Укажите @username или числовой ID.")
                await delete_command_and_response(message, bot_msg, delay=10)
                return

    success, msg = await admin_service.add_admin(
        chat_id, target_user_id, added_by, first_name=first_name, username=username
    )
    bot_msg = await message.answer(msg)
    await delete_command_and_response(message, bot_msg)


# --- /remove_admin command ---


@super_admin_router.message(
    Command("remove_admin"), IsGroupChatFilter(), IsSuperAdminFilter()
)
async def cmd_remove_admin(message: Message):
    chat_id = message.chat.id
    removed_by = message.from_user.id

    target_user_id = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user_id = message.reply_to_message.from_user.id
    else:
        args = message.text.split(maxsplit=1)
        if len(args) < 2 or not args[1].strip():
            bot_msg = await message.answer(
                "Ответьте на сообщение администратора или: /remove_admin <user_id>"
            )
            await delete_command_and_response(message, bot_msg, delay=10)
            return
        try:
            target_user_id = int(args[1].strip())
        except ValueError:
            bot_msg = await message.answer("Неверный формат user_id.")
            await delete_command_and_response(message, bot_msg, delay=10)
            return

    success, msg = await admin_service.remove_admin(chat_id, target_user_id, removed_by)
    bot_msg = await message.answer(msg)
    await delete_command_and_response(message, bot_msg)


# --- Callback handlers ---


@super_admin_router.callback_query(
    SuperAdminCallback.filter(F.action == "promote"), IsSuperAdminFilter()
)
async def cb_sa_promote(callback: CallbackQuery, callback_data: SuperAdminCallback):
    chat_id = callback.message.chat.id
    target_user_id = callback_data.target
    success, msg = await admin_service.promote_admin(
        chat_id, target_user_id, callback.from_user.id
    )
    await callback.answer(msg, show_alert=not success)

    if success:
        admins = await admin_service.list_admins(chat_id)
        kb = admin_management_keyboard(admins, chat_id)
        try:
            await callback.message.edit_text(
                _admin_list_text(admins),
                reply_markup=kb,
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


@super_admin_router.callback_query(
    SuperAdminCallback.filter(F.action == "demote"), IsSuperAdminFilter()
)
async def cb_sa_demote(callback: CallbackQuery, callback_data: SuperAdminCallback):
    chat_id = callback.message.chat.id
    target_user_id = callback_data.target
    success, msg = await admin_service.demote_admin(
        chat_id, target_user_id, callback.from_user.id
    )
    await callback.answer(msg, show_alert=not success)

    if success:
        admins = await admin_service.list_admins(chat_id)
        kb = admin_management_keyboard(admins, chat_id)
        try:
            await callback.message.edit_text(
                _admin_list_text(admins),
                reply_markup=kb,
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


@super_admin_router.callback_query(
    SuperAdminCallback.filter(F.action == "remove"), IsSuperAdminFilter()
)
async def cb_sa_remove(callback: CallbackQuery, callback_data: SuperAdminCallback):
    chat_id = callback.message.chat.id
    target_user_id = callback_data.target
    success, msg = await admin_service.remove_admin(
        chat_id, target_user_id, callback.from_user.id
    )
    await callback.answer(msg, show_alert=not success)

    if success:
        admins = await admin_service.list_admins(chat_id)
        if not admins:
            try:
                await callback.message.edit_text(
                    "Нет администраторов.",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
        else:
            kb = admin_management_keyboard(admins, chat_id)
            try:
                await callback.message.edit_text(
                    _admin_list_text(admins),
                    reply_markup=kb,
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass


@super_admin_router.callback_query(
    SuperAdminCallback.filter(F.action == "close"), IsSuperAdminFilter()
)
async def cb_sa_close(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


@super_admin_router.callback_query(
    SuperAdminCallback.filter(F.action == "info"), IsSuperAdminFilter()
)
async def cb_sa_info(callback: CallbackQuery, callback_data: SuperAdminCallback):
    chat_id = callback.message.chat.id
    target_user_id = callback_data.target
    admin = await admin_service.get_admin(chat_id, target_user_id)
    if not admin:
        await callback.answer("Администратор не найден.", show_alert=True)
        return
    role_label = "Супер-админ" if admin.role == AdminRole.SUPER_ADMIN else "Админ"
    await callback.answer(
        f"{admin.display_name}\n"
        f"ID: {admin.user_id}\n"
        f"Роль: {role_label}\n"
        f"Добавлен: {admin.created_at.strftime('%Y-%m-%d %H:%M')}",
        show_alert=True,
    )
