"""Import all routers and add them to routers_list."""

from bot.handlers.admin import admin_router
from bot.handlers.ai import ai_router
from bot.handlers.casino import router as casino_router
from bot.handlers.group import group_router
from bot.handlers.mentions import mentions_router
from bot.handlers.owner import owner_router
from bot.handlers.penis import penis_router
from bot.handlers.queues import queue_router
from bot.handlers.sanitary import sanitary_router
from bot.handlers.settings import settings_router
from bot.handlers.start import start_router
from bot.handlers.sticker import sticker_router
from bot.handlers.super_admin import super_admin_router
from bot.handlers.toxicity_control import toxicity_router
from bot.handlers.slots import router as slots_router
from bot.handlers.transfer import transfer_router

routers_list = (
    owner_router,
    super_admin_router,
    admin_router,
    settings_router,
    group_router,
    queue_router,
    start_router,
    sticker_router,
    mentions_router,
    penis_router,
    sanitary_router,
    toxicity_router,
    transfer_router,
    casino_router,
    slots_router,
    ai_router,
)

__all__ = [
    "routers_list",
]
