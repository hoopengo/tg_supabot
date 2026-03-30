import argparse
import asyncio
import logging
from pathlib import Path

from aiogram import Bot
from dotenv import dotenv_values

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s - %(message)s",
)

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
ENV_PATH = PROJECT_ROOT / "settings" / "bot.env"


async def print_chat_info(bot: Bot, chat_id: int) -> None:
    try:
        chat = await bot.get_chat(chat_id=chat_id)
    except Exception as e:
        logging.error("Cannot get chat %d: %s", chat_id, e)
        return

    invite_link = getattr(chat, "invite_link", None)
    title = chat.title or chat.full_name or "—"
    logging.info(
        "Chat: id=%d | type=%s | title=%s | invite_link=%s",
        chat.id,
        chat.type,
        title,
        invite_link or "N/A",
    )


async def main():
    parser = argparse.ArgumentParser(
        description="List Telegram chats/groups where the bot exists"
    )
    parser.add_argument(
        "chat_ids",
        nargs="*",
        type=int,
        help="Known chat/group IDs to inspect (optional)",
    )
    args = parser.parse_args()

    env = dotenv_values(ENV_PATH)
    token = env.get("TOKEN")
    if not token:
        logging.error("TOKEN not found in %s", ENV_PATH)
        return

    bot = Bot(token=token)
    me = await bot.get_me()
    logging.info("Bot: @%s (id=%d, name=%s)", me.username, me.id, me.full_name)

    seen_chat_ids: set[int] = set()

    # 1) Inspect explicitly passed chat IDs
    for cid in args.chat_ids:
        if cid not in seen_chat_ids:
            seen_chat_ids.add(cid)
            await print_chat_info(bot, cid)

    # 2) Try to discover chats from pending updates
    updates = await bot.get_updates(timeout=1)
    logging.info("Received %d pending updates", len(updates))

    for upd in updates:
        msg = (
            upd.message
            or upd.edited_message
            or upd.channel_post
            or upd.edited_channel_post
        )
        if not msg or not msg.chat:
            continue
        chat = msg.chat
        if chat.id in seen_chat_ids:
            continue
        seen_chat_ids.add(chat.id)
        await print_chat_info(bot, chat.id)

    if not seen_chat_ids:
        logging.warning(
            "No chats found.\n"
            "  - Make sure no other bot instance is running (docker, polling).\n"
            "  - Or pass known chat IDs:  python scripts/list_chats.py -1001234567890"
        )

    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
