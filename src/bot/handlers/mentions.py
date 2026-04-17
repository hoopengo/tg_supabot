from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from bot.db.methods import get_members
from bot.services.auto_delete import delete_command_and_response

mentions_router = Router()


@mentions_router.message(Command("all", ignore_case=True), F.chat.type != "private")
async def _command_mention_all_handler(message: Message):
    members = await get_members(message.chat.id)
    mention_list = []

    for user in members:
        member = await message.chat.get_member(user.user_id)

        if member.user.username:
            mention_list.append(f"@{member.user.username}")
        else:
            mention_text = (
                f'<a href="tg://user?id={member.user.id}">{member.user.first_name}</a>'
            )
            mention_list.append(mention_text)

    mention = ", ".join(mention_list)
    if mention == "":
        bot_msg = await message.reply("В системе нет зарегистрированых пользователей.")
        await delete_command_and_response(message, bot_msg)
        return
    bot_msg = await message.reply(mention, parse_mode=ParseMode.HTML)
    await delete_command_and_response(message, bot_msg, 60)
