import random
from io import BytesIO
from pathlib import Path
from typing import Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from aiogram import Bot, F, Router, flags
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message, Sticker, StickerSet

from bot.keyboards.inline import (
    StickerAction,
    StickerCallbackFactory,
    get_sticker_keyboard,
)

sticker_router = Router()

sticker_info_texts = (
    "<b>Мне нравится этот стикер, акулёнок!</b> Возможно ты хочешь получить некоторую информацию:",
    "<b>Акулёнок, этот стикер просто супер!</b> Держи информацию:",
    "<b>Мне кажется этот стикер великолепен, акулёнок!</b> Вот информация по нему:",
    "<b>Акулёнок, твой выбор божественнен!</b> Вот как я вижу этот стикер:",
    "<b>Твой выбор великолепен, акулёнок!</b> Информация по стикеру:",
)


class StickerData(StatesGroup):
    sticker_id = State()
    set_name = State()


def _get_sticker_info(sticker: Sticker) -> str:
    """
    Get information about a sticker.

    Args:
        sticker (Sticker): The sticker object.

    Returns:
        str: The information about the sticker.
    """
    return f"""<b>ID стикера:</b> {sticker.file_id} <u>(локальный)</u>
<b>Анимирован:</b> {"Да" if sticker.is_animated or sticker.is_video else "Нет"}
<b>Добавить:</b> https://t.me/addstickers/{sticker.set_name}"""


async def _get_sticker_as_file(sticker: Sticker) -> tuple[bytes, str]:
    """
    Get a sticker as a file.

    Args:
        sticker (Sticker): The sticker object.

    Returns:
        tuple[bytes, str]: A tuple containing saved sticker in bytes, and the sticker filename.
    """
    # create BytesIO object
    saved_sticker = BytesIO()

    # get bot
    bot = sticker.get_mounted_bot()

    # download sticker
    sticker_file = await bot.get_file(sticker.file_id)
    await bot.download_file(sticker_file.file_path, saved_sticker)

    # convert str to Path
    filename = Path(sticker_file.file_path)

    # return sticker as bytes and sticker filename
    return saved_sticker.getvalue(), filename.name


async def _get_set_as_zip(sticker_set: StickerSet):
    stickers_files = await _get_stickers_as_bytes(sticker_set.stickers)

    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, mode="w", compression=ZIP_DEFLATED) as zip_file:
        for sticker_bytes, sticker_filename in stickers_files:
            zip_file.writestr(sticker_filename, sticker_bytes)

    zip_buffer.flush()
    zip_buffer.seek(0)

    filename = sticker_set.name + ".zip"
    return zip_buffer.getvalue(), filename


async def _get_stickers_as_bytes(stickers: Sequence[Sticker]):
    stickers_files = set()
    for sticker in stickers:
        bytes_, name = await _get_sticker_as_file(sticker)
        stickers_files.add((bytes_, name))

    return stickers_files


@sticker_router.message(F.sticker)
@flags.chat_action(action="choose_sticker")
async def _sticker_handler(message: Message) -> None:
    """
    Handle a sticker message.

    Args:
        message (Message): The sticker message.
        bot (Bot): The bot object.

    """
    sticker = message.sticker

    # get stickerfile options
    sticker_bytes, filename = await _get_sticker_as_file(sticker)

    # change .webm suffix to .gif suffix
    converted = sticker.is_video or sticker.is_animated
    if converted:
        filename = filename.replace(".webm", ".gif")

    # get sticker as file
    file = BufferedInputFile(sticker_bytes, filename)

    # get caption for reply
    caption = random.choice(sticker_info_texts) + "\n" + _get_sticker_info(sticker)

    # get keyboard
    keyboard = get_sticker_keyboard(sticker)

    # send sticker as file
    if converted:
        await message.reply_animation(file, caption=caption, reply_markup=keyboard)
    else:
        await message.reply_photo(file, caption=caption, reply_markup=keyboard)


@sticker_router.callback_query(
    StickerCallbackFactory.filter(F.action == StickerAction.DOWNLOAD)
)
@flags.chat_action(action="upload_document")
async def _download_sticker_btn_handler(
    callback: CallbackQuery,
    callback_data: StickerCallbackFactory,
    bot: Bot,
):
    sticker_bytes, filename = await _get_sticker_as_file(callback_data.sticker_id)
    file = BufferedInputFile(sticker_bytes, filename)

    await callback.message.reply_document(file)
    await callback.answer()


@sticker_router.callback_query(
    StickerCallbackFactory.filter(F.action == StickerAction.DOWNLOAD_PACK)
)
@flags.chat_action(action="upload_document")
async def _download_pack_btn_handler(
    callback: CallbackQuery,
    callback_data: StickerCallbackFactory,
    bot: Bot,
):
    if callback_data.set_name is None:
        await callback.message.reply("У этого стикера нету стикерпака.")

    sticker_set = await bot.get_sticker_set(callback_data.set_name)

    zip_file, filename = await _get_set_as_zip(sticker_set)
    file = BufferedInputFile(zip_file, filename)

    await callback.message.reply_document(file)
    await callback.answer()
