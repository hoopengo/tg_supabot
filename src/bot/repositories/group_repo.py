from typing import Sequence

from sqlalchemy import delete, select, update

from bot.db import session
from bot.db.models import QueueGroupMemberModel, QueueGroupModel


async def create_group(
    chat_id: int,
    created_by: int,
    title: str | None = None,
) -> QueueGroupModel:
    async with session() as s:
        group = QueueGroupModel(
            chat_id=chat_id,
            created_by=created_by,
            title=title,
        )
        s.add(group)
        await s.flush()
        await s.refresh(group)
        return group


async def add_queue_to_group(
    group_id: int,
    queue_id: int,
    position: int,
) -> QueueGroupMemberModel:
    async with session() as s:
        member = QueueGroupMemberModel(
            group_id=group_id,
            queue_id=queue_id,
            position=position,
        )
        s.add(member)
        await s.flush()
        await s.refresh(member)
        return member


async def get_group(group_id: int) -> QueueGroupModel | None:
    async with session() as s:
        return await s.scalar(
            select(QueueGroupModel).where(QueueGroupModel.id == group_id)
        )


async def get_groups_by_chat(chat_id: int) -> Sequence[QueueGroupModel]:
    async with session() as s:
        result = await s.scalars(
            select(QueueGroupModel)
            .where(QueueGroupModel.chat_id == chat_id)
            .order_by(QueueGroupModel.created_at.desc())
        )
        return result.all()


async def get_groups_by_queue(queue_id: int) -> Sequence[QueueGroupModel]:
    """Get all groups that contain a given queue."""
    async with session() as s:
        result = await s.scalars(
            select(QueueGroupModel)
            .join(
                QueueGroupMemberModel,
                QueueGroupMemberModel.group_id == QueueGroupModel.id,
            )
            .where(QueueGroupMemberModel.queue_id == queue_id)
        )
        return result.all()


async def get_group_queue_ids(group_id: int) -> Sequence[int]:
    """Get ordered queue IDs for a group."""
    async with session() as s:
        result = await s.scalars(
            select(QueueGroupMemberModel.queue_id)
            .where(QueueGroupMemberModel.group_id == group_id)
            .order_by(QueueGroupMemberModel.position.asc())
        )
        return result.all()


async def get_group_member_count(group_id: int) -> int:
    """Get number of queues in a group."""
    async with session() as s:
        from sqlalchemy import func
        result = await s.scalar(
            select(func.count(QueueGroupMemberModel.id))
            .where(QueueGroupMemberModel.group_id == group_id)
        )
        return result or 0


async def remove_queue_from_group(group_id: int, queue_id: int) -> bool:
    async with session() as s:
        result = await s.execute(
            delete(QueueGroupMemberModel).where(
                QueueGroupMemberModel.group_id == group_id,
                QueueGroupMemberModel.queue_id == queue_id,
            )
        )
        return result.rowcount > 0


async def update_group_message_id(group_id: int, message_id: int) -> None:
    async with session() as s:
        await s.execute(
            update(QueueGroupModel)
            .where(QueueGroupModel.id == group_id)
            .values(message_id=message_id)
        )


async def update_group_title(group_id: int, title: str) -> None:
    async with session() as s:
        await s.execute(
            update(QueueGroupModel)
            .where(QueueGroupModel.id == group_id)
            .values(title=title)
        )


async def delete_group(group_id: int) -> bool:
    async with session() as s:
        result = await s.execute(
            delete(QueueGroupModel).where(QueueGroupModel.id == group_id)
        )
        return result.rowcount > 0
