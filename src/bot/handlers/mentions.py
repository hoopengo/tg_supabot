from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from bot.db.methods import get_members

mentions_router = Router()


@mentions_router.message(Command("all", ignore_case=True), F.chat.type != "private")
async def _command_mention_all_handler(message: Message):
    members = await get_members(message.chat.id)
    mention_list = []

    # Iterate through members by user_id
    for user in members:
        # Get each member individually
        member = await message.chat.get_member(user.user_id)

        # Mention each member in the message
        if member.user.username:
            mention_list.append(f"@{member.user.username}")
        else:
            mention_text = f'<a href="tg://user?id={member.user.id}">{member.user.first_name}</a>'
            mention_list.append(mention_text)

    mention = ", ".join(mention_list)
    if mention == "":
        return await message.reply("В системе нет зарегистрированых пользователей.")
    await message.reply(mention)
