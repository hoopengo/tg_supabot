from enum import Enum

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Sticker


class StickerAction(Enum):
    DOWNLOAD = "DOWNLOAD"
    DOWNLOAD_PACK = "DOWNLOAD_PACK"
    TRANSFORM_PACK = "TRANSFORM_PACK"


class StickerCallbackFactory(CallbackData, prefix="sticker"):
    action: StickerAction


sticker_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Скачать стикер",
                callback_data=StickerCallbackFactory(
                    action=StickerAction.DOWNLOAD,
                ).pack(),
            ),
            InlineKeyboardButton(
                text="Скачать пак",
                callback_data=StickerCallbackFactory(
                    action=StickerAction.DOWNLOAD_PACK,
                ).pack(),
            ),
        ],
    ],
)
