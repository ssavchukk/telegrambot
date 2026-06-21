import asyncio
import time
import re
import logging
import unicodedata
from collections import defaultdict, deque

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramMigrateToChat


TOKEN_ANTIFLOOD = "8255962530:AAGbYDiCaSS_ZAmYokA9wRSovRkXprce_Q4"
TOKEN_LOTTERY = "7757094224:AAGWA-R5TEpM6tZT-ZcXaPF6cCADXs4cDn8"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =========================
# БОТ 1 — АНТИФЛУД
# =========================

bot1 = Bot(TOKEN_ANTIFLOOD)
dp1 = Dispatcher()

FLOOD_LIMIT = 5
FLOOD_INTERVAL = 4
MUTE_TIME = 60
DUPLICATE_LIMIT = 3

messages = defaultdict(deque)
last_message = {}
duplicate_count = defaultdict(int)


def get_message_key(message: types.Message):
    if message.text:
        return f"text:{message.text.strip().lower()}"
    if message.caption:
        return f"caption:{message.caption.strip().lower()}"
    if message.sticker:
        return f"sticker:{message.sticker.file_unique_id}"
    if message.photo:
        return f"photo:{message.photo[-1].file_unique_id}"
    if message.video:
        return f"video:{message.video.file_unique_id}"
    if message.animation:
        return f"animation:{message.animation.file_unique_id}"
    if message.voice:
        return f"voice:{message.voice.file_unique_id}"
    if message.video_note:
        return f"video_note:{message.video_note.file_unique_id}"
    if message.audio:
        return f"audio:{message.audio.file_unique_id}"
    if message.document:
        return f"document:{message.document.file_unique_id}"
    return "other"


@dp1.message(CommandStart())
async def start_antiflood(message: types.Message):
    await message.answer("Антифлуд бот работает.")


@dp1.message()
async def anti_flood(message: types.Message):
    if message.chat.type not in ["group", "supergroup"]:
        return

    user_id = message.from_user.id
    now = time.time()

    try:
        member = await bot1.get_chat_member(message.chat.id, user_id)
    except TelegramMigrateToChat:
        return

    if member.status in ["creator", "administrator"]:
        return

    msg_key = get_message_key(message)

    if last_message.get(user_id) == msg_key:
        duplicate_count[user_id] += 1
    else:
        last_message[user_id] = msg_key
        duplicate_count[user_id] = 1

    if duplicate_count[user_id] >= DUPLICATE_LIMIT:
        try:
            await message.delete()
            duplicate_count[user_id] = 0
            last_message[user_id] = None
        except Exception as e:
            print("Ошибка удаления дубля:", e)
        return

    messages[user_id].append(now)

    while messages[user_id] and now - messages[user_id][0] > FLOOD_INTERVAL:
        messages[user_id].popleft()

    if len(messages[user_id]) >= FLOOD_LIMIT:
        try:
            await message.delete()

            await bot1.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=user_id,
                permissions=types.ChatPermissions(can_send_messages=False),
                until_date=int(now + MUTE_TIME)
            )

            await message.answer(
                f"{message.from_user.full_name} получил мут на {MUTE_TIME} секунд за флуд."
            )

            messages[user_id].clear()
            duplicate_count[user_id] = 0
            last_message[user_id] = None

        except Exception as e:
            print("Ошибка мута:", e)


# =========================
# БОТ 2 — РОЗЫГРЫШИ / ЦЕНА
# =========================

bot2 = Bot(TOKEN_LOTTERY)
dp2 = Dispatcher()


def clean_text(text):
    return ''.join(c for c in text if not unicodedata.category(c).startswith('Cf'))


@dp2.message()
async def handle_lottery_message(message: types.Message):
    if not message.text:
        return

    message_text = message.text.strip()

    if re.match(r'(?i)^\s*.*?баланс.*?', message_text):
        await process_balance_message(message, message_text)

    elif re.match(r'(?i)^\s*.*?ура(?:а+)?\s*.*?', message_text):
        await process_lottery_message(message, message_text)

    elif message_text.lower().startswith("цена") and message.reply_to_message:
        await process_price_message(message, message_text)

    else:
        await message.reply("Сообщение не распознано.")


async def process_balance_message(message: types.Message, message_text: str):
    try:
        amounts = re.findall(r'-\s*([\d\s]+)\s*₽', message_text)
        total = sum(int(a.replace(" ", ""))
                    for a in amounts if a.replace(" ", "").isdigit())
        await message.reply(f"💰 Общая сумма: {total}₽")
    except Exception as e:
        logger.error(f"Ошибка в process_balance_message: {e}")
        await message.reply("Ошибка при обработке баланса.")


async def process_lottery_message(message: types.Message, message_text: str):
    try:
        cleaned_message = clean_text(message_text)

        matches = re.findall(
            r'(@⁨~.*?⁩|@~[^\n]*?)(?=\s*(?:\n|$))',
            cleaned_message,
            re.DOTALL
        )

        if not matches:
            await message.reply("Не удалось найти имена участников.")
            return

        name_counts = {}
        name_checkmarks = {}

        for match in matches:
            split_names = [n.strip() for n in match.split("/") if n.strip()]

            for name in split_names:
                count = 1 if len(split_names) == 1 else 0.5
                name_counts[name] = name_counts.get(name, 0) + count

                match_idx = message_text.find(match)
                if match_idx != -1:
                    next_text = message_text[match_idx + len(match):]
                    name_checkmarks[name] = '✅' in next_text[:10]

        response = ""

        for i, (name, count) in enumerate(name_counts.items(), 1):
            checkmark = "✅" if name_checkmarks.get(name, False) else ""
            count_str = f"{int(count)}" if count == int(count) else f"{count}"
            response += f"[{i}] {name}{checkmark} - {count_str}\n"

        total_count = sum(name_counts.values())
        total_count_str = f"{int(total_count)}" if total_count == int(
            total_count) else f"{total_count}"

        response += f"\nОбщее количество - {total_count_str}"

        modified_text = ""
        lines = message_text.split('\n')

        for line in lines:
            match = re.search(r'(@⁨~.*?⁩|@~[^\n]*?)(?:\s*✅)?', line)

            if match:
                clean_line = re.sub(r'✅', '', line)

                if "/" in clean_line:
                    parts = [p.strip() for p in clean_line.split("/")]
                    clean_line = " / ".join([p + "✅" for p in parts if p])
                else:
                    clean_line = clean_line.strip() + "✅"

                modified_text += clean_line + "\n"
            else:
                modified_text += line + "\n"

        await message.reply(modified_text.rstrip())
        await message.reply(response)

    except Exception as e:
        logger.error(f"Ошибка в process_lottery_message: {e}")
        await message.reply("Ошибка при обработке розыгрыша.")


async def process_price_message(message: types.Message, message_text: str):
    try:
        price_match = re.search(r'цена\s*\n?\s*(\d+)',
                                message_text, re.IGNORECASE)

        if not price_match:
            await message.reply("Не удалось распознать сумму.")
            return

        price = int(price_match.group(1))

        if not message.reply_to_message.text:
            await message.reply("В ответном сообщении нет текста.")
            return

        replied_text = message.reply_to_message.text
        matches = re.findall(r'@~([^-\n]+?)\s*[-—]\s*([\d.,]+)', replied_text)

        if not matches:
            await message.reply("Не удалось распознать список с номерками.")
            return

        result = ""
        total_sum = 0

        for name, count_str in matches:
            count_str = count_str.replace(",", ".")
            count = float(count_str)
            total = int(count * price)
            total_sum += total

            count_str_fmt = f"{int(count)}" if count == int(
                count) else f"{count}"
            result += f"@~{name.strip()} — {count_str_fmt} × {price} = {total}₽\n"

        await message.reply(result.strip())
        await message.reply(f"💰 Общая сумма: {total_sum}₽")

    except Exception as e:
        logger.error(f"Ошибка в process_price_message: {e}")
        await message.reply("Ошибка при обработке цены.")


# =========================
# ЗАПУСК ДВУХ БОТОВ
# =========================

async def main():
    await asyncio.gather(
        dp1.start_polling(bot1),
        dp2.start_polling(bot2)
    )


if __name__ == "__main__":
    asyncio.run(main())
