import logging

from sqlalchemy import select

from bot.db import ChatSettingsModel, session

logger = logging.getLogger(__name__)


async def get_settings(chat_id: int) -> ChatSettingsModel:
    """Get or create chat settings."""
    async with session() as s:
        result = await s.scalar(
            select(ChatSettingsModel).where(ChatSettingsModel.chat_id == chat_id)
        )
        if result:
            return result

        # Create default settings
        settings = ChatSettingsModel(chat_id=chat_id)
        s.add(settings)
        await s.flush()
        return settings


async def toggle_command(chat_id: int, command: str) -> tuple[bool, bool]:
    """Toggle a command on/off. Returns (success, new_state)."""
    attr = ChatSettingsModel.COMMAND_MAP.get(command)
    if not attr:
        return False, False

    async with session() as s:
        result = await s.scalar(
            select(ChatSettingsModel).where(ChatSettingsModel.chat_id == chat_id)
        )
        if not result:
            result = ChatSettingsModel(chat_id=chat_id)
            s.add(result)
            await s.flush()

        current = getattr(result, attr)
        new_value = not current
        setattr(result, attr, new_value)
        return True, new_value


async def is_command_enabled(chat_id: int, command: str) -> bool:
    """Check if a command is enabled for a chat."""
    async with session() as s:
        result = await s.scalar(
            select(ChatSettingsModel).where(ChatSettingsModel.chat_id == chat_id)
        )
        if not result:
            return True  # All commands enabled by default
        return result.is_command_enabled(command)
