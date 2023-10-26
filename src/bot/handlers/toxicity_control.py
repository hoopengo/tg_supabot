from aiogram import F, Router
from aiogram.types import Message, Chat
from bot.db.methods import get_members

from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from bot.middlewares.toxity_middleware import ToxityMessageMiddleware

toxicity_router = Router()
toxicity_router.message.filter(F.chat.type != "private")


async def get_tox_stats(chat: Chat):
    users = sorted(list(await get_members(chat.id, limit=10)), key=lambda x: -x.toxicity_level)
    result = []

    for v, user in enumerate(users, 1):
        if user.toxicity_level == 0:
            continue

        try:
            obj = {"member": await chat.get_member(user.user_id), "user": user}
        except TelegramBadRequest:
            pass
        else:
            result.append(obj)

    return result


@toxicity_router.message(Command("top_toxic", ignore_case=True), F.chat.type != "private")
async def _command_top_toxic_handler(message: Message):
    users_statistic = []

    members = await get_tox_stats(message.chat)
    for v, obj in enumerate(members, 1):
        member = obj.get("member")
        user = obj.get("user")

        users_statistic.append(f"<b>{v}|{member.user.full_name} — {user.toxicity_level}</b>")

    await message.answer("Топ 10 токсиков\n" + "\n".join(users_statistic))
