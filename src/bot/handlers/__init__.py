"""Import all routers and add them to routers_list."""
from bot.handlers.start import start_router
from bot.handlers.sticker import sticker_router
from bot.handlers.mentions import mentions_router
from bot.handlers.penis import penis_router
from bot.handlers.sanitary import sanitary_router

routers_list = (
    start_router,
    sticker_router,
    mentions_router,
    penis_router,
    sanitary_router,
)

__all__ = [
    "routers_list",
]
