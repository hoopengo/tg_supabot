import asyncio
import json
import random
import time

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from bot.db import UserModel, session
from bot.handlers.casino import get_user_penis, update_penis_safe
from bot.keyboards.slots_kb import (
    BLACK_NUMBERS,
    RED_NUMBERS,
    SPIN_DURATION,
    SlotsCallback,
    build_amount_keyboard,
    build_bet_type_keyboard,
    build_cancel_keyboard,
    build_number_keyboard,
)
from bot.redis import message_cache

router = Router()

REDIS_ACTIVE_KEY = "slots_active"
REDIS_BETS_KEY = "slots_bets"
REDIS_LOCK_KEY = "slots_lock"
REDIS_LAST_BET_KEY = "slots_last_bet"

MIN_BET = 1
MAX_BET = 100


def get_active_key(chat_id: int) -> str:
    return f"{REDIS_ACTIVE_KEY}:{chat_id}"


def get_bets_key(chat_id: int) -> str:
    return f"{REDIS_BETS_KEY}:{chat_id}"


def get_lock_key(chat_id: int) -> str:
    return f"{REDIS_LOCK_KEY}:{chat_id}"


def get_last_bet_key(chat_id: int) -> str:
    return f"{REDIS_LAST_BET_KEY}:{chat_id}"


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

        # Update last bet timestamp
        last_bet_key = get_last_bet_key(chat_id)
        await message_cache.setex(last_bet_key, SPIN_DURATION + 60, str(time.time()))

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


async def clear_last_bet(chat_id: int) -> None:
    key = get_last_bet_key(chat_id)
    await message_cache.delete(key)


def spin_roulette() -> int:
    return random.randint(0, 36)


def get_winner_type(number: int) -> str:
    if number == 0:
        return "🟢 Зеро"
    if number in RED_NUMBERS:
        return "🔴 Красное"
    return "⚫ Черное"


async def get_user_names(chat_id: int, user_ids: list[int]) -> dict[int, str]:
    """Get display names for multiple users."""
    names = {}
    async with session() as s:
        results = await s.scalars(
            select(UserModel).where(
                UserModel.chat_id == chat_id, UserModel.user_id.in_(user_ids)
            )
        )
        for user in results:
            if user.username:
                names[user.user_id] = f"@{user.username}"
            elif user.first_name:
                names[user.user_id] = user.first_name
            else:
                names[user.user_id] = f'<a href="tg://user?id={user.user_id}">User</a>'

    # Add missing users with default name
    for uid in user_ids:
        if uid not in names:
            names[uid] = f'<a href="tg://user?id={uid}">User</a>'
    return names


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


def format_bets_text(bets: list, user_names: dict) -> str:
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
        user_name = user_names.get(bet["user_id"], f"User-{bet['user_id']}")
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
    await clear_last_bet(chat_id)

    # Run roulette finish in background to not block the handler
    asyncio.create_task(finish_roulette(message.bot, chat_id, msg.message_id))


async def finish_roulette(bot, chat_id: int, message_id: int) -> None:
    # Wait for betting period (either SPIN_DURATION from start or 15s from last bet)
    while True:
        await asyncio.sleep(1)

        if not await check_roulette_active(chat_id):
            return

        # Check if last bet was more than SPIN_DURATION ago
        last_bet_key = get_last_bet_key(chat_id)
        last_bet_time = await message_cache.get(last_bet_key)

        if last_bet_time:
            last_bet_ts = float(last_bet_time)
            current_time = time.time()
            elapsed = current_time - last_bet_ts
            if elapsed >= SPIN_DURATION:
                break
        else:
            # No bets yet, use original timer
            break

    winning_number = spin_roulette()
    winner_type = get_winner_type(winning_number)

    bets = await get_bets(chat_id)
    await clear_roulette_active(chat_id)
    await clear_bets(chat_id)
    await clear_last_bet(chat_id)

    # Get user names
    user_ids = list(set(bet["user_id"] for bet in bets))
    user_names = await get_user_names(chat_id, user_ids)

    winners = []
    losers = []

    for bet in bets:
        payout = calculate_payout(
            bet["bet_type"], bet["number"], winning_number, bet["amount"]
        )
        user_name = user_names.get(bet["user_id"], f"User-{bet['user_id']}")
        if payout > 0:
            _, actual_win, _ = await update_penis_safe(
                bet["user_id"], chat_id, payout, bet["amount"]
            )
            winners.append(f"• {user_name}: +{actual_win} см")
        else:
            await update_penis_safe(
                bet["user_id"], chat_id, -bet["amount"], bet["amount"]
            )
            losers.append(f"• {user_name}: -{bet['amount']} см")

    result_text = f"🎰 <b>Рулетка</b>\n\nВыпало: {winning_number} ({winner_type})\n\n"

    if winners:
        result_text += "🎉 Победители:\n" + "\n".join(winners) + "\n\n"
    if losers:
        result_text += "💀 Проигравшие:\n" + "\n".join(losers)
    if not winners and not losers:
        result_text += "Ставок не было"

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
    chat_id = message.chat.id

    # Check for force restart
    parts = message.text.split()
    force = len(parts) > 1 and parts[1] == "force"

    if await check_roulette_active(chat_id):
        if force:
            await clear_roulette_active(chat_id)
            await clear_bets(chat_id)
            await clear_last_bet(chat_id)
        else:
            await message.answer(
                "Рулетка уже крутится! Используй /slots force для принудительного перезапуска.",
                parse_mode=ParseMode.HTML,
            )
            return

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
            try:
                await query.message.edit_text(
                    "Выберите число:",
                    reply_markup=build_number_keyboard(),
                )
            except Exception:
                pass
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
            try:
                await query.message.edit_text(
                    f"Выберите ставку на {display_name}:",
                    reply_markup=build_amount_keyboard(bet_type),
                )
            except Exception:
                pass
        return

    if action == "select_num":
        number = callback_data.number
        try:
            await query.message.edit_text(
                f"Выберите ставку на число {number}:",
                reply_markup=build_amount_keyboard("number", number),
            )
        except Exception:
            pass
        return

    if action == "back":
        # Go back to bet type selection
        try:
            await query.message.edit_text(
                "🎰 <b>Рулетка</b>\n\n"
                "Ставки: 1-100 см\n"
                "Время на ставки: 30 сек\n\n"
                "Выберите тип ставки:",
                reply_markup=build_bet_type_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass
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
        # Get user names
        user_ids = list(set(bet["user_id"] for bet in bets))
        user_ids.append(user_id)  # Include current user
        user_names = await get_user_names(chat_id, user_ids)
        bet_text = format_bets_text(bets, user_names)

        try:
            await query.message.edit_text(
                f"🎰 <b>Рулетка</b>\n\nСтавки:\n{bet_text}\n\nВыберите тип ставки:",
                reply_markup=build_bet_type_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass
        return
