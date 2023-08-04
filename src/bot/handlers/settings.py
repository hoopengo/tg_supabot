from aiogram import F, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)


class NumbersCallbackFactory(CallbackData, prefix="fabnum"):
    action: str
    value: int


test_in_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Test",
                callback_data=NumbersCallbackFactory(action="change", value=2).pack(),
            )
        ]
    ]
)

settings_router = Router()


@settings_router.message(F.text == "Настройка")
async def _settings_btn_handler(message: Message):
    # send message with settings
    await message.answer("Test", reply_markup=test_in_kb)


@settings_router.callback_query(NumbersCallbackFactory.filter(F.action == "change"))
async def _test_btn_handler(
    callback: CallbackQuery,
    callback_data: NumbersCallbackFactory,
):
    await callback.message.answer(str(callback_data.model_dump()))
    await callback.answer()
