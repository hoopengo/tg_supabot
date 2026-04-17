from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

SPIN_DURATION = 15
RED_NUMBERS = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
BLACK_NUMBERS = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]


class SlotsCallback(CallbackData, prefix="sl"):
    action: str
    bet_type: str = ""
    number: int = 0
    amount: int = 0


def build_bet_type_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="🔴 Красное (x2)",
                callback_data=SlotsCallback(action="select", bet_type="red").pack(),
            ),
            InlineKeyboardButton(
                text="⚫ Черное (x2)",
                callback_data=SlotsCallback(action="select", bet_type="black").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔢 Четное (x2)",
                callback_data=SlotsCallback(action="select", bet_type="even").pack(),
            ),
            InlineKeyboardButton(
                text="🔢 Нечетное (x2)",
                callback_data=SlotsCallback(action="select", bet_type="odd").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="1️⃣ 1-12 (x3)",
                callback_data=SlotsCallback(action="select", bet_type="dozen1").pack(),
            ),
            InlineKeyboardButton(
                text="2️⃣ 13-24 (x3)",
                callback_data=SlotsCallback(action="select", bet_type="dozen2").pack(),
            ),
            InlineKeyboardButton(
                text="3️⃣ 25-36 (x3)",
                callback_data=SlotsCallback(action="select", bet_type="dozen3").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔢 Конкретное число (x36)",
                callback_data=SlotsCallback(action="select", bet_type="number").pack(),
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_number_keyboard() -> InlineKeyboardMarkup:
    numbers = list(range(1, 37))
    rows = []
    for i in range(0, 36, 6):
        row = numbers[i : i + 6]
        btn_row = [
            InlineKeyboardButton(
                text=str(n),
                callback_data=SlotsCallback(
                    action="select_num", bet_type="number", number=n
                ).pack(),
            )
            for n in row
        ]
        rows.append(btn_row)
    rows.append(
        [
            InlineKeyboardButton(
                text="🟢 Зеро (0)",
                callback_data=SlotsCallback(
                    action="select_num", bet_type="number", number=0
                ).pack(),
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад", callback_data=SlotsCallback(action="back").pack()
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


ALL_IN_MARKER = -1


def build_amount_keyboard(bet_type: str, number: int = 0) -> InlineKeyboardMarkup:
    amounts = [1, 5, 10, 25, 50, 100]
    rows = []
    for i in range(0, len(amounts), 3):
        row = amounts[i : i + 3]
        btn_row = [
            InlineKeyboardButton(
                text=f"{amt} см",
                callback_data=SlotsCallback(
                    action="confirm", bet_type=bet_type, number=number, amount=amt
                ).pack(),
            )
            for amt in row
        ]
        rows.append(btn_row)
    rows.append(
        [
            InlineKeyboardButton(
                text="🔥 All In",
                callback_data=SlotsCallback(
                    action="confirm", bet_type=bet_type, number=number, amount=ALL_IN_MARKER
                ).pack(),
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=SlotsCallback(action="back", bet_type=bet_type).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✖ Закрыть", callback_data=SlotsCallback(action="close").pack()
                )
            ]
        ]
    )
