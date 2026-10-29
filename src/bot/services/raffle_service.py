import asyncio
import html
import logging
import random
import re
from datetime import datetime, timedelta

from aiogram import Bot

from bot.db.models import RaffleModel, RaffleParticipantModel, RaffleStatus
from bot.keyboards.raffle_kb import raffle_keyboard
from bot.repositories import raffle_repo

logger = logging.getLogger(__name__)

# In-memory lock per raffle to prevent concurrent mutations
_raffle_locks: dict[int, asyncio.Lock] = {}


def _get_raffle_lock(raffle_id: int) -> asyncio.Lock:
    if raffle_id not in _raffle_locks:
        _raffle_locks[raffle_id] = asyncio.Lock()
    return _raffle_locks[raffle_id]


# --- Duration parsing ---


_DURATION_RE = re.compile(r"(\d+)\s*(d|д|h|ч|m|м|s|с)", re.IGNORECASE)

_UNIT_SECONDS = {
    "d": 86400, "д": 86400,
    "h": 3600, "ч": 3600,
    "m": 60, "м": 60,
    "s": 1, "с": 1,
}


def parse_duration(raw: str) -> timedelta | None:
    """Parse '30m', '1h', '1ч30м', '2d' into timedelta. Bare number = minutes."""
    raw = raw.strip().lower()
    if not raw:
        return None
    if raw.isdigit():
        return timedelta(minutes=int(raw))
    total = 0
    matched = False
    for value, unit in _DURATION_RE.findall(raw):
        matched = True
        total += int(value) * _UNIT_SECONDS[unit[0].lower()]
    if not matched:
        return None
    if total <= 0:
        return None
    return timedelta(seconds=total)


# --- Raffle CRUD ---


async def create_raffle(
    chat_id: int,
    topic_count: int,
    created_by: int,
    duration: timedelta,
) -> RaffleModel:
    raffle = await raffle_repo.create_raffle(
        chat_id=chat_id,
        topic_count=topic_count,
        created_by=created_by,
        ends_at=datetime.utcnow() + duration,
    )
    logger.info(
        f"Raffle created: id={raffle.id} chat={chat_id} topics={topic_count}"
    )
    return raffle


async def get_raffle(raffle_id: int) -> RaffleModel | None:
    return await raffle_repo.get_raffle(raffle_id)


async def get_active_raffle(chat_id: int) -> RaffleModel | None:
    return await raffle_repo.get_active_raffle(chat_id)


async def update_raffle_message_id(raffle_id: int, message_id: int) -> None:
    await raffle_repo.update_raffle_message_id(raffle_id, message_id)


async def cancel_raffle(raffle_id: int, actor_user_id: int) -> tuple[bool, str]:
    raffle = await raffle_repo.get_raffle(raffle_id)
    if not raffle:
        return False, "Розыгрыш не найден."
    if raffle.status != RaffleStatus.ACTIVE:
        return False, "Розыгрыш уже завершён."
    await raffle_repo.update_raffle_status(raffle_id, RaffleStatus.CANCELLED)
    logger.info(f"Raffle cancelled: id={raffle_id} by={actor_user_id}")
    return True, "Розыгрыш отменён."


# --- Participation ---


async def toggle_participation(
    raffle_id: int,
    user_id: int,
    username: str | None,
    first_name: str | None,
) -> tuple[bool, bool, str]:
    """Toggle user participation. Returns (success, now_participating, message)."""
    lock = _get_raffle_lock(raffle_id)
    async with lock:
        raffle = await raffle_repo.get_raffle(raffle_id)
        if not raffle:
            return False, False, "Розыгрыш не найден."
        if raffle.status != RaffleStatus.ACTIVE:
            return False, False, "Розыгрыш уже завершён."

        existing = await raffle_repo.get_participant(raffle_id, user_id)
        if existing:
            await raffle_repo.remove_participant(raffle_id, user_id)
            return True, False, "Ты больше не участвуешь."

        await raffle_repo.add_participant(raffle_id, user_id, username, first_name)
        return True, True, "Ты участвуешь! 🎲"


async def get_participants(raffle_id: int) -> list[RaffleParticipantModel]:
    return list(await raffle_repo.get_participants(raffle_id))


# --- Rendering ---


def _display_name(participant: RaffleParticipantModel) -> str:
    return (
        participant.first_name
        or participant.username
        or str(participant.user_id)
    )


async def render_raffle(raffle: RaffleModel) -> str:
    """Render the live raffle message text."""
    participants = await raffle_repo.get_participants(raffle.id)
    lines = [
        "🎲 <b>Розыгрыш тем для докладов</b>",
        f"Тем: <b>{raffle.topic_count}</b>",
        "",
        "Нажми «Участвовать» — по окончании темы распределятся случайно и честно.",
        "",
        f"<b>Участники ({len(participants)}):</b>",
    ]
    if participants:
        for i, participant in enumerate(participants, start=1):
            name = html.escape(_display_name(participant))
            if participant.topic_number:
                lines.append(f"  {i}. {name} — тема {participant.topic_number}")
            else:
                lines.append(f"  {i}. {name}")
    else:
        lines.append("  Пока никто. Будь первым!")

    ends_local = raffle.ends_at + timedelta(hours=3)  # Europe/Moscow
    lines.append("")
    lines.append(f"⏳ Итоги: <b>{ends_local.strftime('%d.%m %H:%M')}</b> МСК")
    return "\n".join(lines)


async def refresh_raffle_message(bot: Bot, raffle: RaffleModel) -> None:
    """Edit the live raffle message with the current state."""
    if not raffle.message_id:
        return
    text = await render_raffle(raffle)
    try:
        await bot.edit_message_text(
            text,
            chat_id=raffle.chat_id,
            message_id=raffle.message_id,
            reply_markup=raffle_keyboard(raffle.id, active=raffle.status == RaffleStatus.ACTIVE),
        )
    except Exception as e:
        if "message is not modified" not in str(e):
            logger.warning(f"Failed to edit raffle message: {e}")


# --- Finishing ---


async def finish_raffle(bot: Bot, raffle_id: int) -> None:
    """Assign topics randomly and announce the result."""
    lock = _get_raffle_lock(raffle_id)
    async with lock:
        raffle = await raffle_repo.get_raffle(raffle_id)
        if not raffle or raffle.status != RaffleStatus.ACTIVE:
            return

        participants = await raffle_repo.get_participants(raffle_id)
        assigned = random.sample(
            range(1, raffle.topic_count + 1), min(len(participants), raffle.topic_count)
        )
        for participant, topic in zip(participants, assigned):
            await raffle_repo.assign_topic_number(participant.id, topic)
        await raffle_repo.update_raffle_status(raffle_id, RaffleStatus.FINISHED)

    raffle = await raffle_repo.get_raffle(raffle_id)
    if not raffle:
        return

    participants = await raffle_repo.get_participants(raffle_id)
    if participants:
        lines = ["🎉 <b>Итоги розыгрыша</b>", ""]
        for participant in participants:
            name = html.escape(_display_name(participant))
            mention = (
                f'<a href="tg://user?id={participant.user_id}">{name}</a>'
            )
            lines.append(f"  📌 Тема {participant.topic_number} — {mention}")
        lines.append("")
        lines.append("Удачных докладов!")
        result_text = "\n".join(lines)
    else:
        result_text = "🎲 Розыгрыш завершён. Участников не было."

    if raffle.message_id:
        try:
            await bot.edit_message_text(
                result_text,
                chat_id=raffle.chat_id,
                message_id=raffle.message_id,
            )
        except Exception as e:
            logger.warning(f"Failed to edit raffle result message: {e}")
            try:
                await bot.send_message(raffle.chat_id, result_text)
            except Exception as e2:
                logger.error(f"Failed to send raffle result: {e2}")


async def check_due_raffles(bot: Bot) -> None:
    """Finish every active raffle whose deadline has passed. Run periodically."""
    due = await raffle_repo.get_due_raffles(datetime.utcnow())
    for raffle in due:
        try:
            await finish_raffle(bot, raffle.id)
        except Exception as e:
            logger.error(f"Failed to finish raffle {raffle.id}: {e}")
