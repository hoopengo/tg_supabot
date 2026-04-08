import asyncio
import logging

import betterlogging as bl
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiogram.utils.chat_action import ChatActionMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import config
from bot.handlers import routers_list
from bot.middlewares.flood_control import FloodControlMiddleware
from bot.middlewares.toxity_middleware import ToxityMessageMiddleware
from bot.middlewares.user_exist import UserExistCallbackMiddleware
from bot.services import apshed, broadcaster

COMMANDS = [
    BotCommand(command="start", description="Начало работы"),
    BotCommand(command="dick", description="Узнать размер"),
    BotCommand(command="top_dick", description="Топ размеров"),
    BotCommand(command="stats", description="Статистика"),
    BotCommand(command="sanitary", description="Проверка санитарной зоны"),
    BotCommand(command="all", description="Упомянуть всех"),
    BotCommand(command="top_toxic", description="Топ токсичных"),
    BotCommand(command="create_queue", description="Создать очередь"),
    BotCommand(command="queues", description="Список очередей"),
    BotCommand(command="switch", description="Поменяться местами"),
    BotCommand(command="admin", description="Панель администратора"),
    BotCommand(command="superadmin", description="Панель супер-админа"),
    BotCommand(command="add_admin", description="Добавить админа"),
    BotCommand(command="remove_admin", description="Удалить админа"),
]


async def on_startup(bot: Bot):
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands(COMMANDS)
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

    bot = Bot(
        token=config.TOKEN.get_secret_value(),
        default_bot_properties=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    setup_scheduler(bot)
    dp = Dispatcher(storage=storage)

    # routers register
    dp.include_routers(*routers_list)

    # middlewares register
    dp.message.outer_middleware(FloodControlMiddleware())
    dp.message.outer_middleware(UserExistCallbackMiddleware())
    dp.message.outer_middleware(ToxityMessageMiddleware())
    dp.message.middleware(ChatActionMiddleware())

    await on_startup(bot)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt, SystemExit:
        logging.error("Бот был выключен!")
