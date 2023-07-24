from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

start_router = Router()


@start_router.message(CommandStart(ignore_case=True, ignore_mention=True))
async def _start(message: Message):
    await message.answer_sticker("CAACAgIAAxkBAAMfZL6iDIJXXZfl7dd6b_5cDj13Fc8AAlY1AAIqiqFJG21rvpgD4GQvBA")
    await message.answer("<b>Привет, акулёнок!</b> Снизу ты увидишь кнопочки, не хочешь их потыгыдыкать? 💕")
