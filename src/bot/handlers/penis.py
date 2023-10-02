import random
from contextlib import contextmanager
from datetime import datetime, timedelta
from io import BytesIO
from typing import Sequence

import numpy as np
import pylab as plt
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from bot.db.methods import (
    get_members,
    get_or_create_user,
    get_user,
    last_penis_update_now,
    update_dick_size,
)

penis_router = Router()


@contextmanager
def stats_to_image(users: Sequence[dict[str, str | int]]) -> bytes:
    fig, ax = plt.subplots(figsize=(8, 5), subplot_kw=dict(aspect="equal"))

    labels = [user.get("name") for user in users]
    sizes = [user.get("size") for user in users]

    wedges, texts = ax.pie(
        sizes,
        wedgeprops=dict(width=0.5),
        startangle=-45,
    )

    bbox_props = dict(boxstyle="square,pad=0.3", fc="w", ec="k", lw=0.72)
    kw = dict(arrowprops=dict(arrowstyle="-"), bbox=bbox_props, zorder=0, va="center")

    for i, p in enumerate(wedges):
        ang = (p.theta2 - p.theta1) / 2.0 + p.theta1
        y = np.sin(np.deg2rad(ang))
        x = np.cos(np.deg2rad(ang))
        horizontalalignment = {-1: "right", 1: "left"}[int(np.sign(x))]
        connectionstyle = f"angle,angleA=0,angleB={ang}"
        kw["arrowprops"].update({"connectionstyle": connectionstyle})
        ax.annotate(
            f"{labels[i][:12]} — {sizes[i]} см",
            xy=(x, y),
            xytext=(1.35 * np.sign(x), 1.4 * y),
            horizontalalignment=horizontalalignment,
            **kw,
        )

    ax.axis("equal")
    ax.set_title("Топ пипис")

    image = BytesIO()
    fig.savefig(image, format="png")
    plt.close(fig)

    image.seek(0)
    yield image.getvalue()
    image.close()


@penis_router.message(Command("top_dick", ignore_case=True), F.chat.type != "private")
async def _command_top_dick_handler(message: Message):
    users = await get_members(message.chat.id, limit=10)
    users_statistic = []

    for v, user in enumerate(users, 1):
        if user.penis_size == 0:
            print(user.id, user.penis_size)
            continue

        member = await message.chat.get_member(user.user_id)
        users_statistic.append(
            f"<b>{v}|{member.user.full_name} — {user.penis_size}</b>"
        )

    await message.answer("Топ 10 игроков\n" + "\n".join(users_statistic))


@penis_router.message(Command("stats", ignore_case=True), F.chat.type != "private")
async def _command_stats_handler(message: Message):
    users = await get_members(message.chat.id, limit=10)
    users_statistic = []

    for v, user in enumerate(users, 1):
        if user.penis_size == 0:
            continue

        member = await message.chat.get_member(user.user_id)
        users_statistic.append(
            {"name": member.user.full_name, "rank": v, "size": user.penis_size}
        )

    with stats_to_image(users_statistic) as image_bytes:
        await message.answer_photo(
            BufferedInputFile(image_bytes, "stats-diagram-image")
        )


@penis_router.message(Command("dick", ignore_case=True), F.chat.type != "private")
async def _command_dick_handler(message: Message):
    user = await get_or_create_user(message.from_user.id, message.chat.id)

    seconds_after = 43200 - (datetime.utcnow() - user.last_penis_update).seconds
    if seconds_after >= 0:
        next_attempt = timedelta(seconds=seconds_after)

        return await message.answer(
            f"""{message.from_user.mention_html()}, ты уже играл.
Сейчас он равен {user.penis_size} см.
Ты занимаешь {user.rank} место в топе.
Следующая попытка через {next_attempt}"""
        )
    else:
        dick_append = random.randint(3, 15)
        await update_dick_size(message.from_user.id, message.chat.id, dick_append)
        user = await get_user(message.from_user.id, message.chat.id)

        await message.answer(
            f"""{message.from_user.mention_html()}, твой писюн вырос на {dick_append} см.
Теперь он равен {user.penis_size} см.
Ты занимаешь {user.rank} место в топе
Следующая попытка через 12 часов"""
        )
        await last_penis_update_now(message.from_user.id, message.chat.id)
