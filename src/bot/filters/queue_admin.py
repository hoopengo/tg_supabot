from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message

from bot.services.admin_service import is_admin, is_super_admin


class IsAdminFilter(Filter):
    """Filter that checks if the user is an admin in the current chat."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        chat_id = event.chat.id if isinstance(event, Message) else event.message.chat.id
        user_id = event.from_user.id
        return await is_admin(chat_id, user_id)


class IsSuperAdminFilter(Filter):
    """Filter that checks if the user is a super admin in the current chat."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        chat_id = event.chat.id if isinstance(event, Message) else event.message.chat.id
        user_id = event.from_user.id
        return await is_super_admin(chat_id, user_id)


class IsGroupChatFilter(Filter):
    """Filter that checks if the message is from a group/supergroup."""

    async def __call__(self, message: Message) -> bool:
        return message.chat.type in ("group", "supergroup")
