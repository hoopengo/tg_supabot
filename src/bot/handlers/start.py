from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardRemove

from bot.db.methods import get_user, add_user

start_router = Router()

start_sticker_id = "CAACAgIAAxkBAAMfZL6iDIJXXZfl7dd6b_5cDj13Fc8AAlY1AAIqiqFJG21rvpgD4GQvBA"


@start_router.message(CommandStart(ignore_case=True, ignore_mention=True), F.chat.type == "private")
async def _command_start_private_handler(message: Message):
    # send start sticker
    await message.answer_sticker(start_sticker_id)

    # send start message
    await message.answer(
        "<b>Привет, акулёнок!</b> Ты можешь прислать мне стикер для обработки 💕",
        reply_markup=ReplyKeyboardRemove(),
    )


@start_router.message(CommandStart(ignore_case=True, ignore_mention=True), F.chat.type != "private")
async def _command_start_public_handler(message: Message):
    if await get_user(message.from_user.id, message.chat.id) is not None:
        return await message.answer(f"Ты уже зарегестрирован в системе под id: {message.from_user.id}")

    try:
        await add_user(message.from_user.id, message.chat.id)
    except Exception as err:
        return await message.answer(f"Произошла ошибка: {err}")
    else:
        # send start message
        await message.answer(
            f"Ты был успешно зарегестрирован в системе под id: {message.from_user.id}",
            reply_markup=ReplyKeyboardRemove(),
        )
