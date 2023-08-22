from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Настройка"),
        ],
    ],
    is_persistent=True,
    resize_keyboard=True,
)
