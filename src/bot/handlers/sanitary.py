from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from bot.db.methods import get_next_sanitaries

sanitary_router = Router()


@sanitary_router.message(Command("sanitary", ignore_case=True), F.chat.type != "private")
async def _command_sanitary_handler(message: Message, command: CommandObject):
    count = None
    if command.args:
        try:
            count = int(command.args.split(" ")[0])
        except ValueError:
            await message.reply("Аргумент должен быть числом")
        finally:
            count = abs(count)
            if count == 0:
                count = None

    sanitaries = await get_next_sanitaries(message.chat.id, count)
    if len(sanitaries) == 0:
        return await message.reply("Не найдено кандидатов")

    choisen_users = []
    for sanitary in sanitaries:
        member = await message.chat.get_member(sanitary.user_id)
        choisen_users.append(member.user.mention_html())

    await message.answer("Дежурные: " + ", ".join(choisen_users))
