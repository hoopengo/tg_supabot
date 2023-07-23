from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

start_router = Router()


@start_router.message(CommandStart())
async def user_start(message: Message):
    await message.answer("Привет, акулёнок!")
