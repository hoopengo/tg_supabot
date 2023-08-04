"""Import all routers and add them to routers_list."""
from bot.handlers.settings import settings_router
from bot.handlers.start import start_router
from bot.handlers.sticker import sticker_router

routers_list = (
    start_router,
    sticker_router,
    settings_router,
)

__all__ = [
    "routers_list",
]
