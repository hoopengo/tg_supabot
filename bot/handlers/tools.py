from aiogram import Router, F
from aiogram.types import Message

tools_router = Router()


@tools_router.message(F.sticker)
async def _stick(message: Message):
    await message.answer("<b>Мне нравится этот стикер, акулёнок!</b> Возможно ты хочешь получить некоторую информацию:")
    await message.answer(f"<b>sticker_id:</b> {message.sticker.file_id}")
    await message.answer(f"<b>is_animated:</b> {message.sticker.is_animated}")
