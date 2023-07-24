"""Import all routers and add them to routers_list."""
from bot.handlers.start import start_router
from bot.handlers.sticker import sticker_router

routers_list = (
    start_router,
    sticker_router,
)

__all__ = [
    "routers_list",
]
