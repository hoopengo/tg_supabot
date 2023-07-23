from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.config import config


class AdminFilter(BaseFilter):
    async def __call__(self, obj: Message) -> bool:
        return obj.from_user.id in config.ADMIN_IDS
