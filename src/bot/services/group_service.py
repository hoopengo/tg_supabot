import asyncio
import html
import logging
from typing import Sequence

from aiogram import Bot

from bot.db.models import QueueGroupModel
from bot.repositories import group_repo, member_repo, queue_repo

logger = logging.getLogger(__name__)

# Debounce: track pending update tasks per group_id
_pending_updates: dict[int, asyncio.Task] = {}

DEBOUNCE_SECONDS = 2.0


async def create_group(
    chat_id: int,
    queue_ids: list[int],
    created_by: int,
) -> QueueGroupModel:
    """Create a new queue group with the given queues."""
    # Build title from queue names
    titles = []
    for qid in queue_ids:
        q = await queue_repo.get_queue(qid)
        if q:
            titles.append(q.title)
    title = " + ".join(titles) if titles else "Группа"

    group = await group_repo.create_group(chat_id, created_by, title=title)
    for pos, qid in enumerate(queue_ids, start=1):
        await group_repo.add_queue_to_group(group.id, qid, pos)

    return group


async def render_group(group_id: int) -> str:
    """Render group as formatted text with round-robin interleaving."""
    group = await group_repo.get_group(group_id)
    if not group:
        return "Группа не найдена."

    queue_ids = await group_repo.get_group_queue_ids(group_id)
    if not queue_ids:
        return f"📋 <b>{html.escape(group.title or 'Группа')}</b>\n\nОчереди отсутствуют."

    # Collect members per queue with queue titles
    queue_members: list[list[tuple[str, str]]] = []  # [(name, queue_title), ...]
    for qid in queue_ids:
        q = await queue_repo.get_queue(qid)
        if not q:
            continue
        members = await member_repo.get_active_members(qid)
        q_title = html.escape(q.title)
        member_list = []
        for m in members:
            name = html.escape(
                m.first_name or m.username or str(m.user_id)
            )
            member_list.append((name, q_title))
        queue_members.append(member_list)

    if not queue_members:
        return f"📋 <b>{html.escape(group.title or 'Группа')}</b>\n\nОчереди пусты."

    # Round-robin interleave
    interleaved: list[tuple[str, str]] = []
    max_len = max(len(members) for members in queue_members)
    for i in range(max_len):
        for members in queue_members:
            if i < len(members):
                interleaved.append(members[i])

    total_count = len(interleaved)
    lines = [
        f"📋 <b>{html.escape(group.title or 'Группа')}</b> — {total_count} чел.",
        "",
    ]

    if interleaved:
        for pos, (name, q_title) in enumerate(interleaved, start=1):
            lines.append(f"  {pos}. {name} <i>({q_title})</i>")
    else:
        lines.append("Очереди пусты.")

    return "\n".join(lines)


async def get_groups_containing_queue(queue_id: int) -> Sequence[QueueGroupModel]:
    """Get all groups that contain a given queue."""
    return await group_repo.get_groups_by_queue(queue_id)


async def _do_update_group_message(bot: Bot, group_id: int) -> None:
    """Actually edit the group message in Telegram."""
    group = await group_repo.get_group(group_id)
    if not group or not group.message_id:
        return

    text = await render_group(group_id)
    try:
        await bot.edit_message_text(
            text,
            chat_id=group.chat_id,
            message_id=group.message_id,
            parse_mode="HTML",
        )
    except Exception as e:
        if "message is not modified" not in str(e):
            logger.warning(f"Failed to edit group message {group_id}: {e}")


async def _debounced_update(bot: Bot, group_id: int) -> None:
    """Wait for debounce period, then update."""
    await asyncio.sleep(DEBOUNCE_SECONDS)
    _pending_updates.pop(group_id, None)
    await _do_update_group_message(bot, group_id)


def schedule_group_update(bot: Bot, group_id: int) -> None:
    """Schedule a debounced update for a group message.

    If an update is already pending for this group, the existing task
    is cancelled and a new one is scheduled (resets the debounce timer).
    """
    existing = _pending_updates.get(group_id)
    if existing and not existing.done():
        existing.cancel()

    task = asyncio.create_task(_debounced_update(bot, group_id))
    _pending_updates[group_id] = task


async def on_queue_updated(bot: Bot, queue_id: int) -> None:
    """Called when a queue's members change. Updates all groups containing it."""
    groups = await get_groups_containing_queue(queue_id)
    for group in groups:
        schedule_group_update(bot, group.id)


async def on_queue_deleted(bot: Bot, queue_id: int) -> None:
    """Called when a queue is deleted. Removes it from groups, cleans up."""
    groups = await get_groups_containing_queue(queue_id)
    for group in groups:
        await group_repo.remove_queue_from_group(group.id, queue_id)
        remaining = await group_repo.get_group_member_count(group.id)
        if remaining < 2:
            # Group no longer meaningful — delete it and its message
            if group.message_id:
                try:
                    await bot.delete_message(group.chat_id, group.message_id)
                except Exception:
                    pass
            await group_repo.delete_group(group.id)
        else:
            # Update title and message
            queue_ids = await group_repo.get_group_queue_ids(group.id)
            titles = []
            for qid in queue_ids:
                q = await queue_repo.get_queue(qid)
                if q:
                    titles.append(q.title)
            new_title = " + ".join(titles) if titles else "Группа"
            await group_repo.update_group_title(group.id, new_title)
            # Directly update the message (no debounce needed for deletion)
            await _do_update_group_message(bot, group.id)
