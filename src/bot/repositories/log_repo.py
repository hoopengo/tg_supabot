import json
from typing import Any

from bot.db import session
from bot.db.models import AuditLogModel


async def log_action(
    chat_id: int,
    actor_user_id: int,
    action: str,
    queue_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    async with session() as s:
        entry = AuditLogModel(
            chat_id=chat_id,
            queue_id=queue_id,
            actor_user_id=actor_user_id,
            action=action,
            payload=json.dumps(payload) if payload else None,
        )
        s.add(entry)
