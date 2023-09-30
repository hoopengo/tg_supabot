from bot.db import session, UserModel, StickerMessageModel
from sqlalchemy import select, func
from bot.redis import message_cache
from datetime import datetime


async def get_next_sanitaries(chat_id: int, count: int = 2):
    if count <= 0:
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
                    select(UserModel).where(UserModel.chat_id == chat_id).order_by(func.random()).limit(count)
                )
            ).all()

        if len(result) == 0:
            return []

        deprecated_sanitaries = (
            await s.scalars(
                select(UserModel).where(UserModel.chat_id == chat_id, UserModel.sanitary_last == True)
            )  # noqa
        ).all()

        for deprecated_sanitary in deprecated_sanitaries:
            deprecated_sanitary.sanitary_last = False

        for sanitary in result:
            sanitary.sanitary_last = True

        return result


async def get_members(chat_id: int, limit: int | None = None):
    async with session() as s:
        result = (
            await s.scalars(
                select(UserModel).where(UserModel.chat_id == chat_id).order_by(UserModel.penis_size.desc()).limit(limit)
            )
        ).all()

        return result


async def get_or_create_user(user_id: int, chat_id: int):
    user = await get_user(user_id, chat_id)
    if user is None:
        await add_user(user_id, chat_id)
        user = await get_user(user_id, chat_id)

    return user


async def add_user(user_id: int, chat_id: int) -> None:
    async with session() as s:
        s.add(
            UserModel(
                chat_id=chat_id,
                user_id=user_id,
            )
        )


async def get_user(user_id: int, chat_id: int):
    users = await get_members(chat_id)
    position = 1
    for user in users:
        if user.user_id == user_id:
            user.rank = position
            return user
        position += 1
    return None


async def last_penis_update_now(
    user_id: int,
    chat_id: int,
) -> UserModel:
    async with session() as s:
        result: UserModel = (
            await s.scalars(select(UserModel).where(UserModel.user_id == user_id, UserModel.chat_id == chat_id))
        ).first()

        result.last_penis_update = datetime.utcnow()
        await s.commit()

    return result


async def update_dick_size(
    user_id: int,
    chat_id: int,
    append_size: int,
):
    async with session() as s:
        result: UserModel = (
            await s.scalars(select(UserModel).where(UserModel.user_id == user_id, UserModel.chat_id == chat_id))
        ).first()

        result.penis_size += append_size
        await s.commit()


async def get_message_data(message_id: int) -> dict | None:
    if await message_cache.exists(message_id):
        return await message_cache.hgetall(message_id)

    async with session() as s:
        # get MessageModel from postgresql
        result = (await s.scalars(select(StickerMessageModel).where(StickerMessageModel.id == message_id))).first()

        # check that result exist
        if result is None:
            return None

        # get result as dict
        data = result.as_dict()

        # set cache
        await message_cache.hmset(result.id, data)

        # return result as dict
        return data
