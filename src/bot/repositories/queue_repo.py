from datetime import datetime
from typing import Sequence

from sqlalchemy import delete, select, update

from bot.db import session
from bot.db.models import QueueModel, QueueStatus


async def create_queue(
    chat_id: int,
    title: str,
    created_by: int,
) -> QueueModel:
    async with session() as s:
        queue = QueueModel(
            chat_id=chat_id,
            title=title,
            created_by=created_by,
        )
        s.add(queue)
        await s.flush()
        await s.refresh(queue)
        return queue


async def get_queue(queue_id: int) -> QueueModel | None:
    async with session() as s:
        result = await s.scalar(select(QueueModel).where(QueueModel.id == queue_id))
        return result


async def get_queue_by_message(chat_id: int, message_id: int) -> QueueModel | None:
    async with session() as s:
        result = await s.scalar(
            select(QueueModel).where(
                QueueModel.chat_id == chat_id,
                QueueModel.message_id == message_id,
            )
        )
        return result


async def get_active_queues(chat_id: int) -> Sequence[QueueModel]:
    async with session() as s:
        result = await s.scalars(
            select(QueueModel)
            .where(QueueModel.chat_id == chat_id)
            .order_by(QueueModel.created_at.desc())
        )
        return result.all()


async def update_queue_message_id(queue_id: int, message_id: int) -> None:
    async with session() as s:
        await s.execute(
            update(QueueModel)
            .where(QueueModel.id == queue_id)
            .values(message_id=message_id, updated_at=datetime.utcnow())
        )


async def update_queue_status(queue_id: int, status: QueueStatus) -> None:
    async with session() as s:
        await s.execute(
            update(QueueModel)
            .where(QueueModel.id == queue_id)
            .values(status=status, updated_at=datetime.utcnow())
        )


async def touch_queue(queue_id: int) -> None:
    async with session() as s:
        await s.execute(
            update(QueueModel)
            .where(QueueModel.id == queue_id)
            .values(updated_at=datetime.utcnow())
        )


async def delete_queue(queue_id: int) -> bool:
    async with session() as s:
        result = await s.execute(delete(QueueModel).where(QueueModel.id == queue_id))
        return result.rowcount > 0
