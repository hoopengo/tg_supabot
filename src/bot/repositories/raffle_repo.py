from datetime import datetime
from typing import Sequence

from sqlalchemy import delete, select, update

from bot.db import session
from bot.db.models import (
    RaffleModel,
    RaffleParticipantModel,
    RaffleStatus,
)


async def create_raffle(
    chat_id: int,
    topic_count: int,
    created_by: int,
    ends_at: datetime,
) -> RaffleModel:
    async with session() as s:
        raffle = RaffleModel(
            chat_id=chat_id,
            topic_count=topic_count,
            created_by=created_by,
            ends_at=ends_at,
        )
        s.add(raffle)
        await s.flush()
        await s.refresh(raffle)
        return raffle


async def get_raffle(raffle_id: int) -> RaffleModel | None:
    async with session() as s:
        return await s.scalar(select(RaffleModel).where(RaffleModel.id == raffle_id))


async def get_active_raffle(chat_id: int) -> RaffleModel | None:
    async with session() as s:
        return await s.scalar(
            select(RaffleModel).where(
                RaffleModel.chat_id == chat_id,
                RaffleModel.status == RaffleStatus.ACTIVE,
            )
        )


async def get_due_raffles(now: datetime) -> Sequence[RaffleModel]:
    async with session() as s:
        result = await s.scalars(
            select(RaffleModel).where(
                RaffleModel.status == RaffleStatus.ACTIVE,
                RaffleModel.ends_at <= now,
            )
        )
        return result.all()


async def update_raffle_message_id(raffle_id: int, message_id: int) -> None:
    async with session() as s:
        await s.execute(
            update(RaffleModel)
            .where(RaffleModel.id == raffle_id)
            .values(message_id=message_id)
        )


async def update_raffle_status(raffle_id: int, status: RaffleStatus) -> None:
    async with session() as s:
        await s.execute(
            update(RaffleModel)
            .where(RaffleModel.id == raffle_id)
            .values(status=status)
        )


async def delete_raffle(raffle_id: int) -> bool:
    async with session() as s:
        result = await s.execute(delete(RaffleModel).where(RaffleModel.id == raffle_id))
        return result.rowcount > 0


async def get_participants(raffle_id: int) -> Sequence[RaffleParticipantModel]:
    async with session() as s:
        result = await s.scalars(
            select(RaffleParticipantModel)
            .where(RaffleParticipantModel.raffle_id == raffle_id)
            .order_by(RaffleParticipantModel.joined_at)
        )
        return result.all()


async def get_participant(
    raffle_id: int, user_id: int
) -> RaffleParticipantModel | None:
    async with session() as s:
        return await s.scalar(
            select(RaffleParticipantModel).where(
                RaffleParticipantModel.raffle_id == raffle_id,
                RaffleParticipantModel.user_id == user_id,
            )
        )


async def get_participant_count(raffle_id: int) -> int:
    async with session() as s:
        return int(
            await s.scalar(
                select(sa.func.count())
                .select_from(RaffleParticipantModel)
                .where(RaffleParticipantModel.raffle_id == raffle_id)
            )
        )


async def add_participant(
    raffle_id: int,
    user_id: int,
    username: str | None,
    first_name: str | None,
) -> RaffleParticipantModel:
    async with session() as s:
        participant = RaffleParticipantModel(
            raffle_id=raffle_id,
            user_id=user_id,
            username=username,
            first_name=first_name,
        )
        s.add(participant)
        await s.flush()
        await s.refresh(participant)
        return participant


async def remove_participant(raffle_id: int, user_id: int) -> bool:
    async with session() as s:
        result = await s.execute(
            delete(RaffleParticipantModel).where(
                RaffleParticipantModel.raffle_id == raffle_id,
                RaffleParticipantModel.user_id == user_id,
            )
        )
        return result.rowcount > 0


async def assign_topic_number(
    participant_id: int, topic_number: int | None
) -> None:
    async with session() as s:
        await s.execute(
            update(RaffleParticipantModel)
            .where(RaffleParticipantModel.id == participant_id)
            .values(topic_number=topic_number)
        )
