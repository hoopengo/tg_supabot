from typing import Sequence

from sqlalchemy import select, func, update

from bot.db import session
from bot.db.models import QueueMemberModel, MemberStatus


async def add_member(
    queue_id: int,
    user_id: int,
    username: str | None,
    position: int,
    first_name: str | None = None,
) -> QueueMemberModel:
    async with session() as s:
        member = QueueMemberModel(
            queue_id=queue_id,
            user_id=user_id,
            username=username,
            first_name=first_name,
            position=position,
        )
        s.add(member)
        await s.flush()
        await s.refresh(member)
        return member


async def get_active_members(queue_id: int) -> Sequence[QueueMemberModel]:
    async with session() as s:
        result = await s.scalars(
            select(QueueMemberModel)
            .where(
                QueueMemberModel.queue_id == queue_id,
                QueueMemberModel.status == MemberStatus.ACTIVE,
            )
            .order_by(QueueMemberModel.position.asc())
        )
        return result.all()


async def get_member_by_user(queue_id: int, user_id: int) -> QueueMemberModel | None:
    async with session() as s:
        result = await s.scalar(
            select(QueueMemberModel).where(
                QueueMemberModel.queue_id == queue_id,
                QueueMemberModel.user_id == user_id,
                QueueMemberModel.status == MemberStatus.ACTIVE,
            )
        )
        return result


async def get_member_count(queue_id: int) -> int:
    async with session() as s:
        result = await s.scalar(
            select(func.count(QueueMemberModel.id)).where(
                QueueMemberModel.queue_id == queue_id,
                QueueMemberModel.status == MemberStatus.ACTIVE,
            )
        )
        return result or 0


async def get_max_position(queue_id: int) -> int:
    async with session() as s:
        result = await s.scalar(
            select(func.coalesce(func.max(QueueMemberModel.position), 0)).where(
                QueueMemberModel.queue_id == queue_id,
                QueueMemberModel.status == MemberStatus.ACTIVE,
            )
        )
        return result or 0


async def remove_member(queue_id: int, user_id: int) -> bool:
    async with session() as s:
        result = await s.execute(
            update(QueueMemberModel)
            .where(
                QueueMemberModel.queue_id == queue_id,
                QueueMemberModel.user_id == user_id,
                QueueMemberModel.status == MemberStatus.ACTIVE,
            )
            .values(status=MemberStatus.REMOVED)
        )
        return result.rowcount > 0


async def clear_members(queue_id: int) -> int:
    async with session() as s:
        result = await s.execute(
            update(QueueMemberModel)
            .where(
                QueueMemberModel.queue_id == queue_id,
                QueueMemberModel.status == MemberStatus.ACTIVE,
            )
            .values(status=MemberStatus.REMOVED)
        )
        return result.rowcount


async def swap_positions(queue_id: int, user_a_id: int, user_b_id: int) -> bool:
    """Atomically swap positions of two users in a queue."""
    async with session() as s:
        member_a = await s.scalar(
            select(QueueMemberModel)
            .where(
                QueueMemberModel.queue_id == queue_id,
                QueueMemberModel.user_id == user_a_id,
                QueueMemberModel.status == MemberStatus.ACTIVE,
            )
            .with_for_update()
        )
        member_b = await s.scalar(
            select(QueueMemberModel)
            .where(
                QueueMemberModel.queue_id == queue_id,
                QueueMemberModel.user_id == user_b_id,
                QueueMemberModel.status == MemberStatus.ACTIVE,
            )
            .with_for_update()
        )
        if not member_a or not member_b:
            return False
        member_a.position, member_b.position = member_b.position, member_a.position
        return True


async def set_position(queue_id: int, user_id: int, new_position: int) -> bool:
    """Move a user to a specific position, shifting others as needed."""
    async with session() as s:
        member = await s.scalar(
            select(QueueMemberModel).where(
                QueueMemberModel.queue_id == queue_id,
                QueueMemberModel.user_id == user_id,
                QueueMemberModel.status == MemberStatus.ACTIVE,
            )
        )
        if not member:
            return False

        old_position = member.position
        if old_position == new_position:
            return True

        if new_position < old_position:
            await s.execute(
                update(QueueMemberModel)
                .where(
                    QueueMemberModel.queue_id == queue_id,
                    QueueMemberModel.status == MemberStatus.ACTIVE,
                    QueueMemberModel.position >= new_position,
                    QueueMemberModel.position < old_position,
                    QueueMemberModel.user_id != user_id,
                )
                .values(position=QueueMemberModel.position + 1)
            )
        else:
            await s.execute(
                update(QueueMemberModel)
                .where(
                    QueueMemberModel.queue_id == queue_id,
                    QueueMemberModel.status == MemberStatus.ACTIVE,
                    QueueMemberModel.position > old_position,
                    QueueMemberModel.position <= new_position,
                    QueueMemberModel.user_id != user_id,
                )
                .values(position=QueueMemberModel.position - 1)
            )

        member.position = new_position
        return True


async def recalculate_positions(queue_id: int) -> None:
    """Normalize positions to be 1..N sequential."""
    async with session() as s:
        members = (
            await s.scalars(
                select(QueueMemberModel)
                .where(
                    QueueMemberModel.queue_id == queue_id,
                    QueueMemberModel.status == MemberStatus.ACTIVE,
                )
                .order_by(QueueMemberModel.position.asc())
                .with_for_update()
            )
        ).all()

        for idx, member in enumerate(members, start=1):
            member.position = idx
