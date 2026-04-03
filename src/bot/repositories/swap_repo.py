from datetime import datetime, timedelta

from sqlalchemy import select, update

from bot.db import session
from bot.db.models import SwapRequestModel, SwapStatus


async def create_swap_request(
    queue_id: int,
    from_user_id: int,
    to_user_id: int,
    ttl_minutes: int = 5,
) -> SwapRequestModel:
    async with session() as s:
        now = datetime.utcnow()
        swap = SwapRequestModel(
            queue_id=queue_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            expires_at=now + timedelta(minutes=ttl_minutes),
        )
        s.add(swap)
        await s.flush()
        await s.refresh(swap)
        return swap


async def get_swap_request(swap_id: int) -> SwapRequestModel | None:
    async with session() as s:
        result = await s.scalar(
            select(SwapRequestModel).where(SwapRequestModel.id == swap_id)
        )
        return result


async def get_pending_swap_for_user(
    queue_id: int,
    user_id: int,
) -> SwapRequestModel | None:
    """Find a pending swap request where user_id is the target."""
    async with session() as s:
        result = await s.scalar(
            select(SwapRequestModel).where(
                SwapRequestModel.queue_id == queue_id,
                SwapRequestModel.to_user_id == user_id,
                SwapRequestModel.status == SwapStatus.PENDING,
                SwapRequestModel.expires_at > datetime.utcnow(),
            )
        )
        return result


async def update_swap_status(swap_id: int, status: SwapStatus) -> None:
    async with session() as s:
        await s.execute(
            update(SwapRequestModel)
            .where(SwapRequestModel.id == swap_id)
            .values(status=status)
        )


async def expire_old_swaps() -> int:
    """Mark all expired pending swaps as expired. Returns count."""
    async with session() as s:
        result = await s.execute(
            update(SwapRequestModel)
            .where(
                SwapRequestModel.status == SwapStatus.PENDING,
                SwapRequestModel.expires_at <= datetime.utcnow(),
            )
            .values(status=SwapStatus.EXPIRED)
        )
        return result.rowcount


async def invalidate_queue_swaps(queue_id: int) -> int:
    """Invalidate all pending swaps for a queue (e.g. when queue changes)."""
    async with session() as s:
        result = await s.execute(
            update(SwapRequestModel)
            .where(
                SwapRequestModel.queue_id == queue_id,
                SwapRequestModel.status == SwapStatus.PENDING,
            )
            .values(status=SwapStatus.EXPIRED)
        )
        return result.rowcount
