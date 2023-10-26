import asyncio
import logging

import betterlogging as bl
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.chat_action import ChatActionMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import config
from bot.handlers import routers_list
from bot.middlewares.toxity_middleware import ToxityMessageMiddleware
from bot.middlewares.user_exist import UserExistCallbackMiddleware
from bot.services import apshed, broadcaster


async def on_startup(bot: Bot):
    await bot.delete_webhook(drop_pending_updates=True)
    await broadcaster.broadcast(bot, config.ADMIN_IDS, "Бот был запущен")


def setup_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        apshed.minus_penis_cron,
        trigger="cron",
        day_of_week="mon-sun",
        hour=16,
        minute=00,
        kwargs={"bot": bot},
    )
    scheduler.start()


def setup_logging():
    """
    Set up logging configuration for the application.

    This method initializes the logging configuration for the application.
    It sets the log level to INFO and configures a basic colorized log for
    output. The log format includes the filename, line number, log level,
    timestamp, logger name, and log message.

    Returns:
        None

    Example usage:
        setup_logging()
    """
    log_level = logging.INFO
    bl.basic_colorized_config(level=log_level)

    logging.basicConfig(
        level=logging.INFO,
        format="%(filename)s:%(lineno)d #%(levelname)-8s [%(asctime)s] - \
%(name)s - %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting bot")


async def main():
    setup_logging()

    storage = MemoryStorage()

    bot = Bot(token=config.TOKEN.get_secret_value(), parse_mode="HTML")
    setup_scheduler(bot)
    dp = Dispatcher(storage=storage)

    # routers register
    dp.include_routers(*routers_list)

    # middlewares register
    dp.message.outer_middleware(UserExistCallbackMiddleware())
    dp.message.outer_middleware(ToxityMessageMiddleware())
    dp.message.middleware(ChatActionMiddleware())

    await on_startup(bot)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.error("Бот был выключен!")
