import asyncio
import json
import random

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.handlers.casino import get_user_penis, update_penis_safe
from bot.keyboards.slots_kb import (
    RED_NUMBERS,
    BLACK_NUMBERS,
    SlotsCallback,
    build_amount_keyboard,
    build_bet_type_keyboard,
    build_cancel_keyboard,
    build_number_keyboard,
    SPIN_DURATION,
)
from bot.redis import message_cache

router = Router()

REDIS_ACTIVE_KEY = "slots_active"
REDIS_BETS_KEY = "slots_bets"
REDIS_LOCK_KEY = "slots_lock"

MIN_BET = 1
MAX_BET = 100


def get_active_key(chat_id: int) -> str:
    return f"{REDIS_ACTIVE_KEY}:{chat_id}"


def get_bets_key(chat_id: int) -> str:
    return f"{REDIS_BETS_KEY}:{chat_id}"


def get_lock_key(chat_id: int) -> str:
    return f"{REDIS_LOCK_KEY}:{chat_id}"


async def acquire_bets_lock(chat_id: int) -> bool:
    lock_key = get_lock_key(chat_id)
    try:
        result = await message_cache.set(lock_key, "1", nx=True, ex=5)
        return result
    except Exception:
        return False


async def release_bets_lock(chat_id: int) -> None:
    await message_cache.delete(get_lock_key(chat_id))


async def check_roulette_active(chat_id: int) -> bool:
    key = get_active_key(chat_id)
    return await message_cache.exists(key)


async def set_roulette_active(chat_id: int, message_id: int) -> None:
    key = get_active_key(chat_id)
    await message_cache.setex(key, SPIN_DURATION + 10, str(message_id))


async def clear_roulette_active(chat_id: int) -> None:
    key = get_active_key(chat_id)
    await message_cache.delete(key)


async def save_bet(
    chat_id: int, user_id: int, bet_type: str, number: int, amount: int
) -> bool:
    key = get_bets_key(chat_id)

    # Wait for lock with retry
    for _ in range(20):
        if await acquire_bets_lock(chat_id):
            break
        await asyncio.sleep(0.05)
    else:
        return False

    try:
        existing = await message_cache.get(key)
        bets = json.loads(existing) if existing else []

        # Check if user already has this bet type (for number bet, check number too)
        for bet in bets:
            if bet["user_id"] == user_id and bet["bet_type"] == bet_type:
                if bet_type != "number" or bet.get("number") == number:
                    bet["amount"] = amount
                    break
        else:
            bets.append(
                {
                    "user_id": user_id,
                    "bet_type": bet_type,
                    "number": number,
                    "amount": amount,
                }
            )

        await message_cache.setex(key, SPIN_DURATION + 60, json.dumps(bets))
        return True
    finally:
        await release_bets_lock(chat_id)


async def get_bets(chat_id: int) -> list:
    key = get_bets_key(chat_id)
    existing = await message_cache.get(key)
    return json.loads(existing) if existing else []


async def clear_bets(chat_id: int) -> None:
    key = get_bets_key(chat_id)
    await message_cache.delete(key)


def spin_roulette() -> int:
    return random.randint(0, 36)


def get_winner_type(number: int) -> str:
    if number == 0:
        return "🟢 Зеро"
    if number in RED_NUMBERS:
        return "🔴 Красное"
    return "⚫ Черное"


def calculate_payout(
    bet_type: str, number: int, winning_number: int, amount: int
) -> int:
    if bet_type == "number":
        return amount * 36 if number == winning_number else 0
    if bet_type == "red":
        return amount * 2 if winning_number in RED_NUMBERS else 0
    if bet_type == "black":
        return amount * 2 if winning_number in BLACK_NUMBERS else 0
    if bet_type == "even":
        return amount * 2 if winning_number % 2 == 0 and winning_number != 0 else 0
    if bet_type == "odd":
        return amount * 2 if winning_number % 2 == 1 else 0
    if bet_type == "dozen1":
        return amount * 3 if 1 <= winning_number <= 12 else 0
    if bet_type == "dozen2":
        return amount * 3 if 13 <= winning_number <= 24 else 0
    if bet_type == "dozen3":
        return amount * 3 if 25 <= winning_number <= 36 else 0
    return 0


def format_bets_text(bets: list, users: dict) -> str:
    bet_type_names = {
        "red": "🔴 Красное",
        "black": "⚫ Черное",
        "even": "🔢 Четное",
        "odd": "🔢 Нечетное",
        "dozen1": "1️⃣ 1-я дюжина",
        "dozen2": "2️⃣ 2-я дюжина",
        "dozen3": "3️⃣ 3-я дюжина",
        "number": "🔢 Число",
    }

    if not bets:
        return "Ставок пока нет"
    lines = []
    for bet in bets:
        user_name = users.get(bet["user_id"], f"User-{bet['user_id']}")
        bet_type = bet_type_names.get(bet["bet_type"], bet["bet_type"])
        if bet["bet_type"] == "number":
            lines.append(f"• {user_name}: {bet['amount']} см на {bet['number']}")
        else:
            lines.append(f"• {user_name}: {bet['amount']} см на {bet_type}")
    return "\n".join(lines)


async def start_roulette_game(message: Message) -> None:
    chat_id = message.chat.id

    if await check_roulette_active(chat_id):
        await message.answer("Рулетка уже крутится!", parse_mode=ParseMode.HTML)
        return

    msg = await message.answer(
        "🎰 <b>Рулетка</b>\n\n"
        "Ставки: 1-100 см\n"
        "Время на ставки: 30 сек\n\n"
        "Выберите тип ставки:",
        reply_markup=build_bet_type_keyboard(),
        parse_mode=ParseMode.HTML,
    )

    await set_roulette_active(chat_id, msg.message_id)
    await clear_bets(chat_id)

    # Run roulette finish in background to not block the handler
    asyncio.create_task(finish_roulette(message.bot, chat_id, msg.message_id))


async def finish_roulette(bot, chat_id: int, message_id: int) -> None:
    # Wait for betting period
    await asyncio.sleep(SPIN_DURATION)

    winning_number = spin_roulette()
    winner_type = get_winner_type(winning_number)

    bets = await get_bets(chat_id)
    await clear_roulette_active(chat_id)
    await clear_bets(chat_id)

    results = []

    for bet in bets:
        payout = calculate_payout(
            bet["bet_type"], bet["number"], winning_number, bet["amount"]
        )
        if payout > 0:
            _, actual_win, _ = await update_penis_safe(
                bet["user_id"], chat_id, payout, bet["amount"]
            )
            results.append(f"• User-{bet['user_id']}: +{actual_win} см")
        else:
            await update_penis_safe(
                bet["user_id"], chat_id, -bet["amount"], bet["amount"]
            )

    result_text = f"🎰 <b>Рулетка</b>\n\nВыпало: {winning_number} ({winner_type})\n\n"

    if results:
        result_text += "Победители:\n" + "\n".join(results)
    else:
        result_text += "Никто не угадал!"

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=result_text,
            reply_markup=build_cancel_keyboard(),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass


@router.message(Command("slots", ignore_case=True), F.chat.type != "private")
async def slots_command(message: Message):
    await start_roulette_game(message)


@router.callback_query(SlotsCallback.filter())
async def slots_callback(query: CallbackQuery, callback_data: SlotsCallback):
    await query.answer()

    if not query.message:
        return

    chat_id = query.message.chat.id
    user_id = query.from_user.id
    action = callback_data.action

    if action == "close":
        await query.message.delete()
        return

    if not await check_roulette_active(chat_id):
        await query.answer("Игра уже завершена", show_alert=True)
        return

    if action == "select":
        bet_type = callback_data.bet_type
        if bet_type == "number":
            await query.message.edit_text(
                "Выберите число:",
                reply_markup=build_number_keyboard(),
            )
        else:
            bet_type_names = {
                "red": "🔴 Красное",
                "black": "⚫ Черное",
                "even": "🔢 Четное",
                "odd": "🔢 Нечетное",
                "dozen1": "1️⃣ 1-я дюжина",
                "dozen2": "2️⃣ 2-я дюжина",
                "dozen3": "3️⃣ 3-я дюжина",
            }
            display_name = bet_type_names.get(bet_type, bet_type)
            await query.message.edit_text(
                f"Выберите ставку на {display_name}:",
                reply_markup=build_amount_keyboard(bet_type),
            )
        return

    if action == "select_num":
        number = callback_data.number
        await query.message.edit_text(
            f"Выберите ставку на число {number}:",
            reply_markup=build_amount_keyboard("number", number),
        )
        return

    if action == "back":
        # Go back to bet type selection
        await query.message.edit_text(
            "🎰 <b>Рулетка</b>\n\n"
            "Ставки: 1-100 см\n"
            "Время на ставки: 30 сек\n\n"
            "Выберите тип ставки:",
            reply_markup=build_bet_type_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    if action == "confirm":
        bet_type = callback_data.bet_type
        number = callback_data.number
        amount = callback_data.amount

        if amount < MIN_BET or amount > MAX_BET:
            await query.answer(
                f"Ставка должна быть {MIN_BET}-{MAX_BET} см", show_alert=True
            )
            return

        current_penis = await get_user_penis(user_id, chat_id)
        if current_penis < amount:
            await query.answer(
                f"Недостаточно см! Баланс: {current_penis} см", show_alert=True
            )
            return

        await save_bet(chat_id, user_id, bet_type, number, amount)

        bet_type_names = {
            "red": "🔴 Красное",
            "black": "⚫ Черное",
            "even": "🔢 Четное",
            "odd": "🔢 Нечетное",
            "dozen1": "1️⃣ 1-я дюжина",
            "dozen2": "2️⃣ 2-я дюжина",
            "dozen3": "3️⃣ 3-я дюжина",
            "number": f"число {number}",
        }
        bet_desc = bet_type_names.get(bet_type, bet_type)
        await query.answer(
            f"Ставка {amount} см на {bet_desc} принята!", show_alert=True
        )

        bets = await get_bets(chat_id)
        bet_text = format_bets_text(bets, {})

        await query.message.edit_text(
            f"🎰 <b>Рулетка</b>\n\nСтавки:\n{bet_text}\n\nВыберите тип ставки:",
            reply_markup=build_bet_type_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return
