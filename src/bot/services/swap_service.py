import logging
from datetime import datetime

from bot.db.models import SwapRequestModel, SwapStatus
from bot.repositories import (
    log_repo,
    member_repo,
    queue_repo,
    swap_repo,
)
from bot.services.queue_service import _get_queue_lock

logger = logging.getLogger(__name__)

SWAP_TTL_MINUTES = 5


async def create_swap_request(
    queue_id: int,
    from_user_id: int,
    to_user_id: int,
) -> tuple[bool, str, SwapRequestModel | None]:
    """Create a swap request. Returns (success, message, swap_request)."""
    if from_user_id == to_user_id:
        return False, "Нельзя поменяться местами с собой.", None

    queue = await queue_repo.get_queue(queue_id)
    if not queue:
        return False, "Очередь не найдена.", None

    from_member = await member_repo.get_member_by_user(queue_id, from_user_id)
    if not from_member:
        return False, "Ты не в этой очереди.", None

    to_member = await member_repo.get_member_by_user(queue_id, to_user_id)
    if not to_member:
        return False, "Целевой пользователь не в очереди.", None

    # Check for existing pending swap from this user
    existing = await swap_repo.get_pending_swap_for_user(queue_id, to_user_id)
    if existing and existing.from_user_id == from_user_id:
        return False, "Уже есть активный запрос на обмен.", None

    swap = await swap_repo.create_swap_request(
        queue_id=queue_id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        ttl_minutes=SWAP_TTL_MINUTES,
    )

    await log_repo.log_action(
        chat_id=queue.chat_id,
        actor_user_id=from_user_id,
        action="swap_requested",
        queue_id=queue_id,
        payload={"from": from_user_id, "to": to_user_id, "swap_id": swap.id},
    )

    return True, "Запрос на обмен создан.", swap


async def approve_swap(
    swap_id: int,
    approver_user_id: int,
) -> tuple[bool, str]:
    """Approve a swap request. The target user must be the approver."""
    swap = await swap_repo.get_swap_request(swap_id)
    if not swap:
        return False, "Запрос не найден."

    if swap.to_user_id != approver_user_id:
        return False, "Ты не можешь подтвердить этот запрос."

    if swap.status != SwapStatus.PENDING:
        return False, "Запрос уже обработан."

    if swap.expires_at <= datetime.utcnow():
        await swap_repo.update_swap_status(swap_id, SwapStatus.EXPIRED)
        return False, "Запрос истёк."

    queue = await queue_repo.get_queue(swap.queue_id)
    if not queue:
        return False, "Очередь не найдена."

    lock = _get_queue_lock(swap.queue_id)
    async with lock:
        # Re-check members are still in the queue
        from_member = await member_repo.get_member_by_user(
            swap.queue_id, swap.from_user_id
        )
        to_member = await member_repo.get_member_by_user(swap.queue_id, swap.to_user_id)

        if not from_member or not to_member:
            await swap_repo.update_swap_status(swap_id, SwapStatus.REJECTED)
            return False, "Один из пользователей больше не в очереди."

        success = await member_repo.swap_positions(
            swap.queue_id,
            swap.from_user_id,
            swap.to_user_id,
        )

        if success:
            await swap_repo.update_swap_status(swap_id, SwapStatus.APPROVED)
            await queue_repo.touch_queue(swap.queue_id)
            await log_repo.log_action(
                chat_id=queue.chat_id,
                actor_user_id=approver_user_id,
                action="swap_approved",
                queue_id=swap.queue_id,
                payload={"swap_id": swap_id},
            )
            return True, "Места успешно поменяны!"
        else:
            await swap_repo.update_swap_status(swap_id, SwapStatus.REJECTED)
            return False, "Не удалось поменяться местами."


async def reject_swap(
    swap_id: int,
    rejector_user_id: int,
) -> tuple[bool, str]:
    """Reject a swap request."""
    swap = await swap_repo.get_swap_request(swap_id)
    if not swap:
        return False, "Запрос не найден."

    if swap.to_user_id != rejector_user_id and swap.from_user_id != rejector_user_id:
        return False, "Ты не можешь отклонить этот запрос."

    if swap.status != SwapStatus.PENDING:
        return False, "Запрос уже обработан."

    await swap_repo.update_swap_status(swap_id, SwapStatus.REJECTED)

    queue = await queue_repo.get_queue(swap.queue_id)
    if queue:
        await log_repo.log_action(
            chat_id=queue.chat_id,
            actor_user_id=rejector_user_id,
            action="swap_rejected",
            queue_id=swap.queue_id,
            payload={"swap_id": swap_id},
        )

    return True, "Запрос отклонён."
