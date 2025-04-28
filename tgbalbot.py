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

# Логирование
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
        # Очистка текста от скрытых символов
        cleaned_message = clean_text(message_text)

        # Ищем все имена участников (например, @⁨~Имя⁩ или @~Имя)
        matches = re.findall(
            r'(@⁨~.*?⁩|@~[^\n]*?)(?=\s*(?:\n|$))', cleaned_message, re.DOTALL)

        if not matches:
            await update.message.reply_text("Не удалось найти имена участников.")
            return

        # Подсчет количества для каждого уникального участника и проверка галочек
        name_counts = {}
        name_checkmarks = {}
        for match in matches:
            name = match.strip()
            # Убираем лишние пробелы внутри
            name = re.sub(r'\s+', ' ', name)
            name_counts[name] = name_counts.get(name, 0) + 1
            # Проверяем, есть ли галочка в исходной строке после имени
            match_idx = message_text.find(match)
            if match_idx != -1:
                next_text = message_text[match_idx + len(match):]
                name_checkmarks[name] = '✅' in next_text[:10]

        # Формируем строку для подсчета (сохраняем галочки из исходного текста)
        response = ""
        for i, (name, count) in enumerate(name_counts.items(), 1):
            checkmark = "✅" if name_checkmarks.get(name, False) else ""
            response += f"[{i}] {name}{checkmark} - {count}\n"

        total_count = sum(name_counts.values())
        response += f"\nОбщее количество - {total_count}"

        # Создаем измененный текст розыгрыша с галочками для всех имен
        modified_text = ""
        lines = message_text.split('\n')
        for line in lines:
            # Проверяем, содержит ли строка имя участника
            match = re.search(r'(@⁨~.*?⁩|@~[^\n]*?)(?:\s*✅)?', line)
            if match:
                name = match.group(1)
                # Удаляем старую галочку, если она есть
                clean_line = re.sub(r'✅', '', line)
                # Добавляем новую галочку после имени
                modified_line = clean_line + "✅"
                modified_text += modified_line + "\n"
            else:
                modified_text += line + "\n"

        # Удаляем лишний перенос строки в конце
        modified_text = modified_text.rstrip()

        # Отправляем исправленное сообщение с галочками
        await update.message.reply_text(modified_text)

        # Отправляем второй текст с подсчетом
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
        matches = re.findall(r'@~([^-\n]+?)\s*[-—]\s*(\d+)', replied_text)

        if not matches:
            await update.message.reply_text("Не удалось распознать список с номерками.")
            return

        result = ""
        total_sum = 0
        for name, count in matches:
            count = int(count)
            total = count * price
            total_sum += total
            result += f"@~{name.strip()} — {count} × {price} = {total}₽\n"

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
