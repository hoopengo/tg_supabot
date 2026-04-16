from datetime import datetime
from typing import Sequence

from sqlalchemy import exists, func, select

from bot.db import StickerMessageModel, UserModel, session
from bot.redis import message_cache


async def get_next_sanitaries(chat_id: int, count: int = 2):
    if count is None or count <= 0:
        return []

    async with session() as s:
        result = (
            await s.scalars(
                select(UserModel)
                .where(UserModel.chat_id == chat_id, UserModel.sanitary_last == False)  # noqa
                .order_by(func.random())
                .limit(count)
            )
        ).all()

        if len(result) < count:
            result = (
                await s.scalars(
                    select(UserModel)
                    .where(UserModel.chat_id == chat_id)
                    .order_by(func.random())
                    .limit(count)
                )
            ).all()

        if len(result) == 0:
            return []

        deprecated_sanitaries = (
            await s.scalars(
                select(UserModel).where(
                    UserModel.chat_id == chat_id, UserModel.sanitary_last == True
                )
            )  # noqa
        ).all()

        for deprecated_sanitary in deprecated_sanitaries:
            deprecated_sanitary.sanitary_last = False

        for sanitary in result:
            sanitary.sanitary_last = True

        return result


async def get_members(
    chat_id: int, limit: int | None = None
) -> Sequence[UserModel] | None:
    async with session() as s:
        result = (
            await s.scalars(
                select(UserModel)
                .where(UserModel.chat_id == chat_id)
                .order_by(UserModel.penis_size.desc())
                .limit(limit)
            )
        ).all()

        return result


async def get_or_create_user(user_id: int, chat_id: int):
    user = await get_user(user_id, chat_id)
    if user is None:
        await add_user(user_id, chat_id)
        user = await get_user(user_id, chat_id)

    return user


async def add_user(
    user_id: int,
    chat_id: int,
    username: str | None = None,
    first_name: str | None = None,
) -> None:
    async with session() as s:
        s.add(
            UserModel(
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                first_name=first_name,
            )
        )


async def user_exist(user_id: int, chat_id: int) -> bool:
    async with session() as s:
        user_exists = await s.scalar(
            select(
                exists().where(
                    UserModel.user_id == user_id, UserModel.chat_id == chat_id
                )
            )
        )
        return user_exists


async def get_user_by_username(username: str, chat_id: int) -> UserModel | None:
    async with session() as s:
        return await s.scalar(
            select(UserModel).where(
                UserModel.chat_id == chat_id,
                UserModel.username == username,
            )
        )


async def get_user(user_id: int, chat_id: int):
    async with session() as s:
        user = await s.scalar(
            select(UserModel).where(
                UserModel.user_id == user_id, UserModel.chat_id == chat_id
            )
        )
        if user is None:
            return None

        # Calculate rank based on penis_size
        rank_result = await s.scalar(
            select(func.count(UserModel.id)).where(
                UserModel.chat_id == chat_id,
                UserModel.penis_size > user.penis_size,
            )
        )
        user.rank = (rank_result or 0) + 1
        return user


async def last_penis_update_now(
    user_id: int,
    chat_id: int,
) -> UserModel:
    async with session() as s:
        result: UserModel = (
            await s.scalars(
                select(UserModel).where(
                    UserModel.user_id == user_id, UserModel.chat_id == chat_id
                )
            )
        ).first()

        result.last_penis_update = datetime.utcnow()

    return result


async def update_dick_size(
    user_id: int,
    chat_id: int,
    append_size: int,
):
    async with session() as s:
        result: UserModel = (
            await s.scalars(
                select(UserModel).where(
                    UserModel.user_id == user_id, UserModel.chat_id == chat_id
                )
            )
        ).first()

        result.penis_size += append_size

        if result.penis_size < 0:
            result.penis_size = 0


async def transfer_penis_size(
    from_user_id: int,
    to_user_id: int,
    chat_id: int,
    amount: int,
) -> tuple[bool, str]:
    """
    Transfer centimeters from one user to another.

    Args:
        from_user_id: Sender user ID
        to_user_id: Receiver user ID
        chat_id: Chat ID where both users are
        amount: Amount of centimeters to transfer

    Returns:
        (success, message)
    """
    if amount <= 0:
        return False, "Сумма должна быть больше нуля."

    if from_user_id == to_user_id:
        return False, "Нельзя перевести сантиметры себе."

    async with session() as s:
        sender = await s.scalar(
            select(UserModel).where(
                UserModel.user_id == from_user_id, UserModel.chat_id == chat_id
            )
        )

        if not sender:
            return False, "Отправитель не найден."

        if sender.penis_size < amount:
            return (
                False,
                f"У тебя недостаточно сантиметров. У тебя {sender.penis_size} см.",
            )

        receiver = await s.scalar(
            select(UserModel).where(
                UserModel.user_id == to_user_id, UserModel.chat_id == chat_id
            )
        )

        if not receiver:
            return False, "Получатель не найден."

        # Atomic transfer
        sender.penis_size -= amount
        receiver.penis_size += amount

        return True, f"Успешно переведено {amount} см."


async def update_toxicity_level(
    user_id: int,
    chat_id: int,
    count: int,
):
    async with session() as s:
        result: UserModel = (
            await s.scalars(
                select(UserModel).where(
                    UserModel.user_id == user_id, UserModel.chat_id == chat_id
                )
            )
        ).first()

        result.toxicity_level += count

        if result.toxicity_level < 0:
            result.toxicity_level = 0


async def get_message_data(message_id: int) -> dict | None:
    if await message_cache.exists(message_id):
        return await message_cache.hgetall(message_id)

    async with session() as s:
        # get MessageModel from postgresql
        result = (
            await s.scalars(
                select(StickerMessageModel).where(StickerMessageModel.id == message_id)
            )
        ).first()

        # check that result exist
        if result is None:
            return None

        # get result as dict
        data = result.as_dict()

        # set cache
        await message_cache.hmset(result.id, data)

        # return result as dict
        return data


async def get_rating_users():
    async with session() as s:
        result = (
            await s.scalars(select(UserModel).where(UserModel.penis_size != 0))
        ).all()
        return result


async def get_random_users(chat_id: int, count: int = 3) -> list[UserModel]:
    async with session() as s:
        result = (
            await s.scalars(
                select(UserModel)
                .where(UserModel.chat_id == chat_id)
                .order_by(func.random())
                .limit(count)
            )
        ).all()

        return result
