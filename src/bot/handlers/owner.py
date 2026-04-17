"""Owner-only DM admin panel for managing users across all chats."""

import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select, func, distinct

from bot.config import config
from bot.db import UserModel, session

logger = logging.getLogger(__name__)

owner_router = Router(name="owner")

USERS_PER_PAGE = 10


class OwnerCallback(CallbackData, prefix="own"):
    action: str  # list_chats, list_users, user_info, edit_penis, edit_toxic, reset_user, back, close, page
    chat_id: int = 0
    user_id: int = 0
    page: int = 0
    value: int = 0


def _is_owner(user_id: int) -> bool:
    return user_id == config.ADMIN_IDS[0]


# --- Keyboards ---


def _chats_keyboard(chats: list[dict], page: int = 0) -> InlineKeyboardMarkup:
    per_page = 10
    total_pages = max(1, (len(chats) + per_page - 1) // per_page)
    page = min(page, total_pages - 1)
    start = page * per_page
    page_chats = chats[start : start + per_page]

    rows: list[list[InlineKeyboardButton]] = []
    for chat in page_chats:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"Chat {chat['chat_id']} ({chat['count']} users)",
                    callback_data=OwnerCallback(
                        action="list_users", chat_id=chat["chat_id"], page=0
                    ).pack(),
                ),
            ]
        )

    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=OwnerCallback(action="list_chats", page=page - 1).pack(),
                )
            )
        nav.append(
            InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data=OwnerCallback(action="noop").pack(),
            )
        )
        if page < total_pages - 1:
            nav.append(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=OwnerCallback(action="list_chats", page=page + 1).pack(),
                )
            )
        rows.append(nav)

    rows.append(
        [
            InlineKeyboardButton(
                text="✖ Закрыть",
                callback_data=OwnerCallback(action="close").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _users_keyboard(
    users: list, chat_id: int, page: int = 0
) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(users) + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    page = min(page, total_pages - 1)
    start = page * USERS_PER_PAGE
    page_users = users[start : start + USERS_PER_PAGE]

    rows: list[list[InlineKeyboardButton]] = []
    for user in page_users:
        name = user.first_name or user.username or str(user.user_id)
        if len(name) > 20:
            name = name[:20] + "…"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{name} — {user.penis_size} см | tox:{user.toxicity_level}",
                    callback_data=OwnerCallback(
                        action="user_info",
                        chat_id=chat_id,
                        user_id=user.user_id,
                        page=page,
                    ).pack(),
                ),
            ]
        )

    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=OwnerCallback(
                        action="list_users", chat_id=chat_id, page=page - 1
                    ).pack(),
                )
            )
        nav.append(
            InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data=OwnerCallback(action="noop").pack(),
            )
        )
        if page < total_pages - 1:
            nav.append(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=OwnerCallback(
                        action="list_users", chat_id=chat_id, page=page + 1
                    ).pack(),
                )
            )
        rows.append(nav)

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад к чатам",
                callback_data=OwnerCallback(action="list_chats", page=0).pack(),
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="✖ Закрыть",
                callback_data=OwnerCallback(action="close").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _user_info_keyboard(
    chat_id: int, user_id: int, page: int = 0
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    # Penis size adjustment
    rows.append(
        [
            InlineKeyboardButton(
                text="📏 -10 см",
                callback_data=OwnerCallback(
                    action="edit_penis", chat_id=chat_id, user_id=user_id, value=-10
                ).pack(),
            ),
            InlineKeyboardButton(
                text="📏 -1 см",
                callback_data=OwnerCallback(
                    action="edit_penis", chat_id=chat_id, user_id=user_id, value=-1
                ).pack(),
            ),
            InlineKeyboardButton(
                text="📏 +1 см",
                callback_data=OwnerCallback(
                    action="edit_penis", chat_id=chat_id, user_id=user_id, value=1
                ).pack(),
            ),
            InlineKeyboardButton(
                text="📏 +10 см",
                callback_data=OwnerCallback(
                    action="edit_penis", chat_id=chat_id, user_id=user_id, value=10
                ).pack(),
            ),
        ]
    )

    # Toxicity adjustment
    rows.append(
        [
            InlineKeyboardButton(
                text="☣️ -10",
                callback_data=OwnerCallback(
                    action="edit_toxic", chat_id=chat_id, user_id=user_id, value=-10
                ).pack(),
            ),
            InlineKeyboardButton(
                text="☣️ -1",
                callback_data=OwnerCallback(
                    action="edit_toxic", chat_id=chat_id, user_id=user_id, value=-1
                ).pack(),
            ),
            InlineKeyboardButton(
                text="☣️ +1",
                callback_data=OwnerCallback(
                    action="edit_toxic", chat_id=chat_id, user_id=user_id, value=1
                ).pack(),
            ),
            InlineKeyboardButton(
                text="☣️ +10",
                callback_data=OwnerCallback(
                    action="edit_toxic", chat_id=chat_id, user_id=user_id, value=10
                ).pack(),
            ),
        ]
    )

    # Toggle lucky
    rows.append(
        [
            InlineKeyboardButton(
                text="🍀 Toggle Lucky",
                callback_data=OwnerCallback(
                    action="toggle_lucky", chat_id=chat_id, user_id=user_id
                ).pack(),
            ),
        ]
    )

    # Reset
    rows.append(
        [
            InlineKeyboardButton(
                text="🔄 Сбросить всё",
                callback_data=OwnerCallback(
                    action="reset_user", chat_id=chat_id, user_id=user_id, page=page
                ).pack(),
            ),
        ]
    )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад к пользователям",
                callback_data=OwnerCallback(
                    action="list_users", chat_id=chat_id, page=page
                ).pack(),
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="✖ Закрыть",
                callback_data=OwnerCallback(action="close").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --- Helpers ---


async def _get_chats_with_users() -> list[dict]:
    async with session() as s:
        result = (
            await s.execute(
                select(
                    UserModel.chat_id,
                    func.count(UserModel.id).label("count"),
                )
                .group_by(UserModel.chat_id)
                .order_by(func.count(UserModel.id).desc())
            )
        ).all()
        return [{"chat_id": row[0], "count": row[1]} for row in result]


async def _get_users_in_chat(chat_id: int) -> list:
    async with session() as s:
        result = (
            await s.scalars(
                select(UserModel)
                .where(UserModel.chat_id == chat_id)
                .order_by(UserModel.penis_size.desc())
            )
        ).all()
        return list(result)


async def _get_user(chat_id: int, user_id: int) -> UserModel | None:
    async with session() as s:
        return await s.scalar(
            select(UserModel).where(
                UserModel.chat_id == chat_id, UserModel.user_id == user_id
            )
        )


async def _update_user_field(chat_id: int, user_id: int, field: str, delta: int) -> UserModel | None:
    async with session() as s:
        user = await s.scalar(
            select(UserModel).where(
                UserModel.chat_id == chat_id, UserModel.user_id == user_id
            )
        )
        if not user:
            return None
        current = getattr(user, field)
        new_val = max(0, current + delta)
        setattr(user, field, new_val)
        return user


async def _toggle_lucky(chat_id: int, user_id: int) -> UserModel | None:
    async with session() as s:
        user = await s.scalar(
            select(UserModel).where(
                UserModel.chat_id == chat_id, UserModel.user_id == user_id
            )
        )
        if not user:
            return None
        user.casino_lucky = not user.casino_lucky
        return user


async def _reset_user(chat_id: int, user_id: int) -> bool:
    async with session() as s:
        user = await s.scalar(
            select(UserModel).where(
                UserModel.chat_id == chat_id, UserModel.user_id == user_id
            )
        )
        if not user:
            return False
        user.penis_size = 0
        user.toxicity_level = 0
        user.casino_lucky = False
        return True


def _user_info_text(user: UserModel) -> str:
    lucky = "✅ Да" if user.casino_lucky else "❌ Нет"
    return (
        f"👤 <b>Пользователь</b>\n\n"
        f"ID: <code>{user.user_id}</code>\n"
        f"Имя: {user.first_name or '—'}\n"
        f"Username: @{user.username or '—'}\n"
        f"Chat ID: <code>{user.chat_id}</code>\n\n"
        f"📏 Размер: <b>{user.penis_size}</b> см\n"
        f"☣️ Токсичность: <b>{user.toxicity_level}</b>\n"
        f"🍀 Lucky: {lucky}\n"
        f"🎰 Последнее обновление: {user.last_penis_update.strftime('%Y-%m-%d %H:%M') if user.last_penis_update else '—'}"
    )


# --- Handlers ---


@owner_router.message(Command("owner"), F.chat.type == "private")
async def cmd_owner(message: Message):
    if not _is_owner(message.from_user.id):
        return

    chats = await _get_chats_with_users()
    if not chats:
        await message.answer("Нет данных о чатах.")
        return

    kb = _chats_keyboard(chats)
    await message.answer(
        "👑 <b>Панель владельца</b>\n\nВыберите чат:",
        reply_markup=kb,
        parse_mode=ParseMode.HTML,
    )


@owner_router.callback_query(OwnerCallback.filter(F.action == "list_chats"))
async def cb_list_chats(callback: CallbackQuery, callback_data: OwnerCallback):
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    chats = await _get_chats_with_users()
    kb = _chats_keyboard(chats, callback_data.page)
    try:
        await callback.message.edit_text(
            "👑 <b>Панель владельца</b>\n\nВыберите чат:",
            reply_markup=kb,
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass
    await callback.answer()


@owner_router.callback_query(OwnerCallback.filter(F.action == "list_users"))
async def cb_list_users(callback: CallbackQuery, callback_data: OwnerCallback):
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    chat_id = callback_data.chat_id
    page = callback_data.page
    users = await _get_users_in_chat(chat_id)

    if not users:
        await callback.answer("В этом чате нет пользователей.", show_alert=True)
        return

    kb = _users_keyboard(users, chat_id, page)
    try:
        await callback.message.edit_text(
            f"👥 <b>Пользователи чата</b> <code>{chat_id}</code>\n\n"
            f"Всего: {len(users)}",
            reply_markup=kb,
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass
    await callback.answer()


@owner_router.callback_query(OwnerCallback.filter(F.action == "user_info"))
async def cb_user_info(callback: CallbackQuery, callback_data: OwnerCallback):
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    user = await _get_user(callback_data.chat_id, callback_data.user_id)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    text = _user_info_text(user)
    kb = _user_info_keyboard(callback_data.chat_id, callback_data.user_id, callback_data.page)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        pass
    await callback.answer()


@owner_router.callback_query(OwnerCallback.filter(F.action == "edit_penis"))
async def cb_edit_penis(callback: CallbackQuery, callback_data: OwnerCallback):
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    user = await _update_user_field(
        callback_data.chat_id, callback_data.user_id, "penis_size", callback_data.value
    )
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    # Refresh the panel
    user = await _get_user(callback_data.chat_id, callback_data.user_id)
    text = _user_info_text(user)
    kb = _user_info_keyboard(callback_data.chat_id, callback_data.user_id, callback_data.page)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        pass
    await callback.answer(f"Размер: {user.penis_size} см")


@owner_router.callback_query(OwnerCallback.filter(F.action == "edit_toxic"))
async def cb_edit_toxic(callback: CallbackQuery, callback_data: OwnerCallback):
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    user = await _update_user_field(
        callback_data.chat_id, callback_data.user_id, "toxicity_level", callback_data.value
    )
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    user = await _get_user(callback_data.chat_id, callback_data.user_id)
    text = _user_info_text(user)
    kb = _user_info_keyboard(callback_data.chat_id, callback_data.user_id, callback_data.page)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        pass
    await callback.answer(f"Токсичность: {user.toxicity_level}")


@owner_router.callback_query(OwnerCallback.filter(F.action == "toggle_lucky"))
async def cb_toggle_lucky(callback: CallbackQuery, callback_data: OwnerCallback):
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    user = await _toggle_lucky(callback_data.chat_id, callback_data.user_id)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    user = await _get_user(callback_data.chat_id, callback_data.user_id)
    text = _user_info_text(user)
    kb = _user_info_keyboard(callback_data.chat_id, callback_data.user_id, callback_data.page)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        pass
    lucky_text = "включен" if user.casino_lucky else "выключен"
    await callback.answer(f"Lucky: {lucky_text}")


@owner_router.callback_query(OwnerCallback.filter(F.action == "reset_user"))
async def cb_reset_user(callback: CallbackQuery, callback_data: OwnerCallback):
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    success = await _reset_user(callback_data.chat_id, callback_data.user_id)
    if not success:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    user = await _get_user(callback_data.chat_id, callback_data.user_id)
    text = _user_info_text(user)
    kb = _user_info_keyboard(callback_data.chat_id, callback_data.user_id, callback_data.page)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        pass
    await callback.answer("Пользователь сброшен!")


@owner_router.callback_query(OwnerCallback.filter(F.action == "close"))
async def cb_owner_close(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


@owner_router.callback_query(OwnerCallback.filter(F.action == "noop"))
async def cb_owner_noop(callback: CallbackQuery):
    await callback.answer()
