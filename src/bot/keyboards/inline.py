from enum import Enum

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Sticker


class StickerAction(Enum):
    DOWNLOAD = "DOWNLOAD"
    DOWNLOAD_PACK = "DOWNLOAD_PACK"
    TRANSFORM_PACK = "TRANSFORM_PACK"


class StickerCallbackFactory(CallbackData, prefix="sticker"):
    action: StickerAction
    set


def get_sticker_keyboard(sticker: Sticker):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Скачать стикер",
                    callback_data=StickerCallbackFactory(
                        action=StickerAction.DOWNLOAD,
                    ).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Скачать пак",
                    callback_data=StickerCallbackFactory(
                        action=StickerAction.DOWNLOAD_PACK,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="Превратить пак в 18+",
                    callback_data=StickerCallbackFactory(
                        action=StickerAction.TRANSFORM_PACK,
                        set_name=sticker.set_name,
                    ).pack(),
                ),
            ],
        ],
    )
