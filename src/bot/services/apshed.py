import logging
import random
from collections import defaultdict

from aiogram import Bot

from bot.db.methods import get_all_users, update_dick_size


async def minus_penis_cron(bot: Bot):
    """
    This function selects three random users from each chat and decreases their "dick_size" attribute.
    """
    users = await get_all_users()

    chats = defaultdict(list)
    for user in users:
        chats[user.chat_id].append(user)

    for chat_id, user_members in chats.items():
        random_members = select_random_members(user_members, 3)
        list_members = []

        for member in random_members:
            tg_member = await bot.get_chat_member(member.chat_id, member.user_id)
            if tg_member is None or tg_member.status in ["left", "kicked"]:
                continue

            dec = random.randint(-10, -3)
            try:
                await update_dick_size(member.user_id, chat_id, dec)
            except Exception as e:
                logging.error(f"Error updating dick size: {e}")
                continue
            else:
                list_members.append((tg_member, dec))

        message_text = f"Сегодняшние счастливчики: \
{', '.join([f'{member_data[0].user.mention_html()} ({member_data[1]} см)' for member_data in list_members])}"
        await bot.send_message(chat_id=chat_id, text=message_text)


def select_random_members(members, count):
    """
    This function selects a specified number of random members from a list.
    """
    return [random.choice(members) for _ in range(count)]
