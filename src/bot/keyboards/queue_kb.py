from typing import Sequence

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.db.models import AdminRole, ChatAdminModel, QueueMemberModel, QueueStatus

# --- Callback data factories ---


class QueueCallback(CallbackData, prefix="q"):
    """Queue user action callbacks."""

    action: str  # join, leave, swap_list, swap_request, swap_confirm, swap_reject, close, back_to_queue
    queue_id: int
    target: int = 0
    owner: int = 0


class QueueListCallback(CallbackData, prefix="ql"):
    """Queue list for /queues command."""

    action: str  # view, close
    queue_id: int = 0


class AdminCallback(CallbackData, prefix="adm"):
    """Queue admin action callbacks."""

    action: str  # open, close, clear, delete, close_panel, refresh, move_up, move_down, remove_member
    queue_id: int
    target: int = 0
    page: int = 0


class SuperAdminCallback(CallbackData, prefix="sa"):
    """Super admin action callbacks."""

    action: str
    target: int = 0


class AdminListCallback(CallbackData, prefix="al"):
    """Admin panel queue list callbacks."""

    action: str  # select, back, close
    queue_id: int = 0
    page: int = 0


# --- Keyboard builders ---


def queue_user_keyboard(
    queue_id: int,
    is_open: bool,
    members: Sequence[QueueMemberModel] | None = None,
    owner: int = 0,
) -> InlineKeyboardMarkup:
    """Build the user-facing keyboard for a queue."""
    rows: list[list[InlineKeyboardButton]] = []

    rows.append(
        [
            InlineKeyboardButton(
                text="📥 Встать в конец",
                callback_data=QueueCallback(
                    action="join", queue_id=queue_id, owner=owner
                ).pack(),
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="🚪 Выйти",
                callback_data=QueueCallback(
                    action="leave", queue_id=queue_id, owner=owner
                ).pack(),
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def queue_list_keyboard(queues) -> InlineKeyboardMarkup:
    """Build keyboard listing all queues for /queues command."""
    rows: list[list[InlineKeyboardButton]] = []

    for q in queues:
        status_emoji = "🟢" if q.status == QueueStatus.OPEN else "🔴"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{status_emoji} {q.title}",
                    callback_data=QueueListCallback(
                        action="view", queue_id=q.id
                    ).pack(),
                ),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="✖ Закрыть",
                callback_data=QueueListCallback(action="close").pack(),
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


MEMBERS_PER_PAGE = 5


def queue_admin_keyboard(
    queue_id: int,
    is_open: bool,
    members: Sequence[QueueMemberModel] | None = None,
    page: int = 0,
) -> InlineKeyboardMarkup:
    """Build the admin management keyboard for a queue."""
    rows: list[list[InlineKeyboardButton]] = []

    if is_open:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔴 Закрыть",
                    callback_data=AdminCallback(
                        action="close", queue_id=queue_id, page=page
                    ).pack(),
                ),
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🟢 Открыть",
                    callback_data=AdminCallback(
                        action="open", queue_id=queue_id, page=page
                    ).pack(),
                ),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="🗑 Очистить",
                callback_data=AdminCallback(
                    action="clear", queue_id=queue_id, page=page
                ).pack(),
            ),
            InlineKeyboardButton(
                text="❌ Удалить",
                callback_data=AdminCallback(
                    action="delete", queue_id=queue_id, page=page
                ).pack(),
            ),
        ]
    )

    if members:
        total_pages = max(1, (len(members) + MEMBERS_PER_PAGE - 1) // MEMBERS_PER_PAGE)
        page = min(page, total_pages - 1)
        start = page * MEMBERS_PER_PAGE
        page_members = members[start : start + MEMBERS_PER_PAGE]

        for m in page_members:
            name = m.first_name or m.username or str(m.user_id)
            if len(name) > 12:
                name = name[:12] + "…"
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"{m.position}. {name}",
                        callback_data=AdminCallback(
                            action="noop", queue_id=queue_id, page=page
                        ).pack(),
                    ),
                    InlineKeyboardButton(
                        text="✖",
                        callback_data=AdminCallback(
                            action="remove_member",
                            queue_id=queue_id,
                            target=m.user_id,
                            page=page,
                        ).pack(),
                    ),
                ]
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        text="⬆️",
                        callback_data=AdminCallback(
                            action="move_up",
                            queue_id=queue_id,
                            target=m.user_id,
                            page=page,
                        ).pack(),
                    ),
                    InlineKeyboardButton(
                        text="⬇️",
                        callback_data=AdminCallback(
                            action="move_down",
                            queue_id=queue_id,
                            target=m.user_id,
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
                        callback_data=AdminCallback(
                            action="members_page", queue_id=queue_id, page=page - 1
                        ).pack(),
                    )
                )
            nav.append(
                InlineKeyboardButton(
                    text=f"{page + 1}/{total_pages}",
                    callback_data=AdminCallback(
                        action="noop", queue_id=queue_id, page=page
                    ).pack(),
                )
            )
            if page < total_pages - 1:
                nav.append(
                    InlineKeyboardButton(
                        text="➡️",
                        callback_data=AdminCallback(
                            action="members_page", queue_id=queue_id, page=page + 1
                        ).pack(),
                    )
                )
            rows.append(nav)

    rows.append(
        [
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data=AdminCallback(
                    action="refresh", queue_id=queue_id, page=page
                ).pack(),
            ),
            InlineKeyboardButton(
                text="✖ Закрыть",
                callback_data=AdminCallback(
                    action="close_panel", queue_id=queue_id, page=page
                ).pack(),
            ),
        ]
    )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=AdminListCallback(action="back").pack(),
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_queue_list_keyboard(
    chat_queues: Sequence,
    page: int = 0,
    per_page: int = 5,
) -> InlineKeyboardMarkup:
    """Build keyboard showing queues in a chat with pagination."""
    rows: list[list[InlineKeyboardButton]] = []

    start = page * per_page
    page_queues = chat_queues[start : start + per_page]

    for queue in page_queues:
        status_emoji = "🟢" if queue.status == QueueStatus.OPEN else "🔴"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{status_emoji} {queue.title}",
                    callback_data=AdminListCallback(
                        action="select", queue_id=queue.id, page=page
                    ).pack(),
                ),
            ]
        )

    total_pages = max(1, (len(chat_queues) + per_page - 1) // per_page)
    nav_row: list[InlineKeyboardButton] = []

    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=AdminListCallback(action="back", page=page - 1).pack(),
            )
        )

    if total_pages > 1:
        nav_row.append(
            InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data=AdminListCallback(action="noop").pack(),
            )
        )

    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=AdminListCallback(action="back", page=page + 1).pack(),
            )
        )

    if nav_row:
        rows.append(nav_row)

    rows.append(
        [
            InlineKeyboardButton(
                text="✖ Закрыть",
                callback_data=AdminListCallback(action="close").pack(),
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def swap_list_keyboard(
    queue_id: int,
    members: Sequence[QueueMemberModel],
    current_user_id: int,
    owner: int = 0,
) -> InlineKeyboardMarkup:
    """Build keyboard listing users to swap with."""
    rows: list[list[InlineKeyboardButton]] = []

    for member in members:
        if member.user_id == current_user_id:
            continue
        name = member.first_name or member.username or str(member.position)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🔄 Поменяться с {name}",
                    callback_data=QueueCallback(
                        action="swap_request",
                        queue_id=queue_id,
                        target=member.user_id,
                        owner=owner,
                    ).pack(),
                ),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=QueueCallback(
                    action="back_to_queue", queue_id=queue_id, owner=owner
                ).pack(),
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def swap_confirmation_keyboard(
    swap_id: int,
    queue_id: int,
) -> InlineKeyboardMarkup:
    """Build keyboard for swap confirmation."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принять",
                    callback_data=QueueCallback(
                        action="swap_confirm", queue_id=queue_id, target=swap_id
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=QueueCallback(
                        action="swap_reject", queue_id=queue_id, target=swap_id
                    ).pack(),
                ),
            ],
        ]
    )


def admin_management_keyboard(
    admins: Sequence[ChatAdminModel],
    chat_id: int,
) -> InlineKeyboardMarkup:
    """Build keyboard for managing individual admins."""
    rows: list[list[InlineKeyboardButton]] = []

    for admin in admins:
        role_emoji = "⭐" if admin.role == AdminRole.SUPER_ADMIN else "👤"
        name = admin.display_name
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{role_emoji} {name}",
                    callback_data=SuperAdminCallback(
                        action="info", target=admin.user_id
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="⬆️",
                    callback_data=SuperAdminCallback(
                        action="promote", target=admin.user_id
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="⬇️",
                    callback_data=SuperAdminCallback(
                        action="demote", target=admin.user_id
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="❌",
                    callback_data=SuperAdminCallback(
                        action="remove", target=admin.user_id
                    ).pack(),
                ),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="✖ Закрыть",
                callback_data=SuperAdminCallback(action="close").pack(),
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)
