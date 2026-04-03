import asyncio
import html
import logging
from typing import Sequence

from bot.config import config
from bot.db.models import (
    AdminRole,
    QueueModel,
    QueueMemberModel,
    QueueStatus,
)
from bot.repositories import (
    admin_repo,
    log_repo,
    member_repo,
    queue_repo,
)

logger = logging.getLogger(__name__)

# In-memory lock per queue to prevent concurrent mutations
_queue_locks: dict[int, asyncio.Lock] = {}


def _get_queue_lock(queue_id: int) -> asyncio.Lock:
    if queue_id not in _queue_locks:
        _queue_locks[queue_id] = asyncio.Lock()
    return _queue_locks[queue_id]


# --- Permission checks ---


async def is_super_admin(chat_id: int, user_id: int) -> bool:
    """Check if user is a super admin (bot owner, chat creator, or DB super_admin)."""
    if user_id == config.ADMIN_IDS[0]:
        return True
    admin = await admin_repo.get_admin(chat_id, user_id)
    return admin is not None and admin.role == AdminRole.SUPER_ADMIN


async def is_admin(chat_id: int, user_id: int) -> bool:
    """Check if user is an admin or super admin."""
    if user_id == config.ADMIN_IDS[0]:
        return True
    admin = await admin_repo.get_admin(chat_id, user_id)
    return admin is not None


# --- Queue CRUD ---


async def create_queue(
    chat_id: int,
    title: str,
    created_by: int,
) -> QueueModel:
    queue = await queue_repo.create_queue(chat_id, title, created_by)
    await log_repo.log_action(
        chat_id=chat_id,
        actor_user_id=created_by,
        action="queue_created",
        queue_id=queue.id,
        payload={"title": title},
    )
    logger.info(f"Queue created: id={queue.id} chat={chat_id} title={title}")
    return queue


async def get_queue(queue_id: int) -> QueueModel | None:
    return await queue_repo.get_queue(queue_id)


async def get_queue_by_message(chat_id: int, message_id: int) -> QueueModel | None:
    return await queue_repo.get_queue_by_message(chat_id, message_id)


async def get_active_queues(chat_id: int) -> Sequence[QueueModel]:
    return await queue_repo.get_active_queues(chat_id)


async def update_queue_message_id(queue_id: int, message_id: int) -> None:
    await queue_repo.update_queue_message_id(queue_id, message_id)


# --- Queue operations ---


async def join_queue(
    queue_id: int,
    user_id: int,
    username: str | None,
    first_name: str | None = None,
) -> tuple[bool, str]:
    """Add user to queue. Returns (success, message)."""
    lock = _get_queue_lock(queue_id)
    async with lock:
        queue = await queue_repo.get_queue(queue_id)
        if not queue:
            return False, "Очередь не найдена."
        if queue.status == QueueStatus.CLOSED:
            return False, "Очередь закрыта."

        existing = await member_repo.get_member_by_user(queue_id, user_id)
        if existing:
            max_pos = await member_repo.get_max_position(queue_id)
            if existing.position == max_pos:
                return True, "Ты уже в конце очереди."
            await member_repo.set_position(queue_id, user_id, max_pos)
            await queue_repo.touch_queue(queue_id)
            await log_repo.log_action(
                chat_id=queue.chat_id,
                actor_user_id=user_id,
                action="queue_joined",
                queue_id=queue_id,
            )
            return True, "Перемещён в конец очереди."

        max_pos = await member_repo.get_max_position(queue_id)
        await member_repo.add_member(
            queue_id,
            user_id,
            username,
            max_pos + 1,
            first_name=first_name,
        )
        await queue_repo.touch_queue(queue_id)

        await log_repo.log_action(
            chat_id=queue.chat_id,
            actor_user_id=user_id,
            action="queue_joined",
            queue_id=queue_id,
        )
        return True, "Добавлен в очередь."


async def leave_queue(
    queue_id: int,
    user_id: int,
) -> tuple[bool, str]:
    """Remove user from queue. Returns (success, message)."""
    lock = _get_queue_lock(queue_id)
    async with lock:
        queue = await queue_repo.get_queue(queue_id)
        if not queue:
            return False, "Очередь не найдена."

        removed = await member_repo.remove_member(queue_id, user_id)
        if not removed:
            return False, "Ты не в этой очереди."

        await member_repo.recalculate_positions(queue_id)
        await queue_repo.touch_queue(queue_id)

        await log_repo.log_action(
            chat_id=queue.chat_id,
            actor_user_id=user_id,
            action="queue_left",
            queue_id=queue_id,
        )
        return True, "Удалён из очереди."


async def clear_queue(
    queue_id: int,
    actor_user_id: int,
) -> tuple[bool, str]:
    """Clear all members from queue (admin only)."""
    lock = _get_queue_lock(queue_id)
    async with lock:
        queue = await queue_repo.get_queue(queue_id)
        if not queue:
            return False, "Очередь не найдена."

        count = await member_repo.clear_members(queue_id)
        await queue_repo.touch_queue(queue_id)

        await log_repo.log_action(
            chat_id=queue.chat_id,
            actor_user_id=actor_user_id,
            action="queue_cleared",
            queue_id=queue_id,
            payload={"removed_count": count},
        )
        return True, f"Очередь очищена. Удалено: {count}."


async def open_queue(queue_id: int, actor_user_id: int) -> tuple[bool, str]:
    queue = await queue_repo.get_queue(queue_id)
    if not queue:
        return False, "Очередь не найдена."
    await queue_repo.update_queue_status(queue_id, QueueStatus.OPEN)
    await log_repo.log_action(
        chat_id=queue.chat_id,
        actor_user_id=actor_user_id,
        action="queue_opened",
        queue_id=queue_id,
    )
    return True, "Очередь открыта."


async def close_queue(queue_id: int, actor_user_id: int) -> tuple[bool, str]:
    queue = await queue_repo.get_queue(queue_id)
    if not queue:
        return False, "Очередь не найдена."
    await queue_repo.update_queue_status(queue_id, QueueStatus.CLOSED)
    await log_repo.log_action(
        chat_id=queue.chat_id,
        actor_user_id=actor_user_id,
        action="queue_closed",
        queue_id=queue_id,
    )
    return True, "Очередь закрыта."


async def move_user_up(
    queue_id: int, user_id: int, actor_user_id: int
) -> tuple[bool, str]:
    lock = _get_queue_lock(queue_id)
    async with lock:
        member = await member_repo.get_member_by_user(queue_id, user_id)
        if not member:
            return False, "Пользователь не в очереди."
        if member.position <= 1:
            return False, "Пользователь уже на первой позиции."
        success = await member_repo.set_position(queue_id, user_id, member.position - 1)
        if success:
            await queue_repo.touch_queue(queue_id)
            await log_repo.log_action(
                chat_id=0,
                actor_user_id=actor_user_id,
                action="user_moved_up",
                queue_id=queue_id,
                payload={"user_id": user_id, "new_position": member.position - 1},
            )
        return success, "Пользователь перемещён вверх."


async def move_user_down(
    queue_id: int, user_id: int, actor_user_id: int
) -> tuple[bool, str]:
    lock = _get_queue_lock(queue_id)
    async with lock:
        member = await member_repo.get_member_by_user(queue_id, user_id)
        if not member:
            return False, "Пользователь не в очереди."
        max_pos = await member_repo.get_max_position(queue_id)
        if member.position >= max_pos:
            return False, "Пользователь уже на последней позиции."
        success = await member_repo.set_position(queue_id, user_id, member.position + 1)
        if success:
            await queue_repo.touch_queue(queue_id)
            await log_repo.log_action(
                chat_id=0,
                actor_user_id=actor_user_id,
                action="user_moved_down",
                queue_id=queue_id,
                payload={"user_id": user_id, "new_position": member.position + 1},
            )
        return success, "Пользователь перемещён вниз."


async def set_user_position(
    queue_id: int,
    user_id: int,
    new_position: int,
    actor_user_id: int,
) -> tuple[bool, str]:
    lock = _get_queue_lock(queue_id)
    async with lock:
        member = await member_repo.get_member_by_user(queue_id, user_id)
        if not member:
            return False, "Пользователь не в очереди."
        max_pos = await member_repo.get_max_position(queue_id)
        if new_position < 1 or new_position > max_pos:
            return False, f"Позиция должна быть от 1 до {max_pos}."
        success = await member_repo.set_position(queue_id, user_id, new_position)
        if success:
            await queue_repo.touch_queue(queue_id)
            await log_repo.log_action(
                chat_id=0,
                actor_user_id=actor_user_id,
                action="user_position_set",
                queue_id=queue_id,
                payload={"user_id": user_id, "new_position": new_position},
            )
        return success, f"Позиция установлена: {new_position}."


async def remove_user_from_queue(
    queue_id: int,
    user_id: int,
    actor_user_id: int,
) -> tuple[bool, str]:
    lock = _get_queue_lock(queue_id)
    async with lock:
        queue = await queue_repo.get_queue(queue_id)
        if not queue:
            return False, "Очередь не найдена."

        removed = await member_repo.remove_member(queue_id, user_id)
        if not removed:
            return False, "Пользователь не в очереди."

        await member_repo.recalculate_positions(queue_id)
        await queue_repo.touch_queue(queue_id)

        await log_repo.log_action(
            chat_id=queue.chat_id,
            actor_user_id=actor_user_id,
            action="user_removed_by_admin",
            queue_id=queue_id,
            payload={"removed_user_id": user_id},
        )
        return True, "Пользователь удалён из очереди."


async def get_members(queue_id: int) -> Sequence[QueueMemberModel]:
    return await member_repo.get_active_members(queue_id)


async def get_member_count(queue_id: int) -> int:
    return await member_repo.get_member_count(queue_id)


async def delete_queue(
    queue_id: int,
    actor_user_id: int,
) -> tuple[bool, str]:
    """Delete a queue entirely."""
    queue = await queue_repo.get_queue(queue_id)
    if not queue:
        return False, "Очередь не найдена."
    chat_id = queue.chat_id
    await queue_repo.delete_queue(queue_id)
    await log_repo.log_action(
        chat_id=chat_id,
        actor_user_id=actor_user_id,
        action="queue_deleted",
        queue_id=queue_id,
        payload={"title": queue.title},
    )
    return True, "Очередь удалена."


# --- Rendering ---


async def render_queue(queue_id: int) -> str:
    """Render queue as formatted text for the live message."""
    queue = await queue_repo.get_queue(queue_id)
    if not queue:
        return "Очередь не найдена."

    status_emoji = "🟢" if queue.status == QueueStatus.OPEN else "🔴"
    members = await member_repo.get_active_members(queue_id)

    lines = [
        f"{status_emoji} <b>{html.escape(queue.title)}</b> — {len(members)} чел.",
        "",
    ]

    if members:
        for member in members:
            name = html.escape(
                member.first_name or member.username or str(member.user_id)
            )
            lines.append(f"  {member.position}. {name}")
    else:
        lines.append("Очередь пуста.")

    return "\n".join(lines)
