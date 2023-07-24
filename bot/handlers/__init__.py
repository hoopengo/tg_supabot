"""Import all routers and add them to routers_list."""
from bot.handlers.start import start_router
from bot.handlers.tools import tools_router

routers_list = (
    start_router,
    tools_router,
)

__all__ = [
    "routers_list",
]
