import logging

from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from bot.filters.queue_admin import IsGroupChatFilter
from bot.repositories import group_repo
from bot.services import admin_service, queue_service
from bot.services import group_service
from bot.services.auto_delete import delete_command_and_response, delete_messages_later

logger = logging.getLogger(__name__)

group_router = Router(name="group")


@group_router.message(Command("group"), IsGroupChatFilter())
async def cmd_group(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Only admin / super admin / bot creator
    if not await admin_service.is_admin(chat_id, user_id):
        bot_msg = await message.answer("Недостаточно прав для создания группы.")
        await delete_command_and_response(message, bot_msg, delay=10)
        return

    # Parse queue titles from arguments
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        bot_msg = await message.answer(
            "Использование: /group <очередь1> <очередь2> [очередь3 ...]\n"
            "Названия очередей через пробел."
        )
        await delete_command_and_response(message, bot_msg, delay=15)
        return

    queue_titles = args[1].strip().split()
    if len(queue_titles) < 2:
        bot_msg = await message.answer(
            "Нужно указать минимум 2 очереди для создания группы."
        )
        await delete_command_and_response(message, bot_msg, delay=10)
        return

    # Resolve queue titles to queue IDs
    all_queues = await queue_service.get_active_queues(chat_id)
    title_to_queue = {q.title.lower(): q for q in all_queues}

    queue_ids: list[int] = []
    not_found: list[str] = []
    seen_ids: set[int] = set()

    for title in queue_titles:
        q = title_to_queue.get(title.lower())
        if not q:
            not_found.append(title)
        elif q.id in seen_ids:
            continue  # skip duplicates
        else:
            queue_ids.append(q.id)
            seen_ids.add(q.id)

    if not_found:
        bot_msg = await message.answer(
            f"Очереди не найдены: {', '.join(not_found)}\n"
            "Проверьте названия. Список очередей: /queues"
        )
        await delete_command_and_response(message, bot_msg, delay=15)
        return

    if len(queue_ids) < 2:
        bot_msg = await message.answer(
            "Нужно минимум 2 уникальные очереди для создания группы."
        )
        await delete_command_and_response(message, bot_msg, delay=10)
        return

    # Create the group
    group = await group_service.create_group(chat_id, queue_ids, user_id)

    # Render and send the group message
    text = await group_service.render_group(group.id)
    sent = await message.answer(text, parse_mode=ParseMode.HTML)

    # Save message_id
    await group_repo.update_group_message_id(group.id, sent.message_id)

    # Delete the user's command message
    await delete_messages_later(message.bot, chat_id, [message.message_id], delay=2)

    # Pin the group message
    try:
        await bot.pin_chat_message(
            chat_id, sent.message_id, disable_notification=True
        )
    except Exception:
        pass
