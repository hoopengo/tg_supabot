import logging
from typing import Sequence

from bot.config import config
from bot.db.models import AdminRole, ChatAdminModel
from bot.repositories import admin_repo, log_repo

logger = logging.getLogger(__name__)


def is_bot_creator(user_id: int) -> bool:
    """Check if user is the bot creator (first ADMIN_IDS entry)."""
    return user_id == config.ADMIN_IDS[0]


async def is_super_admin(chat_id: int, user_id: int) -> bool:
    """Check if user is a super admin."""
    if is_bot_creator(user_id):
        return True
    admin = await admin_repo.get_admin(chat_id, user_id)
    return admin is not None and admin.role == AdminRole.SUPER_ADMIN


async def is_admin(chat_id: int, user_id: int) -> bool:
    """Check if user is an admin or super admin."""
    if is_bot_creator(user_id):
        return True
    admin = await admin_repo.get_admin(chat_id, user_id)
    return admin is not None


async def add_admin(
    chat_id: int,
    user_id: int,
    added_by: int,
    role: AdminRole = AdminRole.ADMIN,
    first_name: str | None = None,
    username: str | None = None,
) -> tuple[bool, str]:
    """Add a user as admin. Only super admins can do this."""
    if not await is_super_admin(chat_id, added_by):
        return False, "Недостаточно прав."

    existing = await admin_repo.get_admin(chat_id, user_id)
    if existing:
        return False, "Пользователь уже является администратором."

    await admin_repo.add_admin(chat_id, user_id, role, added_by, first_name, username)
    await log_repo.log_action(
        chat_id=chat_id,
        actor_user_id=added_by,
        action="admin_added",
        payload={"user_id": user_id, "role": role.value},
    )

    role_name = "супер-админ" if role == AdminRole.SUPER_ADMIN else "админ"
    return True, f"Пользователь назначен {role_name}."


async def remove_admin(
    chat_id: int,
    user_id: int,
    removed_by: int,
) -> tuple[bool, str]:
    """Remove an admin. Only super admins can do this."""
    if not await is_super_admin(chat_id, removed_by):
        return False, "Недостаточно прав."

    target = await admin_repo.get_admin(chat_id, user_id)
    if not target:
        return False, "Пользователь не является администратором."

    success = await admin_repo.remove_admin(chat_id, user_id)
    if success:
        await log_repo.log_action(
            chat_id=chat_id,
            actor_user_id=removed_by,
            action="admin_removed",
            payload={"user_id": user_id},
        )
        return True, "Администратор удалён."
    return False, "Не удалось удалить администратора."


async def promote_admin(
    chat_id: int,
    user_id: int,
    promoted_by: int,
) -> tuple[bool, str]:
    """Promote admin to super admin."""
    if not await is_super_admin(chat_id, promoted_by):
        return False, "Недостаточно прав."

    target = await admin_repo.get_admin(chat_id, user_id)
    if not target:
        return False, "Пользователь не является администратором."
    if target.role == AdminRole.SUPER_ADMIN:
        return False, "Пользователь уже супер-админ."

    success = await admin_repo.update_admin_role(
        chat_id, user_id, AdminRole.SUPER_ADMIN
    )
    if success:
        await log_repo.log_action(
            chat_id=chat_id,
            actor_user_id=promoted_by,
            action="admin_promoted",
            payload={"user_id": user_id},
        )
        return True, "Пользователь повышен до супер-админа."
    return False, "Не удалось повысить."


async def demote_admin(
    chat_id: int,
    user_id: int,
    demoted_by: int,
) -> tuple[bool, str]:
    """Demote super admin to regular admin."""
    if not await is_super_admin(chat_id, demoted_by):
        return False, "Недостаточно прав."

    target = await admin_repo.get_admin(chat_id, user_id)
    if not target:
        return False, "Пользователь не является администратором."
    if target.role == AdminRole.ADMIN:
        return False, "Пользователь уже обычный админ."

    success = await admin_repo.update_admin_role(chat_id, user_id, AdminRole.ADMIN)
    if success:
        await log_repo.log_action(
            chat_id=chat_id,
            actor_user_id=demoted_by,
            action="admin_demoted",
            payload={"user_id": user_id},
        )
        return True, "Пользователь понижен до админа."
    return False, "Не удалось понизить."


async def list_admins(chat_id: int) -> Sequence[ChatAdminModel]:
    return await admin_repo.get_admins(chat_id)


async def get_admin(chat_id: int, user_id: int) -> ChatAdminModel | None:
    return await admin_repo.get_admin(chat_id, user_id)
