from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from bot.db.methods import get_next_sanitaries
from bot.services.auto_delete import delete_command_and_response

sanitary_router = Router()


@sanitary_router.message(
    Command("sanitary", ignore_case=True), F.chat.type != "private"
)
async def _command_sanitary_handler(message: Message, command: CommandObject):
    count = None
    if command.args:
        try:
            count = int(command.args.split(" ")[0])
        except ValueError:
            bot_msg = await message.reply("Аргумент должен быть числом")
            await delete_command_and_response(message, bot_msg, 10)
            return
        count = abs(count)
        if count == 0:
            count = None

    if count is not None:
        sanitaries = await get_next_sanitaries(message.chat.id, count)
    else:
        sanitaries = await get_next_sanitaries(message.chat.id)
    if len(sanitaries) == 0:
        bot_msg = await message.reply("Не найдено кандидатов")
        await delete_command_and_response(message, bot_msg)
        return

    choisen_users = []
    for sanitary in sanitaries:
        member = await message.chat.get_member(sanitary.user_id)
        choisen_users.append(member.user.mention_html())

    bot_msg = await message.answer(
        "Дежурные: " + ", ".join(choisen_users), parse_mode=ParseMode.HTML
    )
    await delete_command_and_response(message, bot_msg)
