import random

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from bot.db import UserModel, session
from bot.redis import message_cache

router = Router()

MIN_BET = 1
MAX_BET = 50
MAX_WIN_MULTIPLIER = 5
MIN_BALANCE = 1
COOLDOWN_SECONDS = 30

REDIS_KEY_PREFIX = "casino_cooldown"

SYMBOLS = ["🍒", "🍋", "🍊", "🍇", "💎", "🔔"]
SYMBOL_PAYOUTS = {
    "🍒": 1,
    "🍋": 1,
    "🍊": 2,
    "🍇": 2,
    "💎": 2,
    "🔔": 2,
}


def get_cooldown_key(user_id: int, chat_id: int) -> str:
    return f"{REDIS_KEY_PREFIX}:{chat_id}:{user_id}"


async def check_cooldown(user_id: int, chat_id: int) -> bool:
    key = get_cooldown_key(user_id, chat_id)
    return await message_cache.exists(key)


async def set_cooldown(user_id: int, chat_id: int) -> None:
    key = get_cooldown_key(user_id, chat_id)
    await message_cache.setex(key, COOLDOWN_SECONDS, "1")


async def get_user_penis(user_id: int, chat_id: int) -> int:
    async with session() as s:
        result = await s.scalar(
            select(UserModel).where(
                UserModel.user_id == user_id, UserModel.chat_id == chat_id
            )
        )
        if result:
            return result.penis_size
        return 0


async def is_casino_lucky(user_id: int, chat_id: int) -> bool:
    async with session() as s:
        result = await s.scalar(
            select(UserModel).where(
                UserModel.user_id == user_id, UserModel.chat_id == chat_id
            )
        )
        if result:
            return result.casino_lucky
        return False


async def update_penis_safe(
    user_id: int, chat_id: int, change: int, bet: int = 0
) -> tuple[bool, int, str]:
    async with session() as s:
        result = await s.scalar(
            select(UserModel).where(
                UserModel.user_id == user_id, UserModel.chat_id == chat_id
            )
        )
        if not result:
            return False, 0, "Пользователь не найден"

        current = result.penis_size

        if change < 0:
            new_size = current + change
            if new_size < MIN_BALANCE:
                result.penis_size = MIN_BALANCE
                lost = current - MIN_BALANCE
                await s.commit()
                return True, lost, f"Остановился на минимуме {MIN_BALANCE} см"
            result.penis_size = new_size
            await s.commit()
            return True, abs(change), f"Проиграл {abs(change)} см"
        else:
            max_win = bet * MAX_WIN_MULTIPLIER
            win = min(change, max_win)
            result.penis_size = current + win
            await s.commit()
            return True, win, f"Выиграл {win} см"


@router.message(Command("casino_top", ignore_case=True), F.chat.type != "private")
async def casino_top(message: Message):
    chat_id = message.chat.id

    async with session() as s:
        result = (
            await s.scalars(
                select(UserModel)
                .where(UserModel.chat_id == chat_id, UserModel.penis_size > 0)
                .order_by(UserModel.penis_size.desc())
                .limit(10)
            )
        ).all()

    if not result:
        await message.answer("Нет игроков в казино", parse_mode=ParseMode.HTML)
        return

    lines = ["<b>🎰 Топ казино</b>\n"]
    for i, user in enumerate(result, 1):
        lines.append(
            f"{i}. {user.first_name or user.username or user.user_id} — {user.penis_size} см"
        )

    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)


@router.message(Command("casino", ignore_case=True), F.chat.type != "private")
async def play_casino(message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if await check_cooldown(user_id, chat_id):
        await message.answer(
            "Подожди немного, куколд еще не вышел", parse_mode=ParseMode.HTML
        )
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "<b>🎰 Казино Писюка</b>\n\n"
            "Ставка: 1-50 см\n"
            f"Макс. выигрыш: {MAX_WIN_MULTIPLIER}x от ставки\n"
            f"Мин. баланс: {MIN_BALANCE} см\n"
            f"Кулдаун: {COOLDOWN_SECONDS} сек\n\n"
            "<code>/casino [ставка]</code> - сыграть\n"
            "<code>/casino top</code> - топ игроков",
            parse_mode=ParseMode.HTML,
        )
        return

    if parts[1] == "top":
        await casino_top(message)
        return

    try:
        bet = int(parts[1])
    except ValueError:
        await message.answer("Ставка должна быть числом", parse_mode=ParseMode.HTML)
        return

    if bet < MIN_BET:
        await message.answer(
            f"Минимальная ставка: {MIN_BET} см", parse_mode=ParseMode.HTML
        )
        return

    if bet > MAX_BET:
        await message.answer(
            f"Максимальная ставка: {MAX_BET} см", parse_mode=ParseMode.HTML
        )
        return

    current_penis = await get_user_penis(user_id, chat_id)
    if current_penis < bet:
        await message.answer(
            f"У тебя недостаточно см. У тебя: {current_penis} см",
            parse_mode=ParseMode.HTML,
        )
        return

    if current_penis < MIN_BET:
        await message.answer(
            f"У тебя слишком мало см для игры. Минимум: {MIN_BALANCE} см",
            parse_mode=ParseMode.HTML,
        )
        return

    await set_cooldown(user_id, chat_id)

    lucky = await is_casino_lucky(user_id, chat_id)

    slots = [random.choice(SYMBOLS) for _ in range(3)]

    if lucky:
        # Заменяем на джекпот
        symbol = random.choice(SYMBOLS)
        slots = [symbol, symbol, symbol]

    unique = set(slots)
    len_unique = len(unique)

    if len_unique == 1:
        symbol = slots[0]
        multiplier = SYMBOL_PAYOUTS[symbol] * 2
        # 5% шанс на x5
        if random.random() < 0.05:
            multiplier = 5
        win = bet * multiplier
        _, actual_win, msg = await update_penis_safe(user_id, chat_id, win, bet)
        if multiplier == 5:
            result_text = f"🎉 СУПЕР ДЖЕКПОТ! {slots[0]}{slots[0]}{slots[0]}\n{msg}"
        else:
            result_text = f"🎉 Джекпот! {slots[0]}{slots[0]}{slots[0]}\n{msg}"
    elif len_unique == 2:
        symbol = list(unique - set(slots[:1]))[0] if slots[0] == slots[1] else slots[0]
        if slots.count(slots[0]) == 2:
            symbol = slots[0]
        else:
            symbol = slots[2]
        if symbol in SYMBOL_PAYOUTS:
            multiplier = SYMBOL_PAYOUTS[symbol]
            win = bet * multiplier
            _, actual_win, msg = await update_penis_safe(user_id, chat_id, win, bet)
            result_text = f"🎯 Два совпадения! {symbol}{symbol}\n{msg}"
        else:
            await update_penis_safe(user_id, chat_id, -bet, bet)
            result_text = f"😢 Два совпадения, но не выигрышные\nПроиграл {bet} см"
    else:
        if slots[0] == slots[1] or slots[1] == slots[2]:
            symbol = slots[1]
            if symbol in SYMBOL_PAYOUTS:
                win = bet * SYMBOL_PAYOUTS[symbol]
                _, actual_win, msg = await update_penis_safe(user_id, chat_id, win, bet)
                result_text = f"🎵 {symbol}!\n{msg}"
            else:
                await update_penis_safe(user_id, chat_id, -bet, bet)
                result_text = f"😢 Без выигрыша\nПроиграл {bet} см"
        else:
            await update_penis_safe(user_id, chat_id, -bet, bet)
            result_text = f"😢 {slots[0]}{slots[1]}{slots[2]}\nПроиграл {bet} см"

    new_balance = await get_user_penis(user_id, chat_id)
    result_text += f"\n💰 Баланс: {new_balance} см"

    await message.answer(result_text, parse_mode=ParseMode.HTML)
