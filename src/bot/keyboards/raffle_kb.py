from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class RaffleCallback(CallbackData, prefix="rf"):
    """Raffle callbacks."""

    action: str  # toggle, close
    raffle_id: int


def raffle_keyboard(raffle_id: int, active: bool = True) -> InlineKeyboardMarkup:
    """Keyboard for the live raffle message."""
    rows: list[list[InlineKeyboardButton]] = []

    if active:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🎲 Участвовать",
                    callback_data=RaffleCallback(
                        action="toggle", raffle_id=raffle_id
                    ).pack(),
                ),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="✖ Закрыть",
                callback_data=RaffleCallback(action="close", raffle_id=raffle_id).pack(),
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)
