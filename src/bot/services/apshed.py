import logging
import random
from collections import defaultdict

from aiogram import Bot

from bot.db.methods import get_rating_users, update_dick_size


async def minus_penis_cron(bot: Bot):
    """
    This function selects three random users from each chat and decreases their "dick_size" attribute.
    """
    users = await get_rating_users()

    chats = defaultdict(list)
    for user in users:
        chats[user.chat_id].append(user)

    for chat_id, user_members in chats.items():
        random_members = random.sample(user_members, 3)
        list_members = []

        for member in random_members:
            tg_member = await bot.get_chat_member(member.chat_id, member.user_id)
            if tg_member is None or tg_member.status in ["left", "kicked"]:
                continue

            dec = random.randint(-10, 10)
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
