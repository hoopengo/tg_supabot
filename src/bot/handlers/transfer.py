import logging
from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from bot.db.methods import get_user_by_username, transfer_penis_size, get_user
from bot.services.auto_delete import delete_command_and_response

logger = logging.getLogger(__name__)

transfer_router = Router()
transfer_router.message.filter(F.chat.type != "private")


@transfer_router.message(
    Command("transfer", ignore_case=True), F.chat.type != "private"
)
async def cmd_transfer(message: Message):
    chat_id = message.chat.id
    sender_id = message.from_user.id

    # Parse target user and amount
    target_user_id = None
    amount = None

    # Check if replying to a message
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user_id = message.reply_to_message.from_user.id
        # Amount should be in the command text
        args = message.text.split()[1:]  # Skip command
        if args:
            try:
                amount = int(args[0])
            except ValueError:
                pass
    else:
        # Parse: /transfer @username 10 or /transfer 10 @username
        args = message.text.split()[1:]  # Skip command
        if len(args) < 2:
            bot_msg = await message.answer(
                "Использование:\n"
                "/transfer @username 10\n"
                "или\n"
                "/transfer 10 @username\n"
                "или ответьте на сообщение и напишите /transfer 10"
            )
            await delete_command_and_response(message, bot_msg)
            return

        # Try to identify which arg is username and which is amount
        username_arg = None
        amount_arg = None

        for arg in args:
            if arg.startswith("@"):
                username_arg = arg
            else:
                try:
                    amount_arg = int(arg)
                except ValueError:
                    pass

        if not username_arg or amount_arg is None:
            bot_msg = await message.answer(
                "Укажите @username и сумму (число).\nПример: /transfer @username 10"
            )
            await delete_command_and_response(message, bot_msg, 10)
            return

        # Resolve username to user_id
        username = username_arg.lstrip("@")
        user = await get_user_by_username(username, chat_id)
        if not user:
            bot_msg = await message.answer(f"Пользователь @{username} не найден в базе.")
            await delete_command_and_response(message, bot_msg, 10)
            return
        target_user_id = user.user_id
        amount = amount_arg

    # Validate amount
    if amount is None or amount <= 0:
        bot_msg = await message.answer("Сумма должна быть положительным числом.")
        await delete_command_and_response(message, bot_msg, 10)
        return

    # Check sender has enough
    sender = await get_user(sender_id, chat_id)
    if not sender:
        bot_msg = await message.answer("Вы не зарегистрированы в системе.")
        await delete_command_and_response(message, bot_msg, 10)
        return

    if sender.penis_size < amount:
        bot_msg = await message.answer(
            f"У тебя недостаточно сантиметров. У тебя {sender.penis_size} см."
        )
        await delete_command_and_response(message, bot_msg, 10)
        return

    # Execute transfer
    success, msg = await transfer_penis_size(
        from_user_id=sender_id,
        to_user_id=target_user_id,
        chat_id=chat_id,
        amount=amount,
    )

    if success:
        # Get updated sender info
        sender = await get_user(sender_id, chat_id)
        receiver = await get_user(target_user_id, chat_id)

        sender_mention = message.from_user.mention_html()
        receiver_mention = f'<a href="tg://user?id={receiver.user_id}">{receiver.first_name or "Пользователь"}</a>'

        bot_msg = await message.answer(
            f"✅ {sender_mention} перевёл {amount} см пользователю {receiver_mention}.\n"
            f"У тебя теперь {sender.penis_size} см.",
            parse_mode=ParseMode.HTML,
        )
        await delete_command_and_response(message, bot_msg)
    else:
        bot_msg = await message.answer(f"❌ {msg}")
        await delete_command_and_response(message, bot_msg, 10)
