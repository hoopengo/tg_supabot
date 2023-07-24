from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

start_router = Router()

start_sticker_id = "CAACAgIAAxkBAAMfZL6iDIJXXZfl7dd6b_5cDj13Fc8AAlY1AAIqiqFJG21rvpgD4GQvBA"


@start_router.message(CommandStart(ignore_case=True, ignore_mention=True))
async def _command_start_handler(message: Message):
    # send start sticker
    await message.answer_sticker(start_sticker_id)

    # send start message
    await message.answer("<b>Привет, акулёнок!</b> Снизу ты увидишь кнопочки, не хочешь их потыгыдыкать? 💕")
