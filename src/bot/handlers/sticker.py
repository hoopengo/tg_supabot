import random
from io import BytesIO
from pathlib import Path
from typing import Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from aiogram import Bot, F, Router, flags
from aiogram.enums.parse_mode import ParseMode
from aiogram.types import BufferedInputFile, CallbackQuery, Message, Sticker, StickerSet
from bot.db.methods import get_message_data
from bot.db import StickerMessageModel, session
from bot.keyboards.inline import (
    StickerAction,
    StickerCallbackFactory,
    sticker_keyboard,
)


sticker_router = Router()

on_ready_sticker_id = "CAACAgIAAxkBAAIB62TNYBW6aLGpTbftooGX2xsB7peJAAJZLQACy7ypSbKCxiEXCMjlLwQ"

sticker_info_texts = (
    r"<b>Мне нравится этот стикер, акулёнок!</b> Возможно ты хочешь получить некоторую информацию:",
    r"<b>Акулёнок, этот стикер просто супер!</b> Держи информацию:",
    r"<b>Мне кажется этот стикер великолепен, акулёнок!</b> Вот информация по нему:",
    r"<b>Акулёнок, твой выбор божественнен!</b> Вот как я вижу этот стикер:",
    r"<b>Твой выбор великолепен, акулёнок!</b> Информация по стикеру:",
)


def _get_sticker_info(sticker: Sticker) -> str:
    """
    Get information about a sticker.

    Args:
        sticker (Sticker): The sticker object.

    Returns:
        str: The information about the sticker.
    """
    return f"""<b>ID стикера:</b> <code>{sticker.file_id}</code> <u>(локальный)</u>
<b>Анимирован:</b> {"Да" if sticker.is_animated or sticker.is_video else "Нет"}
<b>Добавить:</b> https://t.me/addstickers/{sticker.set_name}"""


async def _get_sticker_as_file(sticker: Sticker | str, bot: Bot) -> tuple[bytes, str]:
    """
    Get a sticker as a file.

    Args:
        sticker (Sticker | str): The sticker object or file_id.

    Returns:
        tuple[bytes, str]: A tuple containing saved sticker in bytes, and the sticker filename.
    """
    # create BytesIO object
    saved_sticker = BytesIO()

    # get file_id
    if type(sticker) is str:
        file_id = sticker
    else:
        file_id = sticker.file_id

    # download sticker
    sticker_file = await bot.get_file(file_id)
    await bot.download_file(sticker_file.file_path, saved_sticker)

    # convert str to Path
    filename = Path(sticker_file.file_path)

    # return sticker as bytes and sticker filename
    return saved_sticker.getvalue(), filename.name


async def _get_set_as_zip(sticker_set: StickerSet, bot):
    stickers_files = await _get_stickers_as_bytes(sticker_set.stickers, bot)

    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, mode="w", compression=ZIP_DEFLATED) as zip_file:
        for sticker_bytes, sticker_filename in stickers_files:
            zip_file.writestr(sticker_filename, sticker_bytes)

    zip_buffer.flush()
    zip_buffer.seek(0)

    filename = sticker_set.name + ".zip"
    return zip_buffer.getvalue(), filename


async def _get_stickers_as_bytes(stickers: Sequence[Sticker], bot: Bot):
    stickers_files = set()
    for sticker in stickers:
        bytes_, name = await _get_sticker_as_file(sticker, bot)
        stickers_files.add((bytes_, name))

    return stickers_files


@sticker_router.message(F.sticker & F.chat.type == "private")
@flags.chat_action(action="choose_sticker")
async def _sticker_handler(message: Message, bot: Bot) -> None:
    """
    Handle a sticker message.

    Args:
        message (Message): The sticker message.

    """
    sticker = message.sticker

    # get stickerfile options
    sticker_bytes, filename = await _get_sticker_as_file(sticker, bot=bot)

    # change .webm suffix to .gif suffix
    converted = sticker.is_video or sticker.is_animated
    if converted:
        filename = filename.replace(".webm", ".gif")

    # get sticker as file
    file = BufferedInputFile(sticker_bytes, filename)

    # get caption for reply
    caption = random.choice(sticker_info_texts) + "\n" + _get_sticker_info(sticker)

    # get keyboard
    keyboard = sticker_keyboard

    # make function params
    function_params = {
        "caption": caption,
        "reply_markup": keyboard,
        "parse_mode": ParseMode.HTML,
    }

    # send sticker as file
    if converted:
        reply_message = await message.reply_animation(file, **function_params)
    else:
        reply_message = await message.reply_photo(file, **function_params)

    # add data to database
    if reply_message is None:
        return

    async with session() as s:
        s.add(
            StickerMessageModel(
                message_id=reply_message.message_id,
                file_id=sticker.file_id,
                set_name=sticker.set_name,
            )
        )


@sticker_router.callback_query(StickerCallbackFactory.filter(F.action == StickerAction.DOWNLOAD))
@flags.chat_action(action="upload_document")
async def _download_sticker_btn_handler(callback: CallbackQuery, bot: Bot):
    message_data = await get_message_data(callback.message.message_id)

    if message_data is None:
        return await callback.answer(text="Произошла ошибка.")

    await callback.answer()

    sticker_bytes, filename = await _get_sticker_as_file(message_data.get("file_id"), bot=bot)
    file = BufferedInputFile(sticker_bytes, filename)

    await callback.message.reply_document(file, disable_content_type_detection=True)


@sticker_router.callback_query(StickerCallbackFactory.filter(F.action == StickerAction.DOWNLOAD_PACK))
@flags.chat_action(action="upload_document")
async def _download_pack_btn_handler(callback: CallbackQuery, bot: Bot):
    message_data = await get_message_data(callback.message.message_id)

    if message_data is None:
        return await callback.answer(text="Произошла ошибка.")

    if (sticker_set := await bot.get_sticker_set(message_data.get("set_name"))) is None:
        return await callback.answer(text="У этого стикера нету стикерпака.")

    await callback.message.answer_sticker(on_ready_sticker_id)
    await callback.message.answer(text="<b>Я уже работаю над этим акулёнок, дай мне некоторое время!</b>")
    await callback.answer()

    zip_file, filename = await _get_set_as_zip(sticker_set, bot)
    file = BufferedInputFile(zip_file, filename)

    await callback.message.reply_document(file)
