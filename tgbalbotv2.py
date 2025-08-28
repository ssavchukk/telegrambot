import re
import logging
import unicodedata
from telegram.ext import Application, MessageHandler, filters
from telegram import Update
from telegram.ext import ContextTypes

TOKEN = input("Token: ").strip()
if not TOKEN:
    print("Token can not be empty")
    exit(1)

# Отключаем лишние логи httpx и urllib3
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Логирование основное
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def clean_text(text):
    return ''.join(c for c in text if not unicodedata.category(c).startswith('Cf'))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text.strip()
    logger.info(f"Получено сообщение: {message_text[:50]}...")

    if re.match(r'(?i)^\s*.*?баланс.*?', message_text):
        await process_balance_message(update, message_text)
    elif re.match(r'(?i)^\s*.*?ура(?:а+)?\s*.*?', message_text):
        await process_lottery_message(update, message_text)
    elif message_text.lower().startswith("цена") and update.message.reply_to_message:
        await process_price_message(update, message_text)
    else:
        await update.message.reply_text("Сообщение не распознано.")


async def process_balance_message(update: Update, message_text: str):
    try:
        amounts = re.findall(r'-\s*([\d\s]+)\s*₽', message_text)
        total = sum(int(a.replace(" ", ""))
                    for a in amounts if a.replace(" ", "").isdigit())
        await update.message.reply_text(f"💰 Общая сумма: {total}₽")
    except Exception as e:
        logger.error(f"Ошибка в process_balance_message: {e}")
        await update.message.reply_text("Ошибка при обработке баланса.")


async def process_lottery_message(update: Update, message_text: str):
    try:
        cleaned_message = clean_text(message_text)
        matches = re.findall(
            r'(@⁨~.*?⁩|@~[^\n]*?)(?=\s*(?:\n|$))', cleaned_message, re.DOTALL)

        if not matches:
            await update.message.reply_text("Не удалось найти имена участников.")
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

        # Создаём текст розыгрыша с галочками (ставим после каждого ника)
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

        modified_text = modified_text.rstrip()

        await update.message.reply_text(modified_text)
        await update.message.reply_text(response)

    except Exception as e:
        logger.error(f"Ошибка в process_lottery_message: {e}")
        await update.message.reply_text("Ошибка при обработке розыгрыша.")


async def process_price_message(update: Update, message_text: str):
    try:
        price_match = re.search(r'цена\s*\n?\s*(\d+)',
                                message_text, re.IGNORECASE)
        if not price_match:
            await update.message.reply_text("Не удалось распознать сумму.")
            return

        price = int(price_match.group(1))
        replied_text = update.message.reply_to_message.text
        matches = re.findall(r'@~([^-\n]+?)\s*[-—]\s*([\d.,]+)', replied_text)

        if not matches:
            await update.message.reply_text("Не удалось распознать список с номерками.")
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

        await update.message.reply_text(result.strip())
        await update.message.reply_text(f"💰 Общая сумма: {total_sum}₽")
    except Exception as e:
        logger.error(f"Ошибка в process_price_message: {e}")
        await update.message.reply_text("Ошибка при обработке цены.")


def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Запуск бота...")
    application.run_polling()


if __name__ == "__main__":
    main()
