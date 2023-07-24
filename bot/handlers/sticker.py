from aiogram import Router, F, Bot
from aiogram.types import Message, BufferedInputFile, Sticker
import random
from io import BytesIO
from pathlib import Path

sticker_router = Router()

sticker_info_texts = [
    "<b>Мне нравится этот стикер, акулёнок!</b> Возможно ты хочешь получить некоторую информацию:",
    "<b>Акулёнок, этот стикер просто супер!</b> Держи информацию:",
    "<b>Мне кажется этот стикер великолепен, акулёнок!</b> Вот информация по нему:"
    "<b>Акулёнок, твой выбор божественнен!</b> Вот как я вижу этот стикер:"
    "<b>Мне кажется этот стикер великолепен, акулёнок!</b> Вот информация по нему:",
]


def get_sticker_info(sticker: Sticker):
    return f"""{random.choice(sticker_info_texts)}
<b>ID стикера:</b> {sticker.file_id} <u>(локальный)</u>
<b>Анимирован:</b> {"Да" if sticker.is_animated else "Нет"} 
<b>Добавить:</b> https://t.me/addstickers/{sticker.set_name}"""


async def get_sticker_as_file(sticker: Sticker, bot: Bot):
    # create BytesIO object
    saved_sticker = BytesIO()

    # download sticker
    sticker_file = await bot.get_file(sticker.file_id)
    await bot.download_file(sticker_file.file_path, saved_sticker)

    # get correct file suffix
    filename = Path(sticker_file.file_path)
    converted = sticker.is_video or sticker.is_animated
    if converted:
        filename = filename.with_suffix(".gif")
        print(filename)

    # convert sticker into InputFile and return it
    return converted, BufferedInputFile(saved_sticker.getvalue(), str(filename.resolve()))


@sticker_router.message(F.sticker)
async def _stick(message: Message, bot: Bot):
    sticker = message.sticker
    # get sticker as file
    converted, file = await get_sticker_as_file(sticker, bot)

    # get caption for reply
    caption = get_sticker_info(sticker)

    # send sticker as file
    if converted:
        await message.reply_animation(file, caption=caption)
    else:
        await message.reply_photo(file, caption=caption)
