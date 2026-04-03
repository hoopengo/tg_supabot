from typing import Sequence

from sqlalchemy import select, update

from bot.db import session
from bot.db.models import ChatAdminModel, AdminRole


async def get_admin(chat_id: int, user_id: int) -> ChatAdminModel | None:
    async with session() as s:
        result = await s.scalar(
            select(ChatAdminModel).where(
                ChatAdminModel.chat_id == chat_id,
                ChatAdminModel.user_id == user_id,
                ChatAdminModel.is_active == True,  # noqa
            )
        )
        return result


async def get_admins(chat_id: int) -> Sequence[ChatAdminModel]:
    async with session() as s:
        result = await s.scalars(
            select(ChatAdminModel)
            .where(
                ChatAdminModel.chat_id == chat_id,
                ChatAdminModel.is_active == True,  # noqa
            )
            .order_by(ChatAdminModel.role.asc(), ChatAdminModel.created_at.asc())
        )
        return result.all()


async def add_admin(
    chat_id: int,
    user_id: int,
    role: AdminRole,
    added_by: int,
    first_name: str | None = None,
    username: str | None = None,
) -> ChatAdminModel:
    async with session() as s:
        # Check if already exists (inactive -> reactivate)
        existing = await s.scalar(
            select(ChatAdminModel).where(
                ChatAdminModel.chat_id == chat_id,
                ChatAdminModel.user_id == user_id,
            )
        )
        if existing:
            existing.is_active = True
            existing.role = role
            existing.added_by = added_by
            existing.first_name = first_name
            existing.username = username
            await s.flush()
            await s.refresh(existing)
            return existing

        admin = ChatAdminModel(
            chat_id=chat_id,
            user_id=user_id,
            role=role,
            added_by=added_by,
            first_name=first_name,
            username=username,
        )
        s.add(admin)
        await s.flush()
        await s.refresh(admin)
        return admin


async def remove_admin(chat_id: int, user_id: int) -> bool:
    async with session() as s:
        result = await s.execute(
            update(ChatAdminModel)
            .where(
                ChatAdminModel.chat_id == chat_id,
                ChatAdminModel.user_id == user_id,
                ChatAdminModel.is_active == True,  # noqa
            )
            .values(is_active=False)
        )
        return result.rowcount > 0


async def update_admin_role(
    chat_id: int,
    user_id: int,
    role: AdminRole,
) -> bool:
    async with session() as s:
        result = await s.execute(
            update(ChatAdminModel)
            .where(
                ChatAdminModel.chat_id == chat_id,
                ChatAdminModel.user_id == user_id,
                ChatAdminModel.is_active == True,  # noqa
            )
            .values(role=role)
        )
        return result.rowcount > 0
