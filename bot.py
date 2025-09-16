import os
import logging
import time
import json
import threading
import asyncio
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from telegram.error import TelegramError

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Создаем простейший веб-сервер для Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!", 200

def run_web_server():
    # Render сам устанавливает переменную окружения PORT, которую нужно использовать
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting web server on port {port}")
    # Запускаем сервер. Важно: host='0.0.0.0' - слушаем все входящие подключения
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# Конфигурация
TOKEN = os.getenv('TOKEN', '8091371448:AAF7eynXFflA4VO3lz7a1vHREN0tM81FOl4')
GROUP_ID = int(os.getenv('TELEGRAM_GROUP_ID', '-1002789329715'))

# Состояния для ConversationHandler
TEXT, PHOTO_OR_DOC = range(2)

# Клавиатуры
def get_main_keyboard():
    categories = [
        ("Автомобильные товары", "auto"),
        ("Мотоциклы и питбайки", "moto"),
        ("Игрушки", "toys"),
        ("Сумки", "bags"),
        ("Одежда", "clothes"),
        ("Спортивный инвентарь", "sport"),
        ("Электроника", "electronics"),
        ("Бытовая техника", "appliances"),
        ("Домашний декор", "decor"),
        ("Красота и здоровье", "beauty"),
        ("Ювелирка и аксессуары", "jewelry"),
        ("Инструменты и оборудование", "tools"),
        ("Офисные товары", "office"),
        ("Детские товары", "kids"),
        ("Станки и механизмы", "machinery")
    ]
    buttons = [[InlineKeyboardButton(cat[0], callback_data=f"category_{cat[1]}")] for cat in categories]
    buttons.append([InlineKeyboardButton("Другие товары", callback_data="other_items")])
    buttons.append([InlineKeyboardButton("Помощь", callback_data="help")])
    buttons.append([InlineKeyboardButton("Контакты", callback_data="contacts")])
    buttons.append([InlineKeyboardButton("Новости/Отгрузки", callback_data="news_feed")])
    return InlineKeyboardMarkup(buttons)

def get_cancel_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="cancel")]])

# Функции для работы с новостей
def get_news_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'news.json')

def load_news():
    try:
        news_path = get_news_path()
        with open(news_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_news(news):
    news_path = get_news_path()
    with open(news_path, 'w', encoding='utf-8') as f:
        json.dump(news, f, ensure_ascii=False, indent=4)

# Вспомогательные функции
async def cancel_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "❌ Запрос отменён. Выберите категорию:",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Запрос отменён. Выберите категорию:",
            reply_markup=get_main_keyboard()
        )

async def send_to_group(context: ContextTypes.DEFAULT_TYPE, message: str, photo=None, document=None, username=None, request_id=None, category=None):
    logger.info(f"Sending to group {GROUP_ID}: {message}")
    try:
        full_message = f"Запрос #{request_id} из категории '{category}' от @{username if username else 'неизвестный'}:\n{message}"
        await context.bot.send_message(chat_id=GROUP_ID, text=full_message)
        if photo:
            await context.bot.send_photo(chat_id=GROUP_ID, photo=photo[-1].file_id)
        if document:
            await context.bot.send_document(chat_id=GROUP_ID, document=document.file_id)
    except TelegramError as e:
        logger.error(f"Ошибка Telegram: {e}")
        raise
    except Exception as e:
        logger.error(f"Неизвестная ошибка отправки: {e}")
        raise

# Обработчики
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    logger.info(f"Received /start from chat_id: {chat_id}")
    await update.message.reply_text(
        "Добро пожаловать в 'Товары из Китая' — ваш надежный партнер для импорта из Китая. Мы специализируемся на автомобильной индустрии, но можем заказать абсолютно всё: от запчастей до станков и коммерческих механизмов. Быстрая коммуникация с поставщиками, выгодные цены и удобная доставка. Опишите товар, приложите фото/видео или укажите код — и мы найдём лучшее предложение!\n\nМы открыты для сотрудничества с автосервисами, магазинами и предпринимателями. Ваши идеи по улучшению приветствуем в 'Помощь'. Начните заказ прямо сейчас — ваш товар уже ждет!",
        reply_markup=get_main_keyboard()
    )

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    logger.info(f"Button pressed: {data}")

    if data == "cancel":
        await cancel_request(update, context)
        return

    if data == "help":
        await query.edit_message_text(
            "Опишите вашу проблему или предложение:",
            reply_markup=get_cancel_keyboard()
        )
        context.user_data['help_request'] = True
        return

    if data == "contacts":
        await query.edit_message_text(
            "Контакты: yuemo-logistics.ru, WhatsApp +86 153 2332 5277",
            reply_markup=get_main_keyboard()
        )
        return

    if data == "news_feed":
        news = load_news()
        if not news:
            await query.edit_message_text(
                "Пока новостей нет. Проверьте позже!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="back_to_main")]])
            )
        else:
            await query.edit_message_text(
                "🔹 Новости и отгрузки:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="back_to_main")]])
            )
            for item in news:
                if item.get('text'):
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=f"- {item['text']}"
                    )
                if item.get('photo'):
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=item['photo']
                    )
        return

    if data == "back_to_main":
        await query.edit_message_text(
            "Выберите категорию:",
            reply_markup=get_main_keyboard()
        )
        return

    if data.startswith("category_"):
        category_map = {
            "auto": "Автомобильные товары",
            "moto": "Мотоциклы и питбайки",
            "toys": "Игрушки",
            "bags": "Сумки",
            "clothes": "Одежда",
            "sport": "Спортивный инвентарь",
            "electronics": "Электроника",
            "appliances": "Бытовая техника",
            "decor": "Домашний декор",
            "beauty": "Красота и здоровье",
            "jewelry": "Ювелирка и аксессуары",
            "tools": "Инструменты и оборудование",
            "office": "Офисные товары",
            "kids": "Детские товары",
            "machinery": "Станки и механизмы"
        }
        
        category_key = data.replace("category_", "")
        category = category_map.get(category_key, "Неизвестно")
        context.user_data['category'] = category
        
        if category == "Автомобильные товары":
            await query.edit_message_text(
                f"Вы выбрали категорию: {category}\nРекомендации: укажите VIN, номер кузова, марку, модель, год. Это ускорит поиск!\nОпишите ваш запрос:",
                reply_markup=get_cancel_keyboard()
            )
        else:
            await query.edit_message_text(
                f"Вы выбрали категорию: {category}\nРекомендации: укажите ключевые идентификаторы (код, артикул) или приложите фото/видео. Это ускорит поиск!\nОпишите ваш запрос:",
                reply_markup=get_cancel_keyboard()
            )
        context.user_data['free_request'] = True
        return

    if data == "other_items":
        context.user_data['category'] = "Другие товары"
        await query.edit_message_text(
            "Вы выбрали категорию: Другие товары\nРекомендации: укажите описание, код или приложите фото/видео. Это ускорит поиск!\nОпишите ваш запрос:",
            reply_markup=get_cancel_keyboard()
        )
        context.user_data['free_request'] = True
        return

# Обработчик для добавления новостей
async def start_add_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите текст новости (или отправьте /cancel для отмены):"
    )
    return TEXT

async def get_news_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['news_text'] = update.message.text
    await update.message.reply_text(
        "Теперь отправьте фото (или документ, если нужно). Если не хотите, просто отправьте /skip:"
    )
    return PHOTO_OR_DOC

async def get_news_photo_or_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and update.message.text.lower() == "/skip":
        photo = None
        document = None
    else:
        photo = update.message.photo[-1].file_id if update.message.photo else None
        document = update.message.document.file_id if update.message.document else None

    news = load_news()
    news.append({
        "text": context.user_data['news_text'],
        "photo": photo,
        "document": document,
        "timestamp": time.time()
    })
    save_news(news)
    await update.message.reply_text(
        f"✅ Новость добавлена в раздел Новости/Отгрузки."
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Добавление новости отменено.",
        reply_markup=get_main_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END

# Обработчик команды /cancel
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cancel_request(update, context)

# Настройка ConversationHandler для добавления новостей
news_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("add_news", start_add_news)],
    states={
        TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_news_text)],
        PHOTO_OR_DOC: [
            MessageHandler(filters.PHOTO, get_news_photo_or_doc),
            MessageHandler(filters.Document.ALL, get_news_photo_or_doc),
            CommandHandler("skip", get_news_photo_or_doc)
        ]
    },
    fallbacks=[CommandHandler("cancel", cancel_news)]
)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    text = update.message.text or update.message.caption
    photo = update.message.photo
    document = update.message.document
    username = update.effective_user.username
    logger.info(f"Received message from @{username}: {text}")

    if text and text.lower() == "отмена":
        await cancel_request(update, context)
        return

    if user_data.get('help_request'):
        if not text and not photo and not document:
            await update.message.reply_text(
                "Пожалуйста, опишите проблему или предложение.",
                reply_markup=get_cancel_keyboard()
            )
            return
        message = f"Запрос помощи от @{username}:\n{text}"
        try:
            await send_to_group(context, message, photo, document, username)
            await update.message.reply_text(
                "✅ Ваш запрос помощи отправлен. Ожидайте ответа.",
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            logger.error(f"Help request error: {e}")
            await update.message.reply_text(
                "❌ Не удалось отправить запрос. Попробуйте позже.",
                reply_markup=get_main_keyboard()
            )
        user_data.clear()
        return

    if user_data.get('free_request'):
        if not text and not photo and not document:
            await update.message.reply_text(
                "Пожалуйста, добавьте описание, фото или документ к вашему запросу.",
                reply_markup=get_cancel_keyboard()
            )
            return
        request_id = int(time.time())
        category = user_data.get('category', 'Неизвестно')
        message = f"Свободный запрос из категории '{category}' от пользователя:\n{text}"
        try:
            await send_to_group(context, message, photo, document, username, request_id, category)
            await update.message.reply_text(
                f"✅ Ваш запрос #{request_id} отправлен поставщикам! Он будет скоро обработан.",
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            logger.error(f"Free request error: {e}")
            await update.message.reply_text(
                "❌ Не удалось отправить запрос. Попробуйте позже.",
                reply_markup=get_main_keyboard()
            )
        user_data.clear()
        return

# Запуск бота в отдельном потоке с правильным event loop
def run_bot():
    try:
        logger.info("Starting Telegram bot...")
        
        # Создаем новый event loop для этого потока
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        application = Application.builder().token(TOKEN).build()

        # Обработчики команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("cancel", cancel_command))
        application.add_handler(news_conv_handler)

        # Обработчики callback и сообщений
        application.add_handler(CallbackQueryHandler(handle_button))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(MessageHandler(filters.PHOTO, handle_message))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_message))

        # Запуск
        logger.info("Bot starting polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Error in bot thread: {e}")
        raise

# Главная функция запуска
def main():
    logger.info("Application starting...")
    
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, name="BotThread")
    bot_thread.daemon = True
    bot_thread.start()
    
    logger.info("Bot thread started, starting web server...")
    
    # Запускаем веб-сервер в основном потоке
    run_web_server()

if __name__ == '__main__':
    main()